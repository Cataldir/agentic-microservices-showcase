from collections import deque
from dataclasses import asdict
import unittest

from core.book_examples.chapter03.topologies import (
    AgentMessage, MeshTopology, RingTopology, StarTopology, TreeTopology,
)
from tests.book_examples.helpers23 import branching_tree, printed_tree_class, recording_handler


def shortest_path(connections, source, target):
    """Independent BFS oracle for a valid tree; does not duplicate LCA code."""
    pending = deque([(source, [source])])
    visited = {source}
    while pending:
        node, path = pending.popleft()
        if node == target:
            return path
        for neighbor in sorted(connections[node]):
            if neighbor not in visited:
                visited.add(neighbor)
                pending.append((neighbor, path + [neighbor]))
    raise AssertionError("Test tree unexpectedly disconnected")


class StarTests(unittest.IsolatedAsyncioTestCase):
    async def test_leaf_message_reaches_hub_with_destination_and_one_hop(self):
        events = []
        star = StarTopology("hub")
        for node in ("hub", "a", "b"):
            star.register_agent(node, recording_handler(node, events))
        star.connect("hub", "a")
        star.connect("b", "hub")
        payload = {"question": "tradeoffs"}
        message = AgentMessage("a", "b", payload)
        await star.route_message(message)
        self.assertEqual(events, [("hub", {
            "sender_id": "a", "recipient_id": "b", "content": payload, "hop_count": 1})])
        self.assertEqual(message.hop_count, 0)
        self.assertEqual(star.get_neighbors("a"), {"hub"})
        self.assertEqual(star.get_neighbors("hub"), {"a", "b"})

    async def test_hub_handler_explicitly_forwards_once_to_destination(self):
        events = []
        star = StarTopology("hub")

        async def forwarding_hub(message):
            events.append(("hub", asdict(message)))
            # sender_id=hub is essential: preserving the leaf sender would send it back to hub.
            forwarded = AgentMessage("hub", message.recipient_id,
                                     message.content, message.hop_count + 1)
            await star.route_message(forwarded)

        star.register_agent("hub", forwarding_hub)
        star.register_agent("b", recording_handler("b", events))
        star.connect("hub", "a")
        star.connect("hub", "b")
        await star.route_message(AgentMessage("a", "b", "payload"))
        self.assertEqual([x[0] for x in events], ["hub", "b"])
        self.assertEqual([x[1]["hop_count"] for x in events], [1, 2])
        self.assertEqual(events[-1][1]["sender_id"], "hub")
        self.assertEqual(events[-1][1]["content"], "payload")

    async def test_hub_sends_directly_without_automatic_hop_increment(self):
        events = []
        star = StarTopology("hub")
        star.register_agent("b", recording_handler("b", events))
        await star.route_message(AgentMessage("hub", "b", "payload", 7))
        self.assertEqual(events[0][1]["hop_count"], 7)

    async def test_connect_without_hub_is_rejected(self):
        with self.assertRaises(ValueError):
            StarTopology("hub").connect("a", "b")

    async def test_missing_hub_and_unknown_direct_destination_are_silent(self):
        star = StarTopology("hub")
        events = []
        star.register_agent("b", recording_handler("b", events))
        await star.route_message(AgentMessage("a", "b", "payload"))
        await star.route_message(AgentMessage("hub", "unknown", "payload"))
        self.assertEqual(events, [])

    async def test_hub_handler_error_propagates(self):
        failure = RuntimeError("hub rejected message")
        star = StarTopology("hub")
        star.register_agent("hub", recording_handler("hub", [], failure))
        with self.assertRaises(RuntimeError) as caught:
            await star.route_message(AgentMessage("a", "b", "payload"))
        self.assertIs(caught.exception, failure)


class MeshTests(unittest.IsolatedAsyncioTestCase):
    async def test_fully_connect_forms_symmetric_graph_without_self_edges(self):
        mesh = MeshTopology()
        nodes = {"a", "b", "c", "d"}
        for node in nodes:
            mesh.register_agent(node, recording_handler(node, []))
        mesh.fully_connect()
        for node in nodes:
            self.assertEqual(mesh.get_neighbors(node), nodes - {node})

    async def test_direct_delivery_preserves_message_and_original_hop_counter(self):
        mesh = MeshTopology()
        seen = []

        async def destination(message):
            seen.append(message)

        mesh.register_agent("b", destination)
        message = AgentMessage("a", "b", {"value": 42}, 5)
        await mesh.route_message(message)
        self.assertEqual(seen, [message])
        self.assertIs(seen[0], message)
        self.assertEqual(message.hop_count, 5)
        # Existing implementation routes via agents, not the connections graph.
        self.assertEqual(mesh.get_neighbors("b"), set())

    async def test_unknown_destination_is_silently_dropped(self):
        mesh = MeshTopology()
        await mesh.route_message(AgentMessage("a", "unknown", "payload"))

    async def test_destination_handler_error_propagates(self):
        failure = RuntimeError("mesh handler failed")
        mesh = MeshTopology()
        mesh.register_agent("b", recording_handler("b", [], failure))
        with self.assertRaises(RuntimeError) as caught:
            await mesh.route_message(AgentMessage("a", "b", "payload"))
        self.assertIs(caught.exception, failure)


