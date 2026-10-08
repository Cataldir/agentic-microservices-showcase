"""Small deterministic boundaries; the algorithms under test are the real models."""

from dataclasses import asdict
from pathlib import Path
import runpy

from core.book_examples.chapter02.reflexion import ReflexionAgent, ReflexionResult
from core.book_examples.chapter03.topologies import AgentMessage, TreeTopology
from core.book_examples.chapter02.doubles import ScriptedLLM

REPOSITORY = Path(__file__).resolve().parents[2]
EXAMPLES = REPOSITORY / 'docs' / 'book-examples' / 'chapters-02-04'


def printed_reflexion_class():
    namespace = runpy.run_path(str(EXAMPLES / "printed" / "02-01.py"),
                              init_globals={"ReflexionResult": ReflexionResult})
    return type("PrintedReflexion", (ReflexionAgent,), {"solve": namespace["solve"]})


def printed_tree_class():
    namespace = runpy.run_path(str(EXAMPLES / "printed" / "03-05.py"),
                              init_globals={"AgentMessage": AgentMessage})
    return type("PrintedTree", (TreeTopology,), {
        "_find_path": namespace["_find_path"],
        "route_message": namespace["route_message"],
    })


def recording_handler(agent_id, events, failure=None):
    async def handler(message):
        events.append((agent_id, asdict(message)))
        if failure is not None:
            raise failure
    return handler


def branching_tree(cls=TreeTopology):
    tree = cls("root")
    for parent, child in (("root", "left"), ("root", "right"),
                          ("left", "a"), ("left", "b"),
                          ("right", "c"), ("right", "d")):
        tree.connect(parent, child)
    return tree
