"""Offline contracts and preserved limitations for listings 04-02/04/06.

The only non-stdlib dependency is the already installed NumPy runtime.
The embedding model, planner and agents below are local dependency ports.
"""
import ast
import contextlib
import hashlib
import io
import math
from tests.book_examples.helpers4 import CHAPTER04, EXAMPLES
import unittest
from unittest import mock
import warnings

import numpy as np

from core.book_examples.chapter04.context import IsolatedAgentContext
from core.book_examples.chapter04.registry import AgentProfile, AgentRegistry
from core.book_examples.chapter04 import context as context_module
from core.book_examples.chapter04 import registry as registry_module
from core.book_examples.chapter04 import orchestration as orchestration_module
from core.book_examples.chapter04.orchestration import (
    AgentOrchestrator, OrchestrationError, OrchestrationStep, TaskStatus,
)



ARCHIVE_HASHES = {
    "04-02": "e94fe260a39877e7b1a43ae291aab99732ec215ea5a86d4b0ff89efb193d8d30",
    "04-04": "a64dc3462fe6c14176c20f7cf28f23edc830accff09b8fdf91d4869931169a8b",
    "04-06": "f094a3c07ad2550569b54586e893de3ddb543863ac27963109f1dbe656693479",
}


class LocalEmbedding:
    """Deterministic encode port; no model files or remote inference."""

    def __init__(self, vector=(1.0, 0.0)):
        self.vector = np.asarray(vector, dtype=float)
        self.calls = []

    def encode(self, text):
        self.calls.append(text)
        return self.vector.copy()


def profile(agent_id, embeddings=((1.0, 0.0),), *, healthy=True, latency=100.0):
    return AgentProfile(
        agent_id=agent_id, name=agent_id, endpoint=f"local://{agent_id}",
        domain="offline", capabilities=[f"capability-{agent_id}"],
        capability_embeddings=np.asarray(embeddings, dtype=float),
        avg_latency_ms=latency, success_rate=0.8,
        token_cost_per_request=10, is_healthy=healthy, metadata={},
    )


class LocalAgent:
    """Records inputs, outputs and semantic undo; optionally injects failures."""

    def __init__(self, result=None, *, events=None, name="agent",
                 execute_error=None, compensate_error=None):
        self.result = {} if result is None else result
        self.events = [] if events is None else events
        self.name = name
        self.execute_error = execute_error
        self.compensate_error = compensate_error
        self.execute_calls = []
        self.compensate_calls = []

    async def execute(self, action, inputs):
        self.events.append(("execute", self.name, action))
        self.execute_calls.append((action, inputs))
        if self.execute_error is not None:
            raise self.execute_error
        return self.result

    async def compensate(self, action, original_inputs):
        self.events.append(("compensate", self.name, action))
        self.compensate_calls.append((action, original_inputs))
        if self.compensate_error is not None:
            raise self.compensate_error


class LocalPlanner(LocalAgent):
    """Supplies complete plans in order, one per execute_task call."""

    def __init__(self, *plans, error=None):
        super().__init__(name="planner", execute_error=error)
        self.plans = list(plans)

    async def execute(self, action, inputs):
        await super().execute(action, inputs)
        return {"steps": self.plans.pop(0)}


class LocalOrchestrator(AgentOrchestrator):
    """Implements only the original _get_agent dependency port in memory."""

    def __init__(self, registry, planner_agent, agents):
        super().__init__(registry, planner_agent)
        self.agents = dict(agents)
        self.lookups = []
        self.statuses_at_lookup = []

    async def _get_agent(self, agent_id):
        self.lookups.append(agent_id)
        if self._execution_history:
            self.statuses_at_lookup.append(self._execution_history[-1].status)
        return self.agents[agent_id]


def step(step_id, agent_id, *, action="run", inputs=None, undo=None):
    return dict(step_id=step_id, agent_id=agent_id, action=action,
                input_mapping={} if inputs is None else inputs,
                compensation_action=undo)


