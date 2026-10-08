from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
from contextlib import asynccontextmanager
from enum import Enum
import uuid

class EffectType(Enum):
    DATABASE = "database"
    EXTERNAL_API = "external_api"
    MESSAGE = "message"
    MEMORY = "memory"
    FILE_SYSTEM = "file_system"

@dataclass
class SideEffect:
    """Representa um efeito colateral rastreável."""
    effect_id: str
    effect_type: EffectType
    description: str
    reversible: bool
    compensation: Callable[[], Awaitable[None]] | None = None
    committed: bool = False

class TransactionalAgent:
    """
    Agente com suporte a transações e isolamento de efeitos colaterais.

    Implementa padrão Unit of Work para agrupar efeitos colaterais
    e permitir commit/rollback atômico.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._pending_effects: list[SideEffect] = []
        self._committed_effects: list[SideEffect] = []

    @asynccontextmanager
    async def transaction(self):
        """
        Context manager para execução transacional.

        Uso:
            async with agent.transaction():
                await agent.do_something()
                await agent.do_another_thing()
            # Commit automático se nenhuma exceção

        Se exceção ocorrer, todos os efeitos pendentes são revertidos.
        """
        transaction_id = str(uuid.uuid4())
        self._pending_effects = []

        try:
            yield transaction_id
            await self._commit()
        except Exception:
            await self._rollback()
            raise

    def register_effect(
        self,
        effect_type: EffectType,
        description: str,
        compensation: Callable[[], Awaitable[None]] | None = None
    ) -> str:
        """
        Registra um efeito colateral pendente.

        Chamado por operações do agente antes de executar
        qualquer ação com efeito colateral.
        """
        effect = SideEffect(
            effect_id=str(uuid.uuid4()),
            effect_type=effect_type,
            description=description,
            reversible=compensation is not None,
            compensation=compensation
        )
        self._pending_effects.append(effect)
        return effect.effect_id

    async def _commit(self) -> None:
        """Confirma todos os efeitos pendentes."""
        for effect in self._pending_effects:
            effect.committed = True
            self._committed_effects.append(effect)
        self._pending_effects = []

    async def _rollback(self) -> None:
        """
        Reverte efeitos pendentes em ordem reversa.
        Efeitos irreversíveis são logados mas não bloqueiam rollback.
        """
        for effect in reversed(self._pending_effects):
            if effect.reversible and effect.compensation:
                try:
                    await effect.compensation()
                except Exception as e:
                    # Log mas continua rollback
                    print(f"Falha ao compensar {effect.effect_id}: {e}")
            elif not effect.reversible:
                print(f"AVISO: Efeito irreversível: {effect.description}")

        self._pending_effects = []

class MemoryStore:
    """
    Store de memória com suporte transacional.
    Permite rollback de memórias criadas em transação abortada.
    """

    def __init__(self):
        self._memories: dict[str, Any] = {}
        self._pending_writes: dict[str, Any] = {}
        self._pending_deletes: set[str] = set()

    def write(self, key: str, value: Any, transactional: bool = True) -> None:
        """Escreve memória, opcionalmente de forma transacional."""
        if transactional:
            self._pending_writes[key] = value
        else:
            self._memories[key] = value

    def read(self, key: str) -> Any | None:
        """Lê memória, considerando escritas pendentes."""
        if key in self._pending_deletes:
            return None
        return self._pending_writes.get(key, self._memories.get(key))

    def delete(self, key: str, transactional: bool = True) -> None:
        """Remove memória, opcionalmente de forma transacional."""
        if transactional:
            self._pending_deletes.add(key)
        else:
            self._memories.pop(key, None)

    def commit(self) -> None:
        """Confirma todas as operações pendentes."""
        self._memories.update(self._pending_writes)
        for key in self._pending_deletes:
            self._memories.pop(key, None)
        self._pending_writes = {}
        self._pending_deletes = set()

    def rollback(self) -> None:
        """Descarta todas as operações pendentes."""
        self._pending_writes = {}
        self._pending_deletes = set()
