"""Complete in-memory routing with synthetic inputs; no transport or service."""
import asyncio
from dataclasses import asdict
import json
from core.book_examples.chapter03.topologies import AgentMessage, MeshTopology, RingTopology, StarTopology, TreeTopology

def recorder(node, events):
    async def handle(message):
        events.append({"handler": node, **asdict(message)})
    return handle

async def main():
    output = {"mode": "offline synthetic teaching models"}
    star_events = []
    star = StarTopology("hub")

    async def forward_at_hub(message):
        star_events.append({"handler": "hub", **asdict(message)})
        # The hub owns policy, identity change, and the extra forwarding hop.
        await star.route_message(AgentMessage("hub", message.recipient_id,
                                              message.content, message.hop_count + 1))

    star.register_agent("hub", forward_at_hub)
    star.register_agent("worker", recorder("worker", star_events))
    star.connect("hub", "requester")
    star.connect("hub", "worker")
    await star.route_message(AgentMessage("requester", "worker", "star request"))
    output["star"] = star_events

    mesh_events = []
    mesh = MeshTopology()
    for node in ("a", "b", "c"):
        mesh.register_agent(node, recorder(node, mesh_events))
    mesh.fully_connect()
    await mesh.route_message(AgentMessage("a", "c", "direct mesh request"))
    output["mesh"] = mesh_events

    for direction in ("clockwise", "counterclockwise"):
        ring_events = []
        ring = RingTopology(["a", "b", "c", "d"])
        for node in ring.ring_order:
            ring.register_agent(node, recorder(node, ring_events))
        await ring.route_message(AgentMessage("a", "c", "ring request"), direction)
        output[f"ring_{direction}"] = ring_events

    tree_events = []
    tree = TreeTopology("root")
    for parent, child in (("root", "left"), ("root", "right"),
                          ("left", "a"), ("right", "b")):
        tree.connect(parent, child)
    for node in tree.nodes:
        tree.register_agent(node, recorder(node, tree_events))
    await tree.route_message(AgentMessage("a", "b", "cross-branch tree request"))
    output["tree"] = tree_events
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