class RingTests(unittest.IsolatedAsyncioTestCase):
    def make_ring(self):
        events = []
        ring = RingTopology(["a", "b", "c", "d"])
        for node in ring.ring_order:
            ring.register_agent(node, recording_handler(node, events))
        return ring, events

    async def test_clockwise_visits_intermediates_and_delivers_in_order(self):
        ring, events = self.make_ring()
        message = AgentMessage("a", "d", "payload")
        await ring.route_message(message, "clockwise")
        self.assertEqual([x[0] for x in events], ["b", "c", "d"])
        self.assertEqual([x[1]["hop_count"] for x in events], [1, 2, 3])
        self.assertEqual(message.hop_count, 3)
        self.assertEqual(ring.get_neighbors("a"), {"b", "d"})

    async def test_counterclockwise_visits_reverse_order(self):
        ring, events = self.make_ring()
        await ring.route_message(AgentMessage("a", "b", "payload"), "counterclockwise")
        self.assertEqual([x[0] for x in events], ["d", "c", "b"])
        self.assertEqual([x[1]["hop_count"] for x in events], [1, 2, 3])

    async def test_missing_destination_stops_after_one_full_ring(self):
        ring, events = self.make_ring()
        message = AgentMessage("a", "unknown", "payload")
        await ring.route_message(message)
        self.assertEqual([x[0] for x in events], ["b", "c", "d", "a"])
        self.assertEqual(message.hop_count, len(ring.ring_order))

    async def test_existing_hop_counter_consumes_the_original_total_bound(self):
        ring, events = self.make_ring()
        message = AgentMessage("a", "d", "payload", 2)
        await ring.route_message(message)
        self.assertEqual([x[0] for x in events], ["b", "c"])
        self.assertEqual(message.hop_count, 4)

    async def test_exhausted_hop_budget_invokes_no_handler(self):
        ring, events = self.make_ring()
        await ring.route_message(AgentMessage("a", "b", "payload", 4))
        self.assertEqual(events, [])

    async def test_same_sender_recipient_requires_full_circle_in_original_contract(self):
        ring, events = self.make_ring()
        await ring.route_message(AgentMessage("a", "a", "payload"))
        self.assertEqual([x[0] for x in events], ["b", "c", "d", "a"])

    async def test_ring_order_controls_connections(self):
        with self.assertRaises(NotImplementedError):
            RingTopology(["a", "b"]).connect("a", "b")

    async def test_unknown_sender_raises_value_error(self):
        ring, _ = self.make_ring()
        with self.assertRaises(ValueError):
            await ring.route_message(AgentMessage("unknown", "b", "payload"))

    async def test_unregistered_recipient_raises_key_error_at_delivery(self):
        ring = RingTopology(["a", "b"])
        with self.assertRaises(KeyError):
            await ring.route_message(AgentMessage("a", "b", "payload"))

    async def test_intermediate_handler_failure_stops_routing(self):
        ring, events = self.make_ring()
        failure = RuntimeError("ring observer failed")
        ring.register_agent("b", recording_handler("b", events, failure))
        with self.assertRaises(RuntimeError) as caught:
            await ring.route_message(AgentMessage("a", "d", "payload"))
        self.assertIs(caught.exception, failure)
        self.assertEqual([x[0] for x in events], ["b"])


