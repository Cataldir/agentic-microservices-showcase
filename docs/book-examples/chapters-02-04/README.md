# Exemplos de código — capítulos 2 a 4

Cada linha da tabela aponta para uma fonte completa em `archive/`, um recorte
em `printed/` e um módulo importável em `core.book_examples`. Os testes usam
portas determinísticas para executar o mecanismo completo e os métodos dos
recortes com seus auxiliares. Um recorte isolado pode omitir imports, tipos ou
métodos necessários à execução.

| Código | Mecanismo | Fonte completa | Recorte | Módulo importável |
| --- | --- | --- | --- | --- |
| 02-01 | Reflexion limitado por nota e tentativas | [fonte](archive/02/02-01.py) | [recorte](printed/02-01.py) | [reflexion.py](../../../core/book_examples/chapter02/reflexion.py) |
| 03-05 | estrela, malha, anel e caminho em árvore | [fonte](archive/03/03-05.py) | [recorte](printed/03-05.py) | [topologies.py](../../../core/book_examples/chapter03/topologies.py) |
| 04-02 | contexto e histórico por agente | [fonte](archive/04/04-02.py) | [recorte](printed/04-02.py) | [context.py](../../../core/book_examples/chapter04/context.py) |
| 04-04 | descoberta por capacidades e filtros | [fonte](archive/04/04-04.py) | [recorte](printed/04-04.py) | [registry.py](../../../core/book_examples/chapter04/registry.py) |
| 04-06 | passos sequenciais e compensação | [fonte](archive/04/04-06.py) | [recorte](printed/04-06.py) | [orchestration.py](../../../core/book_examples/chapter04/orchestration.py) |
| 04-07 | efeitos pendentes e memória local | [fonte](archive/04/04-07.py) | [recorte](printed/04-07.py) | [transactions.py](../../../core/book_examples/chapter04/transactions.py) |
| 04-08 | breaker com timeout, qualidade e métricas | [fonte](archive/04/04-08.py) | [recorte](printed/04-08.py) | [breaker.py](../../../core/book_examples/chapter04/breaker.py) |
| 04-09 | heurísticas e composição de avaliações | [fonte](archive/04/04-09.py) | [recorte](printed/04-09.py) | [quality.py](../../../core/book_examples/chapter04/quality.py) |
| 04-10 | primário, cache, secundário e resposta degradada | [fonte](archive/04/04-10.py) | [recorte](printed/04-10.py) | [fallback.py](../../../core/book_examples/chapter04/fallback.py) |
| 04-12 | catálogo com schema, cache e cliente injetado | [fonte](archive/04/04-12.py) | [recorte](printed/04-12.py) | [http_adapter.py](../../../core/book_examples/chapter04/http_adapter.py) |

## Executar localmente

Com Python 3.11 ou posterior e NumPy já disponíveis, execute na raiz do
repositório:

```sh
python -m core.book_examples.verify
python -m core.book_examples.chapter02.demo
python -m core.book_examples.chapter03.demo
```

Para executar a suíte diretamente e ver os nomes dos testes:

```sh
python -m unittest discover -s tests/book_examples -t . -v
```

Esses comandos não instalam pacotes nem usam credenciais ou serviços externos.
Os testes exercitam entradas, saídas, estados, erros e correspondência entre
fontes e recortes. Fixtures locais fornecem LLM, planner, agentes, cache,
cliente HTTP, relógio e embeddings. Não medem a qualidade de um modelo real.

## Montagem e classificação

Contexto, registry, transações, breaker e topologias mantêm os algoritmos das
fontes completas. Reflexion acrescenta validações do construtor. Orquestração,
qualidade e fallback acrescentam imports necessários à montagem dos módulos.
O adapter HTTP exige um cliente e uma exceção de status locais; a fonte com
`httpx.AsyncClient` continua disponível na tabela acima.

- **Executáveis localmente:** módulos importáveis, demos determinísticas e
  testes. O registry usa NumPy com vetores conhecidos, sem baixar embeddings.
- **Dependem de montagem:** recortes, protocolos de LLM/agentes, planner,
  fábrica `_get_agent` e endpoints armazenados no registry. É necessário
  fornecer implementações concretas para conectá-los a serviços.
- **Integrações fora dos testes locais:** LLMs, embeddings e tokenização reais,
  catálogo HTTP, OpenAI/MCP, brokers, segurança de secrets e Google Cloud.

O parser de Reflexion pode interpretar `nan` como nota 1,0. Seu protocolo exige
`generate(prompt)` assíncrono; os demos usam respostas programadas. Topologias
entregam mensagens a handlers locais: as conexões não constituem um transporte
de rede, e a malha entrega ao destinatário sem validar uma aresta. Anel e
árvore dependem da estrutura fornecida pelo chamador.

Consulte os contratos e defeitos relevantes antes de integrar os módulos:

- [Contexto, registry e Saga](README-CONTEXT.md), com
  [testes](../../../tests/book_examples/chapter04/test_context_registry_orchestration.py).
- [Transações e breaker](README-TRANSACTIONS.md), com
  [testes](../../../tests/book_examples/chapter04/test_transactions_breaker.py).
- [Qualidade, fallback e HTTP](README-QUALITY-HTTP.md), com
  [testes](../../../tests/book_examples/chapter04/test_quality_fallback_http.py).
- [Testes de Reflexion](../../../tests/book_examples/chapter02/test_reflexion.py)
  e [testes de topologias](../../../tests/book_examples/chapter03/test_topologies.py).

Os notebooks e APIs anteriores têm contratos próprios. Por exemplo, o
Reflexion anterior recebe três callables e usa `run`; as topologias anteriores
usam fan-out/pipeline; os breakers têm critérios diferentes. Compare as APIs
antes de fazer uma substituição.


O [apoio GCP](../../../examples/gcp/README-GCP.md) contém adaptador, referência
HTTP e infraestrutura adicionais. Seus 45 contratos com clientes falsos e os seis
contratos da ponte assíncrona são separados dos 262 casos deste apoio local. O
novo material não altera as APIs dos módulos ou a correspondência das fontes.
