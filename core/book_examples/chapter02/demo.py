"""Run complete local models; all inputs are synthetic and no service is contacted."""

import asyncio
from dataclasses import asdict
import json

from core.book_examples.chapter02.doubles import ScriptedLLM
from core.book_examples.chapter02.reflexion import ReflexionAgent


def recorder(node, events):
    async def handle(message):
        events.append({"handler": node, **asdict(message)})
    return handle


async def main():
    llm = ScriptedLLM("first answer", "REFLEXÃO: add an example\nSCORE: 0.4",
                      "answer with example", "REFLEXÃO: complete\nSCORE: 0.9")
    reflexion = ReflexionAgent(llm)
    await reflexion.solve("Explain the routing tradeoff")
    output = {"mode": "offline synthetic teaching models",
              "reflexion": [asdict(item) for item in reflexion.history]}

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
