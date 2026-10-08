"""Offline behavioral tests for the unmodified book listings 04-07 and 04-08.

Tests named ``limitation`` characterize existing behavior; they do not endorse it.
Run from the repository root with unittest discovery as documented in the example guide.
"""
import ast
import asyncio
import copy
import contextlib
import hashlib
import io
from tests.book_examples.helpers4 import CHAPTER04, EXAMPLES
import threading
import unittest
from unittest.mock import patch

from core.book_examples.chapter04 import breaker
from core.book_examples.chapter04 import transactions


FOLDER = CHAPTER04


def load_printed_methods(filename, complete_module):
    """Execute the actual excerpt in the complete module's dependency namespace."""
    namespace = dict(vars(complete_module))
    source = EXAMPLES / "printed" / filename
    exec(compile(source.read_text(encoding="utf-8"), str(source), "exec"), namespace)
    return namespace


PRINTED_TRANSACTIONS = load_printed_methods("04-07.py", transactions)
PRINTED_BREAKER = load_printed_methods("04-08.py", breaker)


class PrintedTransactionalAgent(transactions.TransactionalAgent):
    transaction = PRINTED_TRANSACTIONS["transaction"]
    _rollback = PRINTED_TRANSACTIONS["_rollback"]


class PrintedAgentCircuitBreaker(breaker.AgentCircuitBreaker):
    call = PRINTED_BREAKER["call"]


class EditorialAstNormalizer(ast.NodeTransformer):
    """Remove prose/types and a precisely checked redundant exception handler.

    This does not erase executable statements. Handler merging is valid only
    when both handlers have identical bodies, their aliases are unused, and the
    first handler catches subclasses already caught by the final Exception.
    """

    def visit_AsyncFunctionDef(self, node):
        self.generic_visit(node)
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            node.body.pop(0)
        node.returns = None
        return node

    def visit_arg(self, node):
        node.annotation = None
        return node

    def visit_ExceptHandler(self, node):
        self.generic_visit(node)
        if node.name and not any(isinstance(child, ast.Name) and child.id == node.name
                                 for statement in node.body for child in ast.walk(statement)):
            node.name = None
        return node

    def visit_Try(self, node):
        self.generic_visit(node)
        if len(node.handlers) == 2:
            narrow, broad = node.handlers
            expected_types = ast.parse("(asyncio.TimeoutError, QualityBelowThresholdError)",
                                       mode="eval").body
            if (ast.dump(narrow.type) == ast.dump(expected_types)
                    and isinstance(broad.type, ast.Name) and broad.type.id == "Exception"
                    and narrow.name is None and broad.name is None
                    and ast.dump(ast.Module(body=narrow.body, type_ignores=[]))
                    == ast.dump(ast.Module(body=broad.body, type_ignores=[]))):
                # Confirm the hierarchy on the Python runtime used for execution.
                assert issubclass(asyncio.TimeoutError, Exception)
                assert issubclass(breaker.QualityBelowThresholdError, Exception)
                node.handlers = [broad]
        return node


