# Transações locais e circuit breaker — capítulo 4

| Código | Fonte completa | Recorte | Módulo |
| --- | --- | --- | --- |
| 04-07 | [transações e memória](archive/04/04-07.py) | [transaction e rollback](printed/04-07.py) | [transactions.py](../../../core/book_examples/chapter04/transactions.py) |
| 04-08 | [breaker](archive/04/04-08.py) | [call](printed/04-08.py) | [breaker.py](../../../core/book_examples/chapter04/breaker.py) |

Os dois módulos funcionam com bibliotecas padrão e operações locais. Na raiz
do repositório, com Python 3.11 ou posterior:

```sh
python -m unittest tests.book_examples.chapter04.test_transactions_breaker -v
```

Os [testes](../../../tests/book_examples/chapter04/test_transactions_breaker.py)
fornecem funções e compensações locais, eventos e um relógio falso para as
transições do breaker. O relógio do event loop continua real; os timeouts usam
limites curtos. Os recortes são carregados com os tipos e auxiliares dos módulos
completos para executar os mesmos contratos.

## 04-07: efeitos e memória

`TransactionalAgent.transaction()` cria um UUID. Dentro do bloco,
`register_effect()` registra tipo, descrição e uma compensação assíncrona
opcional. `_commit()` marca registros como confirmados. Uma exceção derivada
de `Exception` inicia compensações em ordem reversa, continua após falhas de
undo, imprime avisos e relança a exceção original.

Registrar um efeito não executa a operação externa; confirmar registros não
constitui commit entre serviços. A lista pode conter efeitos irreversíveis e
compensações que falham.

`MemoryStore` tem escritas e exclusões pendentes sobre um dicionário. Leituras
veem as escritas pendentes e ocultam as exclusões. `commit()` aplica escritas e
depois exclusões; `rollback()` descarta ambas. Operações com
`transactional=False` são imediatas e sobrevivem ao rollback.

Antes de integrar:

- `MemoryStore` não está ligado ao bloco de `TransactionalAgent`; o chamador
  coordena commit e rollback da memória.
- Uma instância compartilha a lista de efeitos. Transações aninhadas ou
  concomitantes podem perder registros; não há isolamento ou savepoint.
- `asyncio.CancelledError` não entra no `except Exception`; cancelamento deixa
  efeitos pendentes sem compensação.
- Uma exclusão pendente prevalece mesmo sobre uma escrita posterior da mesma
  chave. A memória não representa a sequência temporal por chave.

## 04-08: chamada, estados e erros

`AgentCircuitBreaker.call()` recebe função síncrona ou `async def`, argumentos
e argumentos nomeados. Devolve o resultado, rejeita o estado aberto com
`CircuitOpenError` e propaga falhas técnicas e timeouts. Com avaliação habilitada,
nota abaixo do limiar produz `QualityBelowThresholdError`; igualdade passa.

Falhas consecutivas abrem o circuito no limiar. Um sucesso zera essa sequência.
Após o intervalo desde a última falha, uma chamada admitida inicia `HALF_OPEN`.
Sucessos consecutivos fecham o circuito no limiar de recuperação; nova falha o
reabre e reinicia a espera.

`total_calls` conta chamadas admitidas e `rejected_calls` conta rejeições.
`average_latency_ms` é uma média móvel exponencial dos sucessos, com peso 0,1;
não é a média aritmética de todas as chamadas.

Antes de integrar:

- Half-open admite várias chamadas simultâneas. O lock protege decisões e
  métricas, sem reservar uma única sonda de recuperação.
- Timeout de `asyncio.to_thread()` não interrompe a função síncrona; ela pode
  continuar produzindo efeitos depois que `call()` devolve o timeout.
- Timestamp `0.0` é tratado como ausência de falha e impede a recuperação.
- Cancelamento não incrementa falhas; chamadas admitidas podem superar a soma
  de sucessos e falhas.
- A identificação assíncrona usa `asyncio.iscoroutinefunction()`. Outros
  callables que devolvem coroutine não têm esse contrato garantido. Valores
  de configuração não são validados pelo exemplo.

Os testes incluem esses limites, além de sucesso, erro, compensação, qualidade,
timeout, rejeição e recuperação. São modelos locais: integrar recursos externos
exige definir atomicidade, idempotência, cancelamento e lifecycle próprios.
