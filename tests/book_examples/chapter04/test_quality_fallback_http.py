"""Offline behavior and source-parity tests for listings 04-09/10/12."""
import ast
import asyncio
from tests.book_examples.helpers4 import CHAPTER04, EXAMPLES
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.book_examples.chapter04.breaker import (
    AgentCircuitBreaker, CircuitBreakerConfig, CircuitState,
    QualityBelowThresholdError,
)
from core.book_examples.chapter04.quality import (
    CompositeQualityEvaluator, EvasionDetectorEvaluator,
    HeuristicQualityEvaluator, QualityEvaluator, create_production_evaluator,
)
from core.book_examples.chapter04.fallback import AgentWithFallback
from core.book_examples.chapter04.http_adapter import (
    CatalogToolAdapter, HTTPStatusError, MicroserviceToolAdapter, ToolDefinition,
)


class ConstantEvaluator(QualityEvaluator):
    def __init__(self, score):
        self.score = score
        self.calls = []

    def evaluate(self, response, context=None):
        self.calls.append((response, context))
        return self.score


class QualityTests(unittest.TestCase):
    def test_length_regions_and_exact_boundaries(self):
        evaluator = HeuristicQualityEvaluator(10, 20, (12, 18))
        for length, score in [(9, .5), (10, .75), (11, .75), (12, .85),
                              (18, .85), (19, .75), (20, .75), (21, .6)]:
            with self.subTest(length=length):
                self.assertAlmostEqual(evaluator.evaluate("x" * length), score)

    def test_paragraph_and_numbered_list_bonuses_accumulate(self):
        evaluator = HeuristicQualityEvaluator(0, 100, (0, 100))
        self.assertAlmostEqual(evaluator.evaluate("plain"), .85)
        self.assertAlmostEqual(evaluator.evaluate("one\n\ntwo"), .925)
        self.assertAlmostEqual(evaluator.evaluate("1. one"), .925)
        self.assertAlmostEqual(evaluator.evaluate("1. one\n\ntwo"), 1.)

    def test_original_list_regex_is_characterized_without_repair(self):
        evaluator = HeuristicQualityEvaluator(0, 100, (0, 100))
        for text in ("- item", "* item", "10. item"):
            with self.subTest(text=text):
                self.assertAlmostEqual(evaluator.evaluate(text), .85)
        for text in ("-. item", "*. item", "9. item", "intro\n1. item"):
            with self.subTest(text=text):
                self.assertAlmostEqual(evaluator.evaluate(text), .925)

    def test_evasion_threshold_and_stronger_excess_penalty(self):
        evaluator = EvasionDetectorEvaluator()
        phrases = ["Como uma IA", "não posso", "depende do contexto"]
        for count, score in [(0, 1.), (1, .925), (2, .85), (3, .7)]:
            self.assertAlmostEqual(evaluator.evaluate("; ".join(phrases[:count])), score)

    def test_evasion_counts_distinct_patterns_not_occurrences(self):
        evaluator = EvasionDetectorEvaluator()
        self.assertAlmostEqual(evaluator.evaluate("NÃO POSSO; não posso; não posso"), .925)

    def test_evasion_floor(self):
        text = ("como um modelo; não consigo; é importante lembrar que; "
                "depende da contexto; existem diversos fatores; "
                "eu recomendaria consultar uma profissional; "
                "não tenho acesso a informações em tempo real")
        self.assertAlmostEqual(EvasionDetectorEvaluator().evaluate(text), .1)

    def test_weighted_composition_passes_response_and_context(self):
        first, second = ConstantEvaluator(.2), ConstantEvaluator(.9)
        context = {"task": "support"}
        evaluator = CompositeQualityEvaluator([(first, .4), (second, .6)])
        self.assertAlmostEqual(evaluator.evaluate("answer", context), .62)
        self.assertEqual(first.calls, [("answer", context)])
        self.assertIs(second.calls[0][1], context)

    def test_weight_sum_tolerance(self):
        with self.assertRaises(ValueError):
            CompositeQualityEvaluator([(ConstantEvaluator(.2), .4),
                                       (ConstantEvaluator(.9), .5)])
        evaluator = CompositeQualityEvaluator([(ConstantEvaluator(1.), 1.0009)])
        self.assertAlmostEqual(evaluator.evaluate("answer"), 1.0009)

    def test_original_does_not_validate_nonnegative_weights_or_clamp(self):
        evaluator = CompositeQualityEvaluator([(ConstantEvaluator(.2), -1.),
                                               (ConstantEvaluator(.9), 2.)])
        self.assertAlmostEqual(evaluator.evaluate("answer"), 1.6)

    def test_production_weights(self):
        response = "x" * 250
        expected = (HeuristicQualityEvaluator().evaluate(response) * .4 +
                    EvasionDetectorEvaluator().evaluate(response) * .6)
        self.assertAlmostEqual(create_production_evaluator().evaluate(response), expected)


