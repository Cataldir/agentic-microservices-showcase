@asynccontextmanager
async def transaction(self):
    transaction_id = str(uuid.uuid4())
    self._pending_effects = []
    try:
        yield transaction_id
        await self._commit()
    except Exception:
        await self._rollback()
        raise

async def _rollback(self) -> None:
    for effect in reversed(self._pending_effects):
        if effect.reversible and effect.compensation:
            try:
                await effect.compensation()
            except Exception as e:
                print(
                    f"Falha ao compensar "
                    f"{effect.effect_id}: "
                    f"{e}")
        elif not effect.reversible:
            print(
                f"AVISO: Efeito irreversível: "
                f"{effect.description}")
    self._pending_effects = []