def orchestrator(plans, agents, *, registered=None):
    registry = AgentRegistry(LocalEmbedding())
    for agent_profile in registered or []:
        registry.register(agent_profile)
    planner = LocalPlanner(*plans)
    return LocalOrchestrator(registry, planner, agents), planner


class ArchiveIntegrityTests(unittest.TestCase):
    def test_preserved_archives_match_source_fixtures(self):
        for listing_id, expected in ARCHIVE_HASHES.items():
            with self.subTest(listing=listing_id):
                path = EXAMPLES / "archive" / "04" / f"{listing_id}.py"
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)

    def test_context_and_registry_are_exact_archive_copies(self):
        for module, listing_id in (("context", "04-02"), ("registry", "04-04")):
            with self.subTest(module=module):
                self.assertEqual(
                    (CHAPTER04 / f"{module}.py").read_bytes(),
                    (EXAMPLES / "archive" / "04" / f"{listing_id}.py").read_bytes(),
                )

    def test_orchestration_changes_only_missing_registry_import(self):
        original = ast.parse((EXAMPLES / "archive" / "04" / "04-06.py").read_text(encoding="utf-8"))
        runnable = ast.parse((CHAPTER04 / "orchestration.py").read_text(encoding="utf-8"))
        imports = [node for node in runnable.body
                   if isinstance(node, ast.ImportFrom) and node.module == "registry"]
        self.assertEqual(len(imports), 1)
        self.assertEqual(imports[0].level, 1)
        self.assertEqual([item.name for item in imports[0].names], ["AgentRegistry"])
        runnable.body.remove(imports[0])
        self.assertEqual(ast.dump(original), ast.dump(runnable))