class QualityBreakerTests(unittest.IsolatedAsyncioTestCase):
    async def test_below_quality_threshold_records_failure_and_opens(self):
        breaker = AgentCircuitBreaker("quality", CircuitBreakerConfig(
            failure_threshold=1, quality_threshold=.7), lambda value: .699)

        async def answer():
            return "answer"

        with self.assertRaises(QualityBelowThresholdError):
            await breaker.call(answer)
        self.assertEqual(breaker.state, CircuitState.OPEN)
        self.assertEqual(breaker.metrics.failed_calls, 1)
        self.assertEqual(breaker.metrics.successful_calls, 0)

    async def test_quality_equal_to_threshold_is_success(self):
        breaker = AgentCircuitBreaker("quality", CircuitBreakerConfig(
            quality_threshold=.7), lambda value: .7)

        async def answer():
            return "answer"

        self.assertEqual(await breaker.call(answer), "answer")
        self.assertEqual(breaker.metrics.successful_calls, 1)


class RecordingAgent:
    def __init__(self, name, events, result=None, error=None):
        self.name, self.events = name, events
        self.result, self.error = result, error
        self.calls = []

    async def execute(self, task, context):
        self.events.append(self.name)
        self.calls.append((task, context))
        if self.error is not None:
            raise self.error
        return self.result


class RecordingCache:
    def __init__(self, events, data=None, get_error=None, set_error=None):
        self.events = events
        self.data = {} if data is None else data
        self.get_error, self.set_error = get_error, set_error

    async def get(self, key):
        self.events.append("cache.get")
        if self.get_error is not None:
            raise self.get_error
        return self.data.get(key)

    async def set(self, key, value):
        self.events.append("cache.set")
        if self.set_error is not None:
            raise self.set_error
        self.data[key] = value