def normalized_method_ast(path, method_name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    methods = [node for node in ast.walk(tree)
               if isinstance(node, ast.AsyncFunctionDef) and node.name == method_name]
    if len(methods) != 1:
        raise AssertionError(f"Expected exactly one {method_name} method in {path}")
    normalized = EditorialAstNormalizer().visit(copy.deepcopy(methods[0]))
    return ast.dump(normalized, include_attributes=False)


class FakeClock:
    """Replaces breaker.time, leaving asyncio's own clock untouched."""

    def __init__(self, now=100.0):
        self.now = now

    def time(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class SourcePreservationTests(unittest.TestCase):
    def test_complete_modules_are_identical_to_archived_sources(self):
        folder = CHAPTER04
        for filename, archive in (("transactions.py", "04-07.py"),
                                  ("breaker.py", "04-08.py")):
            with self.subTest(module=filename):
                actual = (folder / filename).read_bytes()
                original = (EXAMPLES / "archive" / "04" / archive).read_bytes()
                self.assertEqual(hashlib.sha256(actual).digest(),
                                 hashlib.sha256(original).digest())
                self.assertEqual(actual, original)

    def test_transaction_printed_methods_have_normalized_ast_parity(self):
        for method in ("transaction", "_rollback"):
            with self.subTest(method=method):
                self.assertEqual(normalized_method_ast(FOLDER / "transactions.py", method),
                                 normalized_method_ast(EXAMPLES / "printed" / "04-07.py", method))

    def test_breaker_printed_call_has_normalized_ast_parity(self):
        self.assertEqual(normalized_method_ast(FOLDER / "breaker.py", "call"),
                         normalized_method_ast(EXAMPLES / "printed" / "04-08.py", "call"))

    def test_printed_methods_are_bound_instead_of_inherited_from_complete_classes(self):
        self.assertIs(PrintedTransactionalAgent.__dict__["transaction"],
                      PRINTED_TRANSACTIONS["transaction"])
        self.assertIs(PrintedTransactionalAgent.__dict__["_rollback"],
                      PRINTED_TRANSACTIONS["_rollback"])
        self.assertIsNot(PrintedTransactionalAgent.__dict__["transaction"],
                         transactions.TransactionalAgent.__dict__["transaction"])
        self.assertIs(PrintedAgentCircuitBreaker.__dict__["call"], PRINTED_BREAKER["call"])
        self.assertIsNot(PrintedAgentCircuitBreaker.__dict__["call"],
                         breaker.AgentCircuitBreaker.__dict__["call"])


class TransactionTests(unittest.IsolatedAsyncioTestCase):
    agent_class = transactions.TransactionalAgent

    def setUp(self):
        self.agent = self.agent_class("offline-test")

    async def test_success_marks_all_effects_committed_without_compensation(self):
        compensated = []

        async def compensate():
            compensated.append("unexpected")

        async with self.agent.transaction() as transaction_id:
            self.assertTrue(transaction_id)
            first = self.agent.register_effect(transactions.EffectType.DATABASE,
                                               "write", compensate)
            second = self.agent.register_effect(transactions.EffectType.MESSAGE,
                                                "publish")
            self.assertFalse(any(e.committed for e in self.agent._pending_effects))
        self.assertEqual(compensated, [])
        self.assertEqual(self.agent._pending_effects, [])
        self.assertEqual([e.effect_id for e in self.agent._committed_effects],
                         [first, second])
        self.assertTrue(all(e.committed for e in self.agent._committed_effects))

    async def test_rollback_compensates_in_reverse_order_and_reraises_original(self):
        compensated = []

        def compensation(label):
            async def run():
                compensated.append(label)
            return run

        original = RuntimeError("operation failed")
        with self.assertRaises(RuntimeError) as raised:
            async with self.agent.transaction():
                for label in ("first", "second", "third"):
                    self.agent.register_effect(transactions.EffectType.EXTERNAL_API,
                                               label, compensation(label))
                raise original
        self.assertIs(raised.exception, original)
        self.assertEqual(compensated, ["third", "second", "first"])
        self.assertEqual(self.agent._pending_effects, [])
        self.assertEqual(self.agent._committed_effects, [])

    async def test_irreversible_warning_and_failed_compensation_do_not_stop_rollback(self):
        compensated = []

        async def good():
            compensated.append("good")

        async def bad():
            compensated.append("bad")
            raise ValueError("compensation unavailable")

        output = io.StringIO()
        original = RuntimeError("original failure")
        with contextlib.redirect_stdout(output), self.assertRaises(RuntimeError) as raised:
            async with self.agent.transaction():
                self.agent.register_effect(transactions.EffectType.DATABASE, "good", good)
                self.agent.register_effect(transactions.EffectType.EXTERNAL_API, "bad", bad)
                self.agent.register_effect(transactions.EffectType.MESSAGE, "already sent")
                raise original
        self.assertIs(raised.exception, original)
        self.assertEqual(compensated, ["bad", "good"])
        self.assertIn("AVISO: Efeito irreversível: already sent", output.getvalue())
        self.assertIn("Falha ao compensar", output.getvalue())
        self.assertIn("compensation unavailable", output.getvalue())
        self.assertEqual(self.agent._pending_effects, [])

    async def test_prior_committed_effects_survive_later_rollback(self):
        async with self.agent.transaction():
            first = self.agent.register_effect(transactions.EffectType.FILE_SYSTEM,
                                               "first committed")
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
            async with self.agent.transaction():
                self.agent.register_effect(transactions.EffectType.MESSAGE, "second failed")
                raise ValueError("abort second")
        self.assertEqual([e.effect_id for e in self.agent._committed_effects], [first])

    async def test_limitation_nested_transaction_replaces_outer_pending_effects(self):
        async with self.agent.transaction():
            outer = self.agent.register_effect(transactions.EffectType.DATABASE, "outer")
            async with self.agent.transaction():
                inner = self.agent.register_effect(transactions.EffectType.DATABASE, "inner")
        self.assertEqual([e.effect_id for e in self.agent._committed_effects], [inner])
        self.assertNotIn(outer, [e.effect_id for e in self.agent._committed_effects])

    async def test_limitation_concurrent_transaction_loses_first_pending_effect(self):
        first_started = asyncio.Event()
        second_committed = asyncio.Event()
        ids = {}

        async def first():
            async with self.agent.transaction():
                ids["first"] = self.agent.register_effect(transactions.EffectType.MEMORY,
                                                         "first")
                first_started.set()
                await second_committed.wait()

        async def second():
            await first_started.wait()
            async with self.agent.transaction():
                ids["second"] = self.agent.register_effect(transactions.EffectType.MEMORY,
                                                          "second")
            second_committed.set()

        await asyncio.wait_for(asyncio.gather(first(), second()), 1)
        self.assertEqual([e.effect_id for e in self.agent._committed_effects], [ids["second"]])

    async def test_limitation_cancellation_does_not_rollback_pending_effects(self):
        entered = asyncio.Event()
        release = asyncio.Event()
        compensated = []

        async def compensate():
            compensated.append(True)

        async def operation():
            async with self.agent.transaction():
                self.agent.register_effect(transactions.EffectType.DATABASE,
                                           "cancelled", compensate)
                entered.set()
                await release.wait()

        task = asyncio.create_task(operation())
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(compensated, [])
        self.assertEqual(len(self.agent._pending_effects), 1)

    async def test_limitation_transaction_does_not_commit_or_rollback_memory_store(self):
        store = transactions.MemoryStore()
        async with self.agent.transaction():
            store.write("kept", "pending")
        self.assertEqual(store._memories, {})
        self.assertEqual(store._pending_writes, {"kept": "pending"})
        with self.assertRaises(RuntimeError):
            async with self.agent.transaction():
                store.write("aborted", "also pending")
                raise RuntimeError("abort")
        self.assertEqual(store.read("aborted"), "also pending")
        self.assertEqual(store._memories, {})


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = transactions.MemoryStore()

    def test_pending_write_is_readable_but_not_persisted_until_commit(self):
        self.store.write("key", {"value": 1})
        self.assertEqual(self.store.read("key"), {"value": 1})
        self.assertNotIn("key", self.store._memories)
        self.store.commit()
        self.assertEqual(self.store._memories, {"key": {"value": 1}})
        self.assertEqual(self.store._pending_writes, {})
        self.assertEqual(self.store._pending_deletes, set())

    def test_rollback_restores_previous_write_and_discards_new_write(self):
        self.store.write("existing", "before", transactional=False)
        self.store.write("existing", "after")
        self.store.write("new", "pending")
        self.assertEqual(self.store.read("existing"), "after")
        self.store.rollback()
        self.assertEqual(self.store.read("existing"), "before")
        self.assertIsNone(self.store.read("new"))
        self.assertEqual(self.store._pending_writes, {})
        self.assertEqual(self.store._pending_deletes, set())

    def test_pending_delete_hides_existing_value_until_commit(self):
        self.store.write("existing", "value", transactional=False)
        self.store.delete("existing")
        self.assertIsNone(self.store.read("existing"))
        self.assertEqual(self.store._memories["existing"], "value")
        self.store.commit()
        self.assertNotIn("existing", self.store._memories)

    def test_delete_rollback_restores_committed_value(self):
        self.store.write("existing", "value", transactional=False)
        self.store.delete("existing")
        self.store.rollback()
        self.assertEqual(self.store.read("existing"), "value")

    def test_immediate_write_and_delete_survive_pending_rollback(self):
        self.store.write("one", 1, transactional=False)
        self.store.write("two", 2, transactional=False)
        self.store.write("pending", 3)
        self.store.delete("one", transactional=False)
        self.store.rollback()
        self.assertIsNone(self.store.read("one"))
        self.assertEqual(self.store.read("two"), 2)
        self.assertIsNone(self.store.read("pending"))

    def test_limitation_delete_wins_even_when_write_is_registered_later(self):
        self.store.write("key", "before", transactional=False)
        self.store.delete("key")
        self.store.write("key", "later write")
        self.assertIsNone(self.store.read("key"))
        self.store.commit()
        self.assertIsNone(self.store.read("key"))
        self.assertEqual(self.store._pending_writes, {})
        self.assertEqual(self.store._pending_deletes, set())


class BreakerTests(unittest.IsolatedAsyncioTestCase):
    breaker_class = breaker.AgentCircuitBreaker

    def setUp(self):
        self.clock = FakeClock()
        self.clock_patch = patch.object(breaker, "time", self.clock)
        self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)
        self.circuit = self.breaker_class(
            "offline-test", breaker.CircuitBreakerConfig(
                failure_threshold=2, recovery_timeout_seconds=5,
                success_threshold=2, timeout_seconds=1))

    async def fail(self):
        raise RuntimeError("technical failure")

    async def succeed(self, value="ok"):
        return value

    async def open_circuit(self):
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                await self.circuit.call(self.fail)
        self.assertEqual(self.circuit.state, breaker.CircuitState.OPEN)

    async def test_sync_and_async_calls_forward_arguments_and_return_results(self):
        def sync(a, *, b):
            return a + b

        async def async_func(a, *, b):
            return a * b

        self.assertEqual(await self.circuit.call(sync, 2, b=3), 5)
        self.assertEqual(await self.circuit.call(async_func, 2, b=3), 6)
        self.assertEqual(self.circuit.metrics.total_calls, 2)
        self.assertEqual(self.circuit.metrics.successful_calls, 2)
        self.assertEqual(self.circuit.metrics.failed_calls, 0)

    async def test_threshold_is_consecutive_and_success_resets_failures(self):
        with self.assertRaises(RuntimeError):
            await self.circuit.call(self.fail)
        self.assertEqual(self.circuit.state, breaker.CircuitState.CLOSED)
        self.assertEqual(self.circuit.metrics.consecutive_failures, 1)
        await self.circuit.call(self.succeed)
        self.assertEqual(self.circuit.metrics.consecutive_failures, 0)
        await self.open_circuit()
        self.assertEqual(self.circuit.metrics.failed_calls, 3)
        self.assertEqual(self.circuit.metrics.successful_calls, 1)
        self.assertEqual(self.circuit.metrics.consecutive_successes, 0)

    async def test_open_rejects_without_executing_or_counting_as_admitted_call(self):
        await self.open_circuit()
        executed = []

        async def forbidden():
            executed.append(True)

        with self.assertRaisesRegex(breaker.CircuitOpenError, "offline-test is open"):
            await self.circuit.call(forbidden)
        self.assertEqual(executed, [])
        self.assertEqual(self.circuit.metrics.total_calls, 2)
        self.assertEqual(self.circuit.metrics.failed_calls, 2)
        self.assertEqual(self.circuit.metrics.rejected_calls, 1)

    async def test_recovery_boundary_half_open_then_closes_after_success_threshold(self):
        await self.open_circuit()
        self.clock.advance(4.99)
        with self.assertRaises(breaker.CircuitOpenError):
            await self.circuit.call(self.succeed)
        self.clock.advance(0.01)
        self.assertEqual(await self.circuit.call(self.succeed), "ok")
        self.assertEqual(self.circuit.state, breaker.CircuitState.HALF_OPEN)
        self.assertEqual(self.circuit.metrics.consecutive_successes, 1)
        await self.circuit.call(self.succeed)
        self.assertEqual(self.circuit.state, breaker.CircuitState.CLOSED)
        self.assertEqual(self.circuit.metrics.consecutive_successes, 0)
        self.assertEqual(self.circuit.metrics.consecutive_failures, 0)
        self.assertEqual(self.circuit.metrics.total_calls, 4)

    async def test_half_open_failure_reopens_and_restarts_recovery_interval(self):
        await self.open_circuit()
        self.clock.advance(5)
        await self.circuit.call(self.succeed)
        self.clock.advance(1)
        with self.assertRaises(RuntimeError):
            await self.circuit.call(self.fail)
        self.assertEqual(self.circuit.state, breaker.CircuitState.OPEN)
        self.assertEqual(self.circuit.metrics.last_failure_time, 106)
        self.assertEqual(self.circuit.metrics.consecutive_successes, 0)
        self.clock.advance(4)
        with self.assertRaises(breaker.CircuitOpenError):
            await self.circuit.call(self.succeed)
        self.clock.advance(1)
        await self.circuit.call(self.succeed)
        self.assertEqual(self.circuit.state, breaker.CircuitState.HALF_OPEN)

    async def test_quality_error_counts_as_failure_and_boundary_quality_is_accepted(self):
        self.circuit.quality_evaluator = lambda result: result["quality"]
        with self.assertRaisesRegex(breaker.QualityBelowThresholdError, "0.69 below"):
            await self.circuit.call(self.succeed, {"quality": 0.69})
        self.assertEqual(self.circuit.metrics.failed_calls, 1)
        self.assertEqual(await self.circuit.call(self.succeed, {"quality": 0.7}),
                         {"quality": 0.7})
        self.assertEqual(self.circuit.metrics.consecutive_failures, 0)

    async def test_quality_evaluator_can_be_disabled(self):
        evaluated = []

        def evaluate(result):
            evaluated.append(result)
            return 0

        self.circuit.quality_evaluator = evaluate
        self.circuit.config.include_quality_in_failure = False
        self.assertEqual(await self.circuit.call(self.succeed), "ok")
        self.assertEqual(evaluated, [])
        self.assertEqual(self.circuit.metrics.successful_calls, 1)

    async def test_evaluator_exception_is_technical_failure_and_original_error_survives(self):
        original = ValueError("evaluator failed")

        def evaluate(result):
            raise original

        self.circuit.quality_evaluator = evaluate
        with self.assertRaises(ValueError) as raised:
            await self.circuit.call(self.succeed)
        self.assertIs(raised.exception, original)
        self.assertEqual(self.circuit.metrics.failed_calls, 1)

    async def test_async_timeout_cancels_operation_and_counts_failure(self):
        self.circuit.config.timeout_seconds = 0.01
        cancelled = asyncio.Event()

        async def stalled():
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        with self.assertRaises(asyncio.TimeoutError):
            await self.circuit.call(stalled)
        self.assertTrue(cancelled.is_set())
        self.assertEqual(self.circuit.metrics.total_calls, 1)
        self.assertEqual(self.circuit.metrics.failed_calls, 1)
        self.assertEqual(self.circuit.metrics.successful_calls, 0)

    async def test_latency_ema_uses_fake_clock_and_only_successful_calls(self):
        async def timed(value, duration):
            self.clock.advance(duration)
            return value

        await self.circuit.call(timed, "first", 0.1)
        self.assertAlmostEqual(self.circuit.metrics.average_latency_ms, 10)
        await self.circuit.call(timed, "second", 0.2)
        self.assertAlmostEqual(self.circuit.metrics.average_latency_ms, 29)

        async def timed_failure():
            self.clock.advance(0.3)
            raise OSError("offline")

        with self.assertRaises(OSError):
            await self.circuit.call(timed_failure)
        self.assertAlmostEqual(self.circuit.metrics.average_latency_ms, 29)
        self.assertAlmostEqual(self.circuit.metrics.last_failure_time, 100.6)
        self.assertEqual(self.circuit.metrics.total_calls, 3)
        self.assertEqual(self.circuit.metrics.successful_calls, 2)
        self.assertEqual(self.circuit.metrics.failed_calls, 1)

    async def test_limitation_half_open_permits_parallel_calls(self):
        await self.open_circuit()
        self.clock.advance(5)
        entered = 0
        both_entered = asyncio.Event()
        release = asyncio.Event()

        async def probe():
            nonlocal entered
            entered += 1
            if entered == 2:
                both_entered.set()
            await release.wait()
            return "probe"

        tasks = [asyncio.create_task(self.circuit.call(probe)) for _ in range(2)]
        try:
            await asyncio.wait_for(both_entered.wait(), 1)
            self.assertEqual(self.circuit.state, breaker.CircuitState.HALF_OPEN)
            self.assertEqual(entered, 2)
        finally:
            release.set()
            results = await asyncio.gather(*tasks)
        self.assertEqual(results, ["probe", "probe"])
        self.assertEqual(self.circuit.state, breaker.CircuitState.CLOSED)

    async def test_limitation_failure_at_zero_timestamp_never_starts_recovery(self):
        self.clock.now = 0.0
        await self.open_circuit()
        self.clock.advance(100)
        with self.assertRaises(breaker.CircuitOpenError):
            await self.circuit.call(self.succeed)
        self.assertEqual(self.circuit.metrics.last_failure_time, 0.0)
        self.assertEqual(self.circuit.state, breaker.CircuitState.OPEN)

    async def test_limitation_sync_timeout_does_not_stop_worker_thread(self):
        self.circuit.config.timeout_seconds = 0.01
        started = threading.Event()
        release = threading.Event()
        completed = threading.Event()

        def blocking():
            started.set()
            release.wait(timeout=2)
            completed.set()
            return "completed after timeout"

        task = asyncio.create_task(self.circuit.call(blocking))
        try:
            self.assertTrue(await asyncio.to_thread(started.wait, 1))
            with self.assertRaises(asyncio.TimeoutError):
                await task
            self.assertFalse(completed.is_set())
            self.assertEqual(self.circuit.metrics.failed_calls, 1)
        finally:
            release.set()
            self.assertTrue(await asyncio.to_thread(completed.wait, 1))
            if not task.done():
                await task
        self.assertEqual(self.circuit.metrics.successful_calls, 0)

    async def test_limitation_cancellation_is_not_counted_as_failure(self):
        entered = asyncio.Event()

        async def pending():
            entered.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(self.circuit.call(pending))
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.circuit.metrics.total_calls, 1)
        self.assertEqual(self.circuit.metrics.failed_calls, 0)
        self.assertEqual(self.circuit.metrics.successful_calls, 0)
        self.assertEqual(self.circuit.state, breaker.CircuitState.CLOSED)


class PrintedTransactionTests(TransactionTests):
    """Run all transaction behavioral paths against the actual printed methods."""
    agent_class = PrintedTransactionalAgent


class PrintedBreakerTests(BreakerTests):
    """Run all breaker paths against printed call, retaining complete helpers."""
    breaker_class = PrintedAgentCircuitBreaker

    def setUp(self):
        super().setUp()
        clock_patch = patch.dict(PRINTED_BREAKER, {"time": self.clock})
        clock_patch.start()
        self.addCleanup(clock_patch.stop)


if __name__ == "__main__":
    unittest.main(verbosity=2)