class ContextTests(unittest.TestCase):
    def make_context(self, *, budget=1500, agent_id="researcher"):
        return IsolatedAgentContext(
            agent_id=agent_id, system_prompt="Local prompt", available_tools=["lookup"],
            memory_namespace=f"memory:{agent_id}", token_budget=budget,
            secrets_scope=f"secrets:{agent_id}",
        )

    def test_history_records_identity_role_content(self):
        ctx = self.make_context()
        ctx.add_to_history("user", "Question")
        self.assertEqual(ctx._conversation_history, [
            {"role": "user", "content": "Question", "agent_id": "researcher"},
        ])

    def test_instances_isolate_history_and_working_memory(self):
        first, second = self.make_context(), self.make_context(agent_id="worker")
        first.add_to_history("user", "Secret")
        first._working_memory["private"] = "data"
        self.assertEqual(second._conversation_history, [])
        self.assertEqual(second._working_memory, {})

    def test_llm_context_has_system_prompt_and_only_budget_tail(self):
        ctx = self.make_context(budget=1000)
        for i in range(5):
            ctx.add_to_history("user", str(i))
        ctx._working_memory["private"] = "not-in-context"
        self.assertEqual(ctx.get_context_for_llm(), [
            {"role": "system", "content": "Local prompt"},
            {"role": "user", "content": "3", "agent_id": "researcher"},
            {"role": "user", "content": "4", "agent_id": "researcher"},
        ])

    def test_history_cap_is_twenty_even_with_large_budget(self):
        ctx = self.make_context(budget=100000)
        for i in range(30):
            ctx.add_to_history("user", str(i))
        self.assertEqual(ctx._max_history_items(), 20)
        self.assertEqual(len(ctx.get_context_for_llm()), 21)
        self.assertEqual(ctx.get_context_for_llm()[1]["content"], "10")

    def test_exact_five_hundred_budget_includes_one_history_item(self):
        ctx = self.make_context(budget=500)
        ctx.add_to_history("user", "first")
        ctx.add_to_history("user", "last")
        self.assertEqual([m["content"] for m in ctx.get_context_for_llm()],
                         ["Local prompt", "last"])

    def test_preserved_under_five_hundred_bug_includes_all_history(self):
        for budget in (0, 1, 499):
            with self.subTest(budget=budget):
                ctx = self.make_context(budget=budget)
                for i in range(30):
                    ctx.add_to_history("user", str(i))
                self.assertEqual(ctx._max_history_items(), 0)
                self.assertEqual(len(ctx.get_context_for_llm()), 31)

    def test_empty_history_always_yields_system_prompt(self):
        self.assertEqual(self.make_context(budget=0).get_context_for_llm(),
                         [{"role": "system", "content": "Local prompt"}])

    def test_returned_history_dicts_are_shared_with_internal_state(self):
        ctx = self.make_context()
        ctx.add_to_history("user", "original")
        result = ctx.get_context_for_llm()
        result[1]["content"] = "mutated"
        self.assertEqual(ctx._conversation_history[0]["content"], "mutated")
        result.append({"role": "user", "content": "new"})
        self.assertEqual(len(ctx._conversation_history), 1)


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.embedding = LocalEmbedding()
        self.registry = AgentRegistry(self.embedding)

    def test_cosine_uses_best_capability_and_is_scale_invariant(self):
        score = self.registry._compute_similarity(
            np.array([3.0, 0.0]), np.array([[0.0, 4.0], [8.0, 6.0]]),
        )
        self.assertAlmostEqual(score, 0.8)

    def test_discovery_encodes_text_once_and_orders_descending(self):
        for item in (profile("mid", ((3, 4),)), profile("best"),
                     profile("low", ((0, 1),))):
            self.registry.register(item)
        result = self.registry.discover_by_capability("book task", min_confidence=0.0)
        self.assertEqual(self.embedding.calls, ["book task"])
        self.assertEqual([a.agent_id for a, _ in result], ["best", "mid", "low"])
        self.assertEqual([round(s, 3) for _, s in result], [1.0, 0.6, 0.0])

    def test_threshold_is_inclusive(self):
        self.registry.register(profile("mid", ((3, 4),)))
        self.assertEqual(len(self.registry.discover_by_capability("task", 0.6)), 1)
        self.assertEqual(self.registry.discover_by_capability("task", 0.601), [])

    def test_health_and_latency_filter_before_similarity(self):
        self.registry.register(profile("sick", embeddings=(), healthy=False))
        self.registry.register(profile("slow", embeddings=(), latency=101))
        self.registry.register(profile("edge", latency=100))
        result = self.registry.discover_by_capability("task", max_latency_ms=100)
        self.assertEqual([a.agent_id for a, _ in result], ["edge"])

    def test_no_latency_limit_keeps_slow_agents(self):
        self.registry.register(profile("slow", latency=10000))
        self.assertEqual(len(self.registry.discover_by_capability("task")), 1)

    def test_preserved_zero_latency_limit_disables_filter(self):
        self.registry.register(profile("slow", latency=10000))
        self.assertEqual(len(self.registry.discover_by_capability("task", max_latency_ms=0)), 1)

    def test_confidence_ties_keep_registration_order(self):
        self.registry.register(profile("second-name"))
        self.registry.register(profile("first-name"))
        self.assertEqual([a.agent_id for a, _ in self.registry.discover_by_capability("task")],
                         ["second-name", "first-name"])

    def test_register_replaces_profile_and_deregister_is_idempotent(self):
        original, updated = profile("agent"), profile("agent", latency=200)
        self.registry.register(original)
        self.registry.register(updated)
        self.assertIs(self.registry._agents["agent"], updated)
        self.registry.deregister("agent")
        self.registry.deregister("unknown")
        self.assertEqual(self.registry._agents, {})

    def test_health_updates_control_discovery(self):
        self.registry.register(profile("agent"))
        self.registry.update_health("agent", False)
        self.registry.update_health("missing", True)
        self.assertEqual(self.registry.discover_by_capability("task"), [])
        self.registry.update_health("agent", True)
        self.assertEqual(len(self.registry.discover_by_capability("task")), 1)

    def test_metrics_use_point_one_ema_for_latency_and_success(self):
        item = profile("agent")
        self.registry.register(item)
        self.registry.update_metrics("agent", latency_ms=200, success=True)
        self.assertAlmostEqual(item.avg_latency_ms, 110)
        self.assertAlmostEqual(item.success_rate, 0.82)
        self.registry.update_metrics("agent", latency_ms=50, success=False)
        self.assertAlmostEqual(item.avg_latency_ms, 104)
        self.assertAlmostEqual(item.success_rate, 0.738)
        self.assertEqual(item.token_cost_per_request, 10)

    def test_unknown_metrics_update_is_noop(self):
        self.registry.update_metrics("unknown", 50, False)
        self.assertEqual(self.registry._agents, {})

    def test_zero_norm_task_is_nan_and_excluded_with_warning(self):
        registry = AgentRegistry(LocalEmbedding((0, 0)))
        registry.register(profile("agent"))
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            result = registry.discover_by_capability("task", min_confidence=-1)
        self.assertEqual(result, [])
        self.assertTrue(any(issubclass(w.category, RuntimeWarning) for w in captured))

    def test_single_zero_norm_capability_is_nan(self):
        with np.errstate(divide="ignore", invalid="ignore"):
            self.assertTrue(math.isnan(self.registry._compute_similarity(
                np.array([1.0, 0.0]), np.array([[0.0, 0.0]]))))

    def test_zero_capability_row_poisoning_valid_row_is_preserved(self):
        self.registry.register(profile("agent", ((1, 0), (0, 0))))
        with np.errstate(divide="ignore", invalid="ignore"):
            self.assertEqual(self.registry.discover_by_capability("task"), [])

    def test_empty_capability_matrix_fails(self):
        with self.assertRaises(ValueError):
            self.registry._compute_similarity(np.array([1.0, 0.0]), np.empty((0, 2)))

    def test_mismatched_embedding_dimensions_fail(self):
        with self.assertRaises(ValueError):
            self.registry._compute_similarity(np.array([1.0, 0.0]), np.array([[1.0, 0.0, 0.0]]))


class OrchestrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_plan_receives_task_context_and_only_healthy_capabilities(self):
        ctx = {"budget": 100, "max_latency_ms": 5}
        instance, planner = orchestrator([[]], {}, registered=[
            profile("healthy-but-slow", latency=10000), profile("sick", healthy=False),
        ])
        result = await instance.execute_task("write book", ctx)
        self.assertEqual(planner.execute_calls, [("create_plan", {
            "task": "write book", "context": ctx,
            "available_agents": [{"id": "healthy-but-slow",
                                  "capabilities": ["capability-healthy-but-slow"]}],
        })])
        self.assertIs(planner.execute_calls[0][1]["context"], ctx)
        # QoS context is forwarded unchanged, but profiles omit latency/cost/success.
        self.assertEqual(set(planner.execute_calls[0][1]["available_agents"][0]),
                         {"id", "capabilities"})
        self.assertEqual(result, {"success": True, "steps": {}, "execution_trace": []})

    async def test_sequential_execution_resolves_previous_result_and_literals(self):
        first, second = LocalAgent({"id": 7}), LocalAgent({"message": "ok"})
        instance, _ = orchestrator([[step("a", "writer", inputs={"text": "literal"}),
                                    step("b", "sender", inputs={"ref": "$a.id"})]],
                                  {"writer": first, "sender": second})
        result = await instance.execute_task("task", {})
        self.assertEqual(first.execute_calls, [("run", {"text": "literal"})])
        self.assertEqual(second.execute_calls, [("run", {"ref": 7})])
        self.assertEqual(instance.statuses_at_lookup, [TaskStatus.IN_PROGRESS] * 2)
        self.assertEqual(result, {"success": True, "steps": {
            "a": {"id": 7}, "b": {"message": "ok"}}, "execution_trace": [
            {"step": "a", "agent": "writer", "status": "completed"},
            {"step": "b", "agent": "sender", "status": "completed"},
        ]})

    async def test_failure_sets_status_error_cause_and_stops_later_steps(self):
        events = []
        error = RuntimeError("provider failed")
        failing = LocalAgent(execute_error=error, events=events, name="failing")
        later = LocalAgent(events=events, name="later")
        instance, _ = orchestrator([[step("bad", "failing"), step("later", "later")]],
                                  {"failing": failing, "later": later})
        with self.assertRaisesRegex(OrchestrationError, "Falha no passo bad: provider failed") as caught:
            await instance.execute_task("task", {})
        self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(len(instance._execution_history), 1)
        self.assertEqual(instance._execution_history[0].status, TaskStatus.FAILED)
        self.assertEqual(instance._execution_history[0].error, "provider failed")
        self.assertIsNone(instance._execution_history[0].result)
        self.assertEqual(later.execute_calls, [])

    async def test_compensation_is_reverse_best_effort_and_uses_outputs(self):
        events = []
        a = LocalAgent({"receipt": "a"}, events=events, name="a")
        b = LocalAgent({"receipt": "b"}, events=events, name="b",
                       compensate_error=RuntimeError("undo b failed"))
        bad = LocalAgent(events=events, name="bad", execute_error=ValueError("run failed"))
        instance, _ = orchestrator([[step("a", "a", inputs={"request": "a"}, undo="undo-a"),
                                    step("b", "b", undo="undo-b"), step("bad", "bad")]],
                                  {"a": a, "b": b, "bad": bad})
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(OrchestrationError):
                await instance.execute_task("task", {})
        self.assertEqual(events[-2:], [("compensate", "b", "undo-b"),
                                     ("compensate", "a", "undo-a")])
        self.assertEqual(a.compensate_calls, [("undo-a", {"receipt": "a"})])
        self.assertEqual(b.compensate_calls, [("undo-b", {"receipt": "b"})])
        self.assertEqual([s.status for s in instance._execution_history],
                         [TaskStatus.COMPENSATED, TaskStatus.COMPLETED, TaskStatus.FAILED])
        self.assertIn("Falha na compensação de b: undo b failed", output.getvalue())

    async def test_completed_step_without_undo_and_failed_step_are_not_compensated(self):
        complete = LocalAgent({"id": 1})
        bad = LocalAgent(execute_error=RuntimeError("bad"))
        instance, _ = orchestrator([[step("done", "done"), step("bad", "bad", undo="undo")]],
                                  {"done": complete, "bad": bad})
        with self.assertRaises(OrchestrationError):
            await instance.execute_task("task", {})
        self.assertEqual(complete.compensate_calls, [])
        self.assertEqual(bad.compensate_calls, [])
        self.assertEqual([s.status for s in instance._execution_history],
                         [TaskStatus.COMPLETED, TaskStatus.FAILED])

    async def test_missing_agent_is_wrapped_failure(self):
        instance, _ = orchestrator([[step("missing", "unknown")]], {})
        with self.assertRaises(OrchestrationError) as caught:
            await instance.execute_task("task", {})
        self.assertIsInstance(caught.exception.__cause__, KeyError)
        self.assertEqual(instance._execution_history[0].status, TaskStatus.FAILED)

    async def test_original_agent_factory_port_stays_unimplemented(self):
        instance = AgentOrchestrator(AgentRegistry(LocalEmbedding()), LocalPlanner([]))
        with self.assertRaises(NotImplementedError):
            await instance._get_agent("any")

    async def test_missing_input_reference_fails_before_agent_lookup(self):
        worker = LocalAgent()
        instance, _ = orchestrator([[step("bad", "worker", inputs={"id": "$missing.id"})]],
                                  {"worker": worker})
        with self.assertRaises(OrchestrationError) as caught:
            await instance.execute_task("task", {})
        self.assertIsInstance(caught.exception.__cause__, KeyError)
        self.assertEqual(instance.lookups, [])
        self.assertEqual(worker.execute_calls, [])
        self.assertEqual(instance._execution_history[0].status, TaskStatus.FAILED)

    async def test_malformed_or_nested_references_and_nonstring_literals_fail(self):
        instance, _ = orchestrator([[]], {})
        for reference, exception in (("$step", ValueError), ("$step.a.b", ValueError),
                                     (9, AttributeError)):
            with self.subTest(reference=reference):
                with self.assertRaises(exception):
                    instance._resolve_inputs({"arg": reference}, {"step": {"a": 1}})

    async def test_planning_error_propagates_without_execution_or_compensation(self):
        error = RuntimeError("planner failed")
        planner = LocalPlanner(error=error)
        instance = LocalOrchestrator(AgentRegistry(LocalEmbedding()), planner, {})
        with self.assertRaises(RuntimeError) as caught:
            await instance.execute_task("task", {})
        self.assertIs(caught.exception, error)
        self.assertEqual(instance._execution_history, [])

    async def test_invalid_plan_data_fails_before_execution(self):
        instance, _ = orchestrator([[{"step_id": "incomplete"}]], {})
        with self.assertRaises(TypeError):
            await instance.execute_task("task", {})
        self.assertEqual(instance._execution_history, [])

    async def test_history_retains_previous_calls_in_trace(self):
        agent = LocalAgent({"id": 1})
        instance, _ = orchestrator([[step("first", "a")], [step("second", "a")]], {"a": agent})
        first = await instance.execute_task("one", {})
        second = await instance.execute_task("two", {})
        self.assertEqual(list(first["steps"]), ["first"])
        self.assertEqual(list(second["steps"]), ["second"])
        self.assertEqual([entry["step"] for entry in second["execution_trace"]], ["first", "second"])

    async def test_failure_in_second_call_can_compensate_previous_call(self):
        prior = LocalAgent({"reservation": 1})
        bad = LocalAgent(execute_error=RuntimeError("second call failed"))
        instance, _ = orchestrator([[step("prior", "a", undo="release")], [step("bad", "b")]],
                                  {"a": prior, "b": bad})
        await instance.execute_task("first task", {})
        with self.assertRaises(OrchestrationError):
            await instance.execute_task("second task", {})
        self.assertEqual(prior.compensate_calls, [("release", {"reservation": 1})])
        self.assertEqual(instance._execution_history[0].status, TaskStatus.COMPENSATED)

    async def test_failed_compensation_keeps_completed_and_can_be_retried(self):
        worker = LocalAgent({"id": 1}, compensate_error=RuntimeError("undo unavailable"))
        bad = LocalAgent(execute_error=RuntimeError("failed"))
        instance, _ = orchestrator([[step("done", "a", undo="undo"), step("bad", "b")]],
                                  {"a": worker, "b": bad})
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(OrchestrationError):
                await instance.execute_task("task", {})
        self.assertEqual(instance._execution_history[0].status, TaskStatus.COMPLETED)
        worker.compensate_error = None
        await instance._compensate_completed_steps()
        self.assertEqual(len(worker.compensate_calls), 2)
        self.assertEqual(instance._execution_history[0].status, TaskStatus.COMPENSATED)

    async def test_plan_may_name_unhealthy_agent_no_execution_health_recheck(self):
        worker = LocalAgent({"ok": True})
        instance, planner = orchestrator([[step("s", "sick")]], {"sick": worker},
                                         registered=[profile("sick", healthy=False)])
        result = await instance.execute_task("task", {})
        self.assertEqual(planner.execute_calls[0][1]["available_agents"], [])
        self.assertTrue(result["steps"]["s"]["ok"])

    async def test_duplicate_step_ids_overwrite_results_but_keep_trace(self):
        first, second = LocalAgent({"value": 1}), LocalAgent({"value": 2})
        instance, _ = orchestrator([[step("same", "a"), step("same", "b")]],
                                  {"a": first, "b": second})
        result = await instance.execute_task("task", {})
        self.assertEqual(result["steps"], {"same": {"value": 2}})
        self.assertEqual(len(result["execution_trace"]), 2)