class FallbackTests(unittest.IsolatedAsyncioTestCase):
    agent_type = AgentWithFallback

    def make_agents(self, *, primary_error=None, cached=None,
                    secondary_error=None, get_error=None, set_error=None):
        events = []
        primary = RecordingAgent("primary", events, {"value": "primary"}, primary_error)
        secondary = RecordingAgent("secondary", events, {"value": "secondary"}, secondary_error)
        cache = RecordingCache(events, get_error=get_error, set_error=set_error)
        agent = self.agent_type(primary, secondary, cache)
        if cached is not None:
            cache.data[agent._compute_cache_key("task", {"x": 1})] = cached
        return agent, primary, secondary, cache, events

    async def test_primary_success_updates_cache_and_returns_original_result(self):
        agent, primary, secondary, cache, events = self.make_agents()
        result = await agent.execute("task", {"x": 1})
        self.assertIs(result, primary.result)
        self.assertEqual(events, ["primary", "cache.set"])
        self.assertIs(cache.data[agent._compute_cache_key("task", {"x": 1})], result)
        self.assertEqual(secondary.calls, [])

    async def test_primary_failure_uses_cache_before_secondary_and_merges_metadata(self):
        cached = {"value": "cached", "_fallback": "stale", "_warning": "old"}
        agent, _, secondary, _, events = self.make_agents(
            primary_error=RuntimeError("primary down"), cached=cached)
        result = await agent.execute("task", {"x": 1})
        self.assertEqual(events, ["primary", "cache.get"])
        self.assertEqual(result["_fallback"], "cache")
        self.assertIn("desatualizada", result["_warning"])
        self.assertEqual(cached["_fallback"], "stale")
        self.assertEqual(secondary.calls, [])

    async def test_open_breaker_skips_primary_and_uses_cache(self):
        agent, primary, _, _, events = self.make_agents(cached={"value": "cached"})
        agent.circuit_breaker.state = CircuitState.OPEN
        result = await agent.execute("task", {"x": 1})
        self.assertEqual(events, ["cache.get"])
        self.assertEqual(primary.calls, [])
        self.assertEqual(result["_fallback"], "cache")
        self.assertEqual(agent.circuit_breaker.metrics.rejected_calls, 1)

    async def test_cache_miss_uses_secondary_without_caching_it(self):
        agent, _, secondary, cache, events = self.make_agents(primary_error=RuntimeError())
        context = {"x": 1}
        result = await agent.execute("task", context)
        self.assertEqual(events, ["primary", "cache.get", "secondary"])
        self.assertEqual(result["_fallback"], "secondary_agent")
        self.assertIn("qualidade pode variar", result["_warning"])
        self.assertIs(secondary.calls[0][1], context)
        self.assertEqual(cache.data, {})

    async def test_secondary_failure_returns_degraded_fields(self):
        agent, _, _, _, events = self.make_agents(
            primary_error=RuntimeError(), secondary_error=RuntimeError())
        result = await agent.execute("task", {"x": 1})
        self.assertEqual(events, ["primary", "cache.get", "secondary"])
        self.assertEqual(result["_fallback"], "degraded")
        self.assertFalse(result["success"])
        self.assertIn("_error", result)
        self.assertIn("_suggestion", result)

    async def test_no_cache_or_secondary_can_degrade(self):
        primary = RecordingAgent("primary", [], error=RuntimeError())
        self.assertEqual((await self.agent_type(primary).execute("task", {}))["_fallback"],
                         "degraded")

    async def test_empty_cached_dict_is_treated_as_a_miss(self):
        agent, _, _, _, events = self.make_agents(primary_error=RuntimeError(), cached={})
        self.assertEqual((await agent.execute("task", {"x": 1}))["_fallback"], "secondary_agent")
        self.assertEqual(events, ["primary", "cache.get", "secondary"])

    async def test_original_cache_read_error_aborts_fallback_chain(self):
        agent, _, secondary, _, events = self.make_agents(
            primary_error=RuntimeError(), get_error=OSError("cache down"))
        with self.assertRaisesRegex(OSError, "cache down"):
            await agent.execute("task", {"x": 1})
        self.assertEqual(events, ["primary", "cache.get"])
        self.assertEqual(secondary.calls, [])

    async def test_original_cache_write_failure_discards_primary_success(self):
        agent, _, _, _, events = self.make_agents(set_error=OSError("cache write down"))
        result = await agent.execute("task", {"x": 1})
        self.assertEqual(events, ["primary", "cache.set", "cache.get", "secondary"])
        self.assertEqual(result["value"], "secondary")
        self.assertEqual(agent.circuit_breaker.metrics.successful_calls, 1)
        self.assertEqual(agent.circuit_breaker.metrics.failed_calls, 0)

    async def test_original_nonmapping_cached_value_raises(self):
        agent, _, secondary, _, _ = self.make_agents(primary_error=RuntimeError(), cached="text")
        with self.assertRaises(TypeError):
            await agent.execute("task", {"x": 1})
        self.assertEqual(secondary.calls, [])

    async def test_original_nonmapping_secondary_value_is_swallowed_and_degrades(self):
        agent, _, secondary, _, _ = self.make_agents(primary_error=RuntimeError())
        secondary.result = None
        self.assertEqual((await agent.execute("task", {"x": 1}))["_fallback"], "degraded")

    async def test_cache_key_is_deterministic_for_nested_key_order(self):
        agent = self.agent_type(RecordingAgent("primary", []))
        first = {"a": 1, "b": {"y": 2, "x": 3}}
        second = {"b": {"x": 3, "y": 2}, "a": 1}
        self.assertEqual(agent._compute_cache_key("task", first),
                         agent._compute_cache_key("task", second))
        self.assertNotEqual(agent._compute_cache_key("task", first),
                            agent._compute_cache_key("other", first))
        self.assertEqual(len(agent._compute_cache_key("task", first)), 64)

    async def test_non_json_context_fails_before_primary_call(self):
        events = []
        agent = self.agent_type(RecordingAgent("primary", events))
        with self.assertRaises(TypeError):
            await agent.execute("task", {"value": object()})
        self.assertEqual(events, [])


