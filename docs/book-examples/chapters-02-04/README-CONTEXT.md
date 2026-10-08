# Contexto, registry e Saga — capítulo 4

Os módulos abaixo permitem explorar histórico por agente, descoberta por
capacidades e execução sequencial com compensação. Para o registry, o ambiente
precisa ter NumPy disponível. Os testes fornecem embeddings, planner e agentes
locais; não fazem descoberta remota nem chamadas de rede.

| Código | Fonte completa | Recorte | Módulo |
| --- | --- | --- | --- |
| 04-02 | [contexto](archive/04/04-02.py) | [classe](printed/04-02.py) | [context.py](../../../core/book_examples/chapter04/context.py) |
| 04-04 | [registry](archive/04/04-04.py) | [descoberta](printed/04-04.py) | [registry.py](../../../core/book_examples/chapter04/registry.py) |
| 04-06 | [orquestração](archive/04/04-06.py) | [execute_task](printed/04-06.py) | [orchestration.py](../../../core/book_examples/chapter04/orchestration.py) |

## Executar e fornecer dependências

Na raiz do repositório, com Python 3.11+ e NumPy:

```sh
python -m unittest tests.book_examples.chapter04.test_context_registry_orchestration -v
```

O [arquivo de testes](../../../tests/book_examples/chapter04/test_context_registry_orchestration.py)
contém exemplos de montagem: `LocalEmbedding.encode` produz vetores conhecidos;
`LocalPlanner.execute` devolve planos programados; `LocalAgent` registra a
execução e a compensação; `LocalOrchestrator._get_agent` consulta um dicionário
de instâncias. Cada componente pode receber falhas controladas.

Para usar o módulo de orquestração, forneça planner e registry e implemente
`_get_agent` numa subclasse. A classe base lança `NotImplementedError` nessa
porta. O módulo acrescenta o import de `AgentRegistry`, ausente na fonte 04-06;
essa fonte isolada pode falhar ao avaliar a anotação do construtor.

## Entradas, saídas e limites

**Contexto.** Armazena prompt do sistema e mensagens identificadas por papel,
conteúdo e identidade. O orçamento divide `token_budget` por 500 e limita o
histórico a 20 itens, sem contar tokens reais. Entre 0 e 499, o slice `[-0:]`
inclui todo o histórico. Os dicionários retornados compartilham referências
internas. `available_tools`, `memory_namespace` e `secrets_scope` são metadados;
a dataclass não aplica autorização ou isolamento de recursos.

**Registry.** Classifica pelo maior cosseno entre as capacidades e o vetor da
tarefa; aceita o limiar de confiança na igualdade e filtra saúde e latência.
Os vetores precisam ter dimensões compatíveis e norma não nula. O código não
valida isso: norma zero gera NaN, uma linha nula pode contaminar o máximo,
e matriz vazia ou dimensão incompatível gera `ValueError`.
`max_latency_ms=0` desativa o filtro. Custo e taxa de sucesso são armazenados,
mas não participam da classificação.

**Plano.** O planner recebe tarefa, contexto e IDs/capacidades dos agentes
saudáveis. O catálogo enviado não contém custo, latência ou taxa de sucesso.
A execução não revalida saúde ou QoS nem verifica dependências e IDs duplicados.
O mapping aceita literais textuais e referências `$passo.campo` a um campo
imediato de um resultado anterior. Campo inexistente gera `KeyError`; referências
malformadas geram `ValueError`; literais não textuais geram `AttributeError`.

**Execução e compensação.** Uma falha no ciclo marca o passo como `FAILED`,
interrompe os seguintes e é encapsulada em `OrchestrationError`, preservando
sua causa. Erros do planner ou da construção do plano propagam antes desse
ciclo. A compensação percorre passos concluídos em ordem reversa e recebe
`step.result`. Um undo falho não impede os outros, mas mantém o passo como
`COMPLETED`. Não há persistência, retry automático ou idempotência.

**Reutilização.** A instância reinicia resultados por chamada, mas acumula
`_execution_history`. Uma falha posterior pode compensar passos de tarefas
anteriores. Evite compartilhar essa instância entre tarefas independentes
sem tratar esse comportamento. IDs duplicados sobrescrevem resultados,
embora continuem como entradas distintas no trace.

Os testes executam também os métodos dos recortes com auxiliares completos.
Esse vínculo permite testar o mecanismo; não transforma cada recorte em um
programa independente. Serviços de embeddings, planner real, resolução de
endpoints, transporte, tokenização e controle de secrets precisam de adapters
e testes de integração próprios.
