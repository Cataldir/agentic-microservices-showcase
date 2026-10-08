def _find_path(self, from_id, to_id):
    def ancestors(node):
        path = []
        while node:
            path.append(node)
            node = self.nodes[node].parent
        return path
    source, target = ancestors(from_id), ancestors(to_id)
    source_set = set(source)
    lca = next(node for node in target if node in source_set)
    return (source[:source.index(lca)] + [lca]
            + list(reversed(target[:target.index(lca)])))

async def route_message(self, message: AgentMessage) -> None:
    path = self._find_path(
        message.sender_id, message.recipient_id)
    for node_id in path[1:]:
        message.hop_count += 1
        if node_id == message.recipient_id:
            await self.agents[node_id](message)
            return
        if node_id in self.agents:
            await self.agents[node_id](message)