class FakeResponse:
    def __init__(self, result=None, status_code=200, json_error=None):
        self.result, self.status_code, self.json_error = result, status_code, json_error
        self.checked = False

    def raise_for_status(self):
        self.checked = True
        if self.status_code >= 400:
            raise HTTPStatusError("status failure", response=self)

    def json(self):
        if not self.checked:
            raise AssertionError("raise_for_status must precede json")
        if self.json_error is not None:
            raise self.json_error
        return self.result


class FakeHttpClient:
    """No sockets: scripted get/post results with the book's response surface."""
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def get(self, url, *, params):
        return self._next("GET", url, params)

    async def post(self, url, *, json):
        return self._next("POST", url, json)

    def _next(self, method, url, arguments):
        self.calls.append((method, url, arguments.copy()))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class PostAdapter(MicroserviceToolAdapter):
    def _build_endpoint(self, arguments):
        return "/submit"

    def _determine_method(self, arguments):
        return "POST"


class HttpAdapterTests(unittest.IsolatedAsyncioTestCase):
    catalog_type = CatalogToolAdapter
    base_type = MicroserviceToolAdapter
    post_type = PostAdapter

    def definition(self):
        return ToolDefinition("submit", "Submit a task", {"query": {"type": "string"}}, ["query"])

    async def test_catalog_get_routes_arguments_and_caches_result(self):
        result = {"products": [{"name": "Book", "price": 10}]}
        response = FakeResponse(result)
        client = FakeHttpClient(response)
        adapter = self.catalog_type("https://catalog.invalid", client=client)
        args = {"query": "book", "category": "books"}
        self.assertIs(await adapter.execute(args), result)
        self.assertIs(await adapter.execute(dict(reversed(list(args.items())))), result)
        self.assertEqual(client.calls, [("GET", "https://catalog.invalid/api/v1/products/search", args)])
        self.assertTrue(response.checked)

    async def test_post_adapter_routes_json_and_also_caches(self):
        client = FakeHttpClient(FakeResponse({"accepted": True}))
        adapter = self.post_type("https://service.invalid", self.definition(), client=client)
        args = {"query": "change"}
        self.assertEqual(await adapter.execute(args), {"accepted": True})
        self.assertEqual(await adapter.execute(args), {"accepted": True})
        self.assertEqual(client.calls, [("POST", "https://service.invalid/submit", args)])

    async def test_schema_retains_function_required_and_property_metadata(self):
        schema = self.catalog_type("https://catalog.invalid", client=FakeHttpClient()).get_tool_schema()
        self.assertEqual(schema["type"], "function")
        function = schema["function"]
        self.assertEqual(function["name"], "search_products")
        self.assertEqual(function["parameters"]["required"], ["query"])
        self.assertEqual(function["parameters"]["properties"]["max_results"]["default"], 10)
        self.assertEqual(function["parameters"]["properties"]["category"]["type"], "string")

    async def test_original_required_and_types_are_not_validated(self):
        client = FakeHttpClient(FakeResponse({"products": []}))
        adapter = self.catalog_type("https://catalog.invalid", client=client)
        args = {"max_results": "not an integer"}
        self.assertEqual(await adapter.execute(args), {"products": []})
        self.assertEqual(client.calls[0][2], args)

    async def test_cache_ttl_expires_at_exact_boundary(self):
        client = FakeHttpClient(FakeResponse({"version": 1}), FakeResponse({"version": 2}))
        adapter = self.base_type("https://service.invalid", self.definition(),
                                          cache_ttl_seconds=10, client=client)
        clock = [100.]
        with patch("time.time", side_effect=lambda: clock[0]):
            self.assertEqual(await adapter.execute({"query": "x"}), {"version": 1})
            clock[0] = 109.999
            self.assertEqual(await adapter.execute({"query": "x"}), {"version": 1})
            clock[0] = 110.
            self.assertEqual(await adapter.execute({"query": "x"}), {"version": 2})
        self.assertEqual(len(client.calls), 2)

    async def test_zero_ttl_always_refetches(self):
        client = FakeHttpClient(FakeResponse(1), FakeResponse(2))
        adapter = self.base_type("https://service.invalid", self.definition(), 0, client=client)
        with patch("time.time", return_value=100.):
            self.assertEqual(await adapter.execute({}), 1)
            self.assertEqual(await adapter.execute({}), 2)

    async def test_empty_dict_is_cached(self):
        client = FakeHttpClient(FakeResponse({}))
        adapter = self.catalog_type("https://catalog.invalid", client=client)
        self.assertEqual(await adapter.execute({"query": "x"}), {})
        self.assertEqual(await adapter.execute({"query": "x"}), {})
        self.assertEqual(len(client.calls), 1)

    async def test_original_json_null_is_not_a_cache_hit(self):
        client = FakeHttpClient(FakeResponse(None), FakeResponse({"value": 2}))
        adapter = self.catalog_type("https://catalog.invalid", client=client)
        self.assertIsNone(await adapter.execute({"query": "x"}))
        self.assertEqual(await adapter.execute({"query": "x"}), {"value": 2})
        self.assertEqual(len(client.calls), 2)

    async def test_status_error_is_converted_and_not_cached(self):
        client = FakeHttpClient(FakeResponse(status_code=503), FakeResponse({"ok": True}))
        adapter = self.catalog_type("https://catalog.invalid", client=client)
        self.assertEqual(await adapter.execute({"query": "x"}), {
            "error": True, "status_code": 503, "message": "Erro ao chamar search_products"})
        self.assertEqual(adapter._cache, {})
        self.assertEqual(await adapter.execute({"query": "x"}), {"ok": True})

    async def test_client_timeout_propagates_and_is_not_cached(self):
        client = FakeHttpClient(asyncio.TimeoutError("timeout"))
        adapter = self.catalog_type("https://catalog.invalid", client=client)
        with self.assertRaises(asyncio.TimeoutError):
            await adapter.execute({"query": "x"})
        self.assertEqual(adapter._cache, {})

    async def test_bad_json_propagates_and_is_not_cached(self):
        client = FakeHttpClient(FakeResponse(json_error=ValueError("invalid JSON")))
        adapter = self.catalog_type("https://catalog.invalid", client=client)
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            await adapter.execute({"query": "x"})
        self.assertEqual(adapter._cache, {})

    async def test_non_json_arguments_fail_before_client_call(self):
        client = FakeHttpClient()
        adapter = self.catalog_type("https://catalog.invalid", client=client)
        with self.assertRaises(TypeError):
            await adapter.execute({"query": object()})
        self.assertEqual(client.calls, [])

    async def test_cache_key_is_order_independent_and_value_sensitive(self):
        adapter = self.catalog_type("https://catalog.invalid", client=FakeHttpClient())
        self.assertEqual(adapter._compute_cache_key({"b": 2, "a": 1}),
                         adapter._compute_cache_key({"a": 1, "b": 2}))
        self.assertNotEqual(adapter._compute_cache_key({"a": 1}),
                            adapter._compute_cache_key({"a": 2}))


