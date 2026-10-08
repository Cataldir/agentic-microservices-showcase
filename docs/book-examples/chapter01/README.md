# Apoio do capítulo 1 — Rust e referências complementares

Use este guia para localizar as fontes Rust em `archive/01/`, seus recortes em
`printed/` e os modelos locais de checkout, Saga e retry. As fontes e os
recortes são arquivos de consulta; nem todos constituem programas independentes.

## Executar os modelos locais

Na raiz do repositório, com Cargo e Rust compatíveis com a edição 2024:

```sh
cargo test --offline --locked --manifest-path rust/book_examples/chapter01/Cargo.toml
```

A crate não tem dependências externas. Seus testes exercitam composição de
serviços em memória, compensação e esperas registradas por um duplo local.
Esse comando não compila automaticamente cada arquivo em `archive/` ou
`printed/`, nem faz chamadas HTTP, pagamentos, operações de estoque ou envio
de eventos a um broker.

## Fontes, recortes e modelos

| Código | Fonte completa | Recorte | Modelo ou limite de execução |
| --- | --- | --- | --- |
| 01-04 a 01-07 | [04](archive/01/01-04.rs), [05](archive/01/01-05.rs), [06](archive/01/01-06.rs), [07](archive/01/01-07.rs) | [composição](printed/01-04-07.rs) | [modular.rs](../../../rust/book_examples/chapter01/pilot/modular.rs): users, orders e payments locais |
| 01-13 | [pagamento HTTP](archive/01/01-13.rs) | [recorte](printed/01-13.rs) | requer serde, reqwest, Tokio e um serviço externo |
| 01-14 | [estados do breaker](archive/01/01-14.rs) | [recorte](printed/01-14.rs) | compõe o breaker com 01-15 a 01-17 |
| 01-15 | [estado e construtor](archive/01/01-15.rs) | [recorte](printed/01-15.rs) | fragmento, depende das demais definições |
| 01-16 | [chamada e admissão](archive/01/01-16.rs) | [recorte](printed/01-16.rs) | método, depende das demais definições |
| 01-17 | [falhas e recuperação](archive/01/01-17.rs) | [recorte](printed/01-17.rs) | métodos, dependem das demais definições |
| 01-19 | [OrderCreatedEvent](archive/01/01-19.rs) | [recorte](printed/01-19.rs) | definição de dados, usa serde |
| 01-20 | [criação de evento](archive/01/01-20.rs) | [recorte](printed/01-20.rs) | usa chrono e imprime uma mensagem; não envia ao broker |
| 01-21 | [consumidores](archive/01/01-21.rs) | [recorte](printed/01-21.rs) | funções ilustrativas, sem transporte |
| 01-24 | [Saga](archive/01/01-24.rs) | [recorte](printed/01-24.rs) | [saga.rs](../../../rust/book_examples/chapter01/pilot/saga.rs): passos e falhas controladas |
| 01-26 | [retry](archive/01/01-26.rs) | [recorte](printed/01-26.rs) | [retry.rs](../../../rust/book_examples/chapter01/pilot/retry.rs): waiter injetado |

## Contratos dos modelos e limites das fontes

- **Checkout:** o modelo oferece `create/create/process`, IDs fixos e erros
  para nome vazio ou valor inválido. As fontes usam
  `UserService/OrderService/PaymentService`, campos e IDs diferentes. O modelo
  demonstra a composição, sem persistência. O `PaymentStatus` da fonte não
  deriva `Debug`, embora o exemplo use `{:?}`.
- **Saga:** o modelo executa quatro passos e compensa os concluídos em ordem
  reversa. Se uma compensação falhar, interrompe as seguintes e devolve seu
  erro. Não há durabilidade nem transação entre serviços externos.
- **Retry:** o modelo troca a espera Tokio por um `Waiter` injetado. Mantém
  cinco tentativas totais, espera inicial de 100 ms, fator 2 e teto de 30 s.
  Não há jitter ou classificação de erros. A política não valida parâmetros:
  zero tentativas configuradas ainda permite a primeira chamada, e um
  multiplicador inválido pode causar panic em `Duration::from_secs_f64`.
- **Executor:** o helper de testes em
  [lib.rs](../../../rust/book_examples/chapter01/pilot/lib.rs) usa polling e
  `Noop Waker`. Destina-se às futures determinísticas desses modelos; não é
  um executor de I/O.
- **Breaker Rust:** a fonte aceita `FnOnce` síncrono e devolve erros `String`.
  O estado half-open não limita sondas concorrentes. `on_success` e
  `on_failure` adquirem estado e contador em ordens opostas, criando risco de
  deadlock em chamadas concomitantes. As fontes exigem montagem e avaliação
  próprias antes de uso numa aplicação.

## Referências complementares do repositório

| Material | Uso e diferença relevante |
| --- | --- |
| [Notebook C1](../../../notebooks/chapter-01-microservices-architecture/01-microservices-architecture.ipynb) | demonstra breaker, recuperação e um Bulkhead local; não implementa checkout, Saga ou retry Rust |
| [Breaker Python](../../../core/patterns/circuit_breaker.py) e [testes](../../../tests/test_circuit_breaker.py) | API awaitable, `asyncio.Lock` e política de recuperação própria; não têm o contrato Rust |
| [Saga Python C4](../chapters-02-04/README-CONTEXT.md) | planner, registry e compensação que continua após erro; política diferente da Saga Rust |
| [Eventos](../../../core/messaging/events.py), [bus](../../../core/messaging/bus.py) e [testes](../../../tests/test_messaging.py) | pub/sub em memória que aguarda handlers; sem fila durável e com retry linear |
| [Infraestrutura Azure](../../../infra/modules/container-apps.bicep) | define ACR e managedEnvironment; esse módulo não cria aplicações individuais, probes, gateway ou Dapr |

O breaker Python exige que a função admitida seja awaitable. Lambdas síncronas
usadas para demonstrar rejeição no notebook não servem como funções de sucesso.
O Bulkhead do notebook limita concorrência global; não fornece quotas por tenant.
Confiança e custo no `AgentCircuitBreaker` Python são valores informados pelo
chamador, sem avaliação automática da resposta. Consulte também o
[guia de arquitetura](../../../docs/ARCHITECTURE.md) para o restante do companion.