def load_printed(listing_id, original_module):
    namespace = dict(vars(original_module))
    path = EXAMPLES / "printed" / f"{listing_id}.py"
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    return namespace


PRINTED_CONTEXT = load_printed("04-02", context_module)["IsolatedAgentContext"]
PRINTED_REGISTRY_NAMESPACE = load_printed("04-04", registry_module)
PRINTED_REGISTRY = type("PrintedRegistry", (AgentRegistry,), {
    "discover_by_capability": PRINTED_REGISTRY_NAMESPACE["discover_by_capability"],
    "_compute_similarity": PRINTED_REGISTRY_NAMESPACE["_compute_similarity"],
})
PRINTED_ORCHESTRATOR = type("PrintedOrchestrator", (LocalOrchestrator,), {
    "execute_task": load_printed("04-06", orchestration_module)["execute_task"],
})


class WithoutDocstrings(ast.NodeTransformer):
    """AST comparison ignores only prose and non-executable comments."""

    def visit_ClassDef(self, node):
        self.generic_visit(node)
        self._remove_docstring(node)
        return node

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        self._remove_docstring(node)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    @staticmethod
    def _remove_docstring(node):
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            node.body.pop(0)


def source_node(path, name):
    tree = WithoutDocstrings().visit(ast.parse(path.read_text(encoding="utf-8")))
    return next(node for node in ast.walk(tree)
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == name)