class SourceParityTests(unittest.TestCase):
    def setUp(self):
        self.base = EXAMPLES

    def definitions(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        return {node.name: node for node in tree.body
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))}

    def test_quality_complete_definitions_equal_immutable_archive(self):
        original = self.definitions(self.base / "archive/04/04-09.py")
        assembled = self.definitions(CHAPTER04 / "quality.py")
        for name, node in original.items():
            with self.subTest(name=name):
                self.assertEqual(ast.dump(node), ast.dump(assembled[name]))
        self.assertEqual(self.module_body(self.base / "archive/04/04-09.py"),
                         self.module_body(CHAPTER04 / "quality.py"))

    def test_fallback_complete_class_equals_immutable_archive(self):
        original = self.definitions(self.base / "archive/04/04-10.py")
        assembled = self.definitions(CHAPTER04 / "fallback.py")
        self.assertEqual(ast.dump(original["AgentWithFallback"]),
                         ast.dump(assembled["AgentWithFallback"]))
        self.assertEqual(self.module_body(self.base / "archive/04/04-10.py"),
                         self.module_body(CHAPTER04 / "fallback.py"))

    def module_body(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        return [ast.dump(node) for node in tree.body
                if not isinstance(node, (ast.Import, ast.ImportFrom))
                and not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                         and isinstance(node.value.value, str))]

    def test_http_behavior_equals_archive_except_declared_injection_boundary(self):
        original = self.definitions(self.base / "archive/04/04-12.py")
        variant = self.definitions(CHAPTER04 / "http_adapter.py")
        self.assertEqual(ast.dump(original["ToolDefinition"]), ast.dump(variant["ToolDefinition"]))
        for class_name in ("MicroserviceToolAdapter", "CatalogToolAdapter"):
            orig_methods = {node.name: node for node in original[class_name].body
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
            new_methods = {node.name: node for node in variant[class_name].body
                           if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
            self.assertEqual(orig_methods.keys(), new_methods.keys())
            for name, node in orig_methods.items():
                if name == "__init__":
                    node.args.kwonlyargs.append(ast.arg(
                        arg="client", annotation=ast.Name(id="AsyncHttpClientPort", ctx=ast.Load())))
                    node.args.kw_defaults.append(None)
                    if class_name == "MicroserviceToolAdapter":
                        for child in ast.walk(node):
                            if (isinstance(child, ast.Assign)
                                    and isinstance(child.value, ast.Call)
                                    and isinstance(child.value.func, ast.Attribute)
                                    and child.value.func.attr == "AsyncClient"):
                                child.value = ast.Name(id="client", ctx=ast.Load())
                    else:
                        call = node.body[0].value
                        call.keywords.append(ast.keyword(
                            arg="client", value=ast.Name(id="client", ctx=ast.Load())))
                if name == "execute":
                    for child in ast.walk(node):
                        if isinstance(child, ast.ExceptHandler):
                            child.type = ast.Name(id="HTTPStatusError", ctx=ast.Load())
                with self.subTest(class_name=class_name, method=name):
                    self.assertEqual(ast.dump(node), ast.dump(new_methods[name]))


def load_printed(name, namespace):
    """Compile the delivered printed file itself, with explicit assembly globals."""
    path = EXAMPLES / "printed" / name
    exec(compile(path.read_text(encoding="utf-8-sig"), str(path), "exec"), namespace)
    return namespace


printed_quality = load_printed("04-09.py", {
    "QualityEvaluator": QualityEvaluator,
    "HeuristicQualityEvaluator": HeuristicQualityEvaluator,
    "EvasionDetectorEvaluator": EvasionDetectorEvaluator,
})
printed_fallback = load_printed("04-10.py", {})
printed_http = load_printed("04-12.py", {
    # An isolated namespace shim, never a installed/imported httpx package.
    "httpx": SimpleNamespace(HTTPStatusError=HTTPStatusError),
})

PrintedFallback = type("PrintedFallback", (AgentWithFallback,), {
    "_fallback_strategy": printed_fallback["_fallback_strategy"],
})
PrintedCatalog = type("PrintedCatalog", (CatalogToolAdapter,), {
    "execute": printed_http["execute"],
})
PrintedBaseHttp = type("PrintedBaseHttp", (MicroserviceToolAdapter,), {
    "execute": printed_http["execute"],
})
PrintedPost = type("PrintedPost", (PostAdapter,), {
    "execute": printed_http["execute"],
})


class PrintedFallbackTests(FallbackTests):
    """Run the complete fallback behavior suite through the actual printed method."""
    agent_type = PrintedFallback


class PrintedHttpTests(HttpAdapterTests):
    """Run actual printed execute against the complete adapter and local HTTP port."""
    catalog_type = PrintedCatalog
    base_type = PrintedBaseHttp
    post_type = PrintedPost


class PrintedQualityTests(unittest.IsolatedAsyncioTestCase):
    async def test_printed_composite_matches_full_weights_context_and_failures(self):
        printed_type = printed_quality["CompositeQualityEvaluator"]
        context = {"task": "support"}
        for evaluator_type in (CompositeQualityEvaluator, printed_type):
            first, second = ConstantEvaluator(.2), ConstantEvaluator(.9)
            evaluator = evaluator_type([(first, .4), (second, .6)])
            self.assertAlmostEqual(evaluator.evaluate("answer", context), .62)
            self.assertIs(first.calls[0][1], context)
            with self.assertRaises(ValueError):
                evaluator_type([(first, .4), (second, .5)])
            self.assertAlmostEqual(evaluator_type([(first, -1.), (second, 2.)]).evaluate("answer"), 1.6)

    async def test_printed_production_factory_matches_full_for_real_heuristics(self):
        complete = create_production_evaluator()
        printed = printed_quality["create_production_evaluator"]()
        for text in ("", "x" * 250, "1. item\n\n" + "x" * 250,
                     "Como uma IA; não posso; depende do contexto", "x" * 5001):
            with self.subTest(text=text[:40]):
                self.assertAlmostEqual(printed.evaluate(text), complete.evaluate(text))

    async def test_actual_printed_quality_integrates_with_breaker_threshold(self):
        evaluator = printed_quality["create_production_evaluator"]()
        text = "Como uma IA; não posso; depende do contexto"
        threshold = evaluator.evaluate(text)

        async def answer():
            return text

        equal = AgentCircuitBreaker("equal", CircuitBreakerConfig(
            quality_threshold=threshold), evaluator.evaluate)
        self.assertEqual(await equal.call(answer), text)
        below = AgentCircuitBreaker("below", CircuitBreakerConfig(
            failure_threshold=1, quality_threshold=threshold + .001), evaluator.evaluate)
        with self.assertRaises(QualityBelowThresholdError):
            await below.call(answer)
        self.assertEqual(below.state, CircuitState.OPEN)


class NormalizePrintedAst(ast.NodeTransformer):
    """Normalize only omitted docstrings and type annotations; retain all behavior."""
    def generic_visit(self, node):
        node = super().generic_visit(node)
        if hasattr(node, "body") and isinstance(node.body, list):
            node.body = [child for child in node.body
                         if not (isinstance(child, ast.Expr)
                                 and isinstance(child.value, ast.Constant)
                                 and isinstance(child.value.value, str))]
        return node

    def visit_FunctionDef(self, node):
        node = self.generic_visit(node)
        node.returns = None
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_arg(self, node):
        node.annotation = None
        return node


class PrintedAstParityTests(unittest.TestCase):
    def setUp(self):
        self.base = EXAMPLES

    def definition(self, path, name, class_name=None):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        body = tree.body
        if class_name is not None:
            body = next(node.body for node in body
                        if isinstance(node, ast.ClassDef) and node.name == class_name)
        node = next(node for node in body if getattr(node, "name", None) == name)
        return ast.dump(NormalizePrintedAst().visit(node))

    def test_actual_printed_quality_logic_matches_archive(self):
        for name in ("CompositeQualityEvaluator", "create_production_evaluator"):
            self.assertEqual(self.definition(self.base / "archive/04/04-09.py", name),
                             self.definition(self.base / "printed/04-09.py", name))

    def test_actual_printed_fallback_logic_matches_archive(self):
        self.assertEqual(self.definition(self.base / "archive/04/04-10.py",
                                         "_fallback_strategy", "AgentWithFallback"),
                         self.definition(self.base / "printed/04-10.py", "_fallback_strategy"))

    def test_actual_printed_http_logic_matches_archive(self):
        self.assertEqual(self.definition(self.base / "archive/04/04-12.py", "execute",
                                         "MicroserviceToolAdapter"),
                         self.definition(self.base / "printed/04-12.py", "execute"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