class TreeTests(unittest.IsolatedAsyncioTestCase):
    async def test_lca_path_matches_independent_shortest_path_for_all_branch_pairs(self):
        tree = TreeTopology("n0")
        for index in range(1, 31):
            tree.connect(f"n{(index - 1) // 2}", f"n{index}")
        for source in tree.nodes:
            for target in tree.nodes:
                with self.subTest(source=source, target=target):
                    self.assertEqual(tree._find_path(source, target),
                                     shortest_path(tree.connections, source, target))

    async def test_route_visits_lca_and_intermediate_handlers_once(self):
        tree = branching_tree()
        events = []
        for node in tree.nodes:
            tree.register_agent(node, recording_handler(node, events))
        message = AgentMessage("a", "c", {"payload": "x"})
        await tree.route_message(message)
        self.assertEqual([x[0] for x in events], ["left", "root", "right", "c"])
        self.assertEqual([x[1]["hop_count"] for x in events], [1, 2, 3, 4])
        self.assertTrue(all(x[1]["sender_id"] == "a" for x in events))
        self.assertTrue(all(x[1]["recipient_id"] == "c" for x in events))
        self.assertEqual(message.hop_count, 4)

    async def test_unregistered_intermediates_are_skipped_but_hops_are_counted(self):
        tree = branching_tree()
        events = []
        tree.register_agent("c", recording_handler("c", events))
        await tree.route_message(AgentMessage("a", "c", "payload"))
        self.assertEqual([x[0] for x in events], ["c"])
        self.assertEqual(events[0][1]["hop_count"], 4)

    async def test_unknown_parent_is_rejected(self):
        with self.assertRaises(ValueError):
            TreeTopology("root").connect("missing", "child")

    async def test_unknown_path_node_raises_key_error(self):
        tree = branching_tree()
        with self.assertRaises(KeyError):
            tree._find_path("a", "missing")

    async def test_unregistered_destination_raises_key_error(self):
        tree = branching_tree()
        with self.assertRaises(KeyError):
            await tree.route_message(AgentMessage("a", "c", "payload"))

    async def test_intermediate_failure_propagates_and_aborts_later_handlers(self):
        tree = branching_tree()
        events = []
        failure = RuntimeError("tree observer rejected message")
        for node in tree.nodes:
            tree.register_agent(node, recording_handler(node, events,
                                                       failure if node == "root" else None))
        with self.assertRaises(RuntimeError) as caught:
            await tree.route_message(AgentMessage("a", "c", "payload"))
        self.assertIs(caught.exception, failure)
        self.assertEqual([x[0] for x in events], ["left", "root"])

    async def test_same_node_path_does_not_invoke_sender_handler(self):
        tree = branching_tree()
        events = []
        tree.register_agent("a", recording_handler("a", events))
        await tree.route_message(AgentMessage("a", "a", "payload"))
        self.assertEqual(events, [])


class PrintedTreeParityTests(unittest.IsolatedAsyncioTestCase):
    async def test_printed_lca_matches_full_model_and_bfs_for_961_node_pairs(self):
        full = TreeTopology("n0")
        printed = printed_tree_class()("n0")
        for index in range(1, 31):
            for tree in (full, printed):
                tree.connect(f"n{(index - 1) // 2}", f"n{index}")
        for source in full.nodes:
            for target in full.nodes:
                with self.subTest(source=source, target=target):
                    expected = shortest_path(full.connections, source, target)
                    self.assertEqual(full._find_path(source, target), expected)
                    self.assertEqual(printed._find_path(source, target), expected)

    async def test_printed_route_matches_callback_order_content_and_hops_for_49_pairs(self):
        for source in branching_tree().nodes:
            for target in branching_tree().nodes:
                with self.subTest(source=source, target=target):
                    observations = []
                    for cls in (TreeTopology, printed_tree_class()):
                        tree = branching_tree(cls)
                        events = []
                        for node in tree.nodes:
                            tree.register_agent(node, recording_handler(node, events))
                        message = AgentMessage(source, target, {"value": 42}, 3)
                        await tree.route_message(message)
                        expected_path = shortest_path(tree.connections, source, target)[1:]
                        self.assertEqual([x[0] for x in events], expected_path)
                        self.assertEqual([x[1]["hop_count"] for x in events],
                                         list(range(4, 4 + len(expected_path))))
                        observations.append((events, asdict(message)))
                    self.assertEqual(observations[0], observations[1])

    async def test_printed_route_matches_propagated_errors_and_stopping_point(self):
        observations = []
        for cls in (TreeTopology, printed_tree_class()):
            tree = branching_tree(cls)
            events = []
            failure = RuntimeError("observer failure")
            tree.register_agent("left", recording_handler("left", events, failure))
            with self.assertRaises(RuntimeError) as caught:
                await tree.route_message(AgentMessage("a", "c", "payload"))
            self.assertIs(caught.exception, failure)
            observations.append(events)
        self.assertEqual(observations[0], observations[1])