class PrintedAstParityTests(unittest.TestCase):
    def assert_listing_node(self, listing_id, name):
        complete = source_node(EXAMPLES / "archive" / "04" / f"{listing_id}.py", name)
        printed = source_node(EXAMPLES / "printed" / f"{listing_id}.py", name)
        self.assertEqual(ast.dump(complete), ast.dump(printed),
                         f"{listing_id}/{name} changes executable AST or API")

    def test_context_class_matches_archive_ast(self):
        self.assert_listing_node("04-02", "IsolatedAgentContext")

    def test_registry_methods_match_archive_ast(self):
        for method in ("discover_by_capability", "_compute_similarity"):
            with self.subTest(method=method):
                self.assert_listing_node("04-04", method)

    def test_orchestrator_execution_matches_archive_ast(self):
        self.assert_listing_node("04-06", "execute_task")


class PrintedContextTests(ContextTests):
    """Execute all context contracts against the actual printed class."""

    def make_context(self, *, budget=1500, agent_id="researcher"):
        return PRINTED_CONTEXT(
            agent_id=agent_id, system_prompt="Local prompt", available_tools=["lookup"],
            memory_namespace=f"memory:{agent_id}", token_budget=budget,
            secrets_scope=f"secrets:{agent_id}",
        )


class PrintedRegistryTests(RegistryTests):
    """Bind printed methods to the full registry and repeat its contracts."""

    def setUp(self):
        patcher = mock.patch(f"{__name__}.AgentRegistry", PRINTED_REGISTRY)
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()


class PrintedOrchestrationTests(OrchestrationTests):
    """Bind the printed cycle to original helpers and repeat Saga contracts."""

    def setUp(self):
        patcher = mock.patch(f"{__name__}.LocalOrchestrator", PRINTED_ORCHESTRATOR)
        patcher.start()
        self.addCleanup(patcher.stop)


if __name__ == "__main__":
    unittest.main()
