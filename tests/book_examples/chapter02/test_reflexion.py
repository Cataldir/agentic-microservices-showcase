import unittest
from dataclasses import asdict

from core.book_examples.chapter02.reflexion import ReflexionAgent
from tests.book_examples.helpers23 import ScriptedLLM, printed_reflexion_class


class ReflexionTests(unittest.IsolatedAsyncioTestCase):
    async def test_threshold_stops_at_first_sufficient_score(self):
        llm = ScriptedLLM("answer", "REFLEXÃO: completa\nSCORE: 0.8")
        agent = ReflexionAgent(llm, quality_threshold=0.8, max_iterations=3)
        result = await agent.solve("task")
        self.assertEqual((result.response, result.reflection, result.quality_score),
                         ("answer", "completa", 0.8))
        self.assertEqual(result.iteration, 1)
        self.assertTrue(result.is_final)
        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(agent.history, [result])

    async def test_feedback_reaches_next_real_generation_prompt(self):
        llm = ScriptedLLM("incomplete", "REFLEXÃO: add missing detail\nSCORE: 0.3",
                          "improved", "REFLEXÃO: fixed\nSCORE: 0.9")
        agent = ReflexionAgent(llm)
        result = await agent.solve("explain tradeoffs")
        self.assertEqual(result.response, "improved")
        self.assertEqual([item.is_final for item in agent.history], [False, True])
        self.assertIn("Tarefa: explain tradeoffs", llm.prompts[2])
        self.assertIn("incomplete", llm.prompts[2])
        self.assertIn("add missing detail", llm.prompts[2])
        self.assertIn("MELHORADA", llm.prompts[2])
        self.assertIn("improved", llm.prompts[3])

    async def test_max_iterations_terminates_below_threshold(self):
        llm = ScriptedLLM(*[item for n in range(3)
                            for item in (f"answer {n}", "SCORE: 0.1")])
        agent = ReflexionAgent(llm, max_iterations=3)
        result = await agent.solve("hard task")
        self.assertEqual(result.iteration, 3)
        self.assertEqual(result.quality_score, 0.1)
        self.assertTrue(result.is_final)
        self.assertEqual([x.iteration for x in agent.history], [1, 2, 3])
        self.assertEqual([x.is_final for x in agent.history], [False, False, True])
        self.assertEqual(len(llm.prompts), 6)

    async def test_a_new_task_clears_previous_history(self):
        llm = ScriptedLLM("first answer", "SCORE: 1.0", "second answer", "SCORE: 1.0")
        agent = ReflexionAgent(llm)
        first = await agent.solve("first task")
        second = await agent.solve("second task")
        self.assertEqual(agent.history, [second])
        self.assertNotIn(first, agent.history)
        self.assertEqual(second.iteration, 1)
        self.assertIn("second task", llm.prompts[2])
        self.assertNotIn("first answer", llm.prompts[2])

    async def test_missing_score_has_conservative_fallback(self):
        agent = ReflexionAgent(ScriptedLLM("REFLEXÃO: needs revision"))
        self.assertEqual(await agent._reflect("task", "answer"), ("needs revision", 0.5))

    async def test_malformed_score_keeps_fallback(self):
        agent = ReflexionAgent(ScriptedLLM("REFLEXÃO: details\nSCORE: unavailable"))
        self.assertEqual(await agent._reflect("task", "answer"), ("details", 0.5))

    async def test_finite_scores_are_clamped_and_boundary_is_preserved(self):
        for textual, expected in (("-4.0", 0.0), ("4.0", 1.0), ("0.8", 0.8)):
            with self.subTest(score=textual):
                agent = ReflexionAgent(ScriptedLLM(f"SCORE: {textual}"))
                _, score = await agent._reflect("task", "answer")
                self.assertEqual(score, expected)

    async def test_parser_requires_exact_line_prefixes(self):
        agent = ReflexionAgent(ScriptedLLM(" REFLEXÃO: ignored\n score: 0.99"))
        self.assertEqual(await agent._reflect("task", "answer"), ("", 0.5))

    async def test_nonfinite_nan_is_a_documented_original_parser_limitation(self):
        # Characterization, not an assertion that this score is meaningful.
        agent = ReflexionAgent(ScriptedLLM("SCORE: nan"))
        self.assertEqual((await agent._reflect("task", "answer"))[1], 1.0)

    async def test_generation_error_propagates_without_history_entry(self):
        failure = RuntimeError("provider unavailable")
        llm = ScriptedLLM(failure)
        agent = ReflexionAgent(llm)
        with self.assertRaises(RuntimeError) as caught:
            await agent.solve("task")
        self.assertIs(caught.exception, failure)
        self.assertEqual(agent.history, [])
        self.assertEqual(len(llm.prompts), 1)

    async def test_reflection_error_propagates_without_history_entry(self):
        failure = TimeoutError("reflection timeout")
        llm = ScriptedLLM("answer", failure)
        agent = ReflexionAgent(llm)
        with self.assertRaises(TimeoutError) as caught:
            await agent.solve("task")
        self.assertIs(caught.exception, failure)
        self.assertEqual(agent.history, [])
        self.assertEqual(len(llm.prompts), 2)

    async def test_later_provider_error_preserves_only_completed_iterations(self):
        failure = RuntimeError("second generation failed")
        agent = ReflexionAgent(ScriptedLLM("partial", "SCORE: 0.2", failure))
        with self.assertRaises(RuntimeError):
            await agent.solve("task")
        self.assertEqual(len(agent.history), 1)
        self.assertEqual(agent.history[0].response, "partial")
        self.assertFalse(agent.history[0].is_final)

    async def test_support_variant_rejects_invalid_iteration_limit(self):
        for value in (0, -1, 1.5, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ReflexionAgent(ScriptedLLM(), max_iterations=value)

    async def test_support_variant_rejects_invalid_threshold(self):
        for value in (-0.1, 1.1, float("inf"), float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ReflexionAgent(ScriptedLLM(), quality_threshold=value)


class PrintedReflexionParityTests(unittest.IsolatedAsyncioTestCase):
    async def test_printed_loop_matches_full_results_history_and_prompts(self):
        scenarios = (
            ("threshold", ("answer", "REFLEXÃO: enough\nSCORE: 0.8"), 0.8, 3),
            ("revision", ("first", "REFLEXÃO: improve\nSCORE: 0.1",
                          "second", "REFLEXÃO: fixed\nSCORE: 0.9"), 0.8, 3),
            ("bounded", ("first", "SCORE: 0.1", "second", "SCORE: 0.2"), 0.8, 2),
            ("fallback", ("answer", "REFLEXÃO: absent score"), 0.8, 1),
        )
        printed_cls = printed_reflexion_class()
        for label, replies, threshold, limit in scenarios:
            with self.subTest(scenario=label):
                full_llm, printed_llm = ScriptedLLM(*replies), ScriptedLLM(*replies)
                full = ReflexionAgent(full_llm, threshold, limit)
                printed = printed_cls(printed_llm, threshold, limit)
                actual = await printed.solve(label)
                expected = await full.solve(label)
                self.assertEqual(asdict(actual), asdict(expected))
                self.assertEqual([asdict(x) for x in printed.history],
                                 [asdict(x) for x in full.history])
                self.assertEqual(printed_llm.prompts, full_llm.prompts)

    async def test_printed_loop_matches_error_and_partial_history(self):
        for prefix in ((), ("answer",), ("first", "SCORE: 0.1")):
            with self.subTest(completed_calls=len(prefix)):
                observations = []
                for cls in (ReflexionAgent, printed_reflexion_class()):
                    error = RuntimeError("scripted provider error")
                    llm = ScriptedLLM(*prefix, error)
                    agent = cls(llm)
                    with self.assertRaises(RuntimeError) as caught:
                        await agent.solve("task")
                    self.assertIs(caught.exception, error)
                    observations.append(([asdict(x) for x in agent.history], llm.prompts))
                self.assertEqual(observations[0], observations[1])

    async def test_printed_loop_resets_history_like_full_model(self):
        observations = []
        for cls in (ReflexionAgent, printed_reflexion_class()):
            agent = cls(ScriptedLLM("first", "SCORE: 1", "second", "SCORE: 1"))
            await agent.solve("first task")
            await agent.solve("second task")
            observations.append([asdict(x) for x in agent.history])
        self.assertEqual(observations[0], observations[1])
