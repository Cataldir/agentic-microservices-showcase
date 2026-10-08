"""An explicitly synthetic LLM boundary for offline teaching and tests."""


class ScriptedLLM:
    """Records prompts and yields responses/errors without a provider or network."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    async def generate(self, prompt):
        self.prompts.append(prompt)
        if not self.replies:
            raise AssertionError("The agent requested an unexpected LLM call")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
