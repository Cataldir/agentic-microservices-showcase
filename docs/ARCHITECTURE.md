# Architecture Guide

This document explains how the showcase repository is structured and how each
architectural concept maps to code, tests, notebooks, and Azure infrastructure.

## Repository Layout

```
agentic-microservices-showcase/
├── core/                        # Reusable Python package
│   ├── agents/                  # Agent base classes, registry, Reflexion
│   ├── memory/                  # Hot / Warm / Cold memory hierarchy
│   ├── messaging/               # Event bus, events, commands, DLQ
│   ├── topologies/              # Star, Mesh, Ring, Tree multi-agent graphs
│   ├── mcp/                     # MCP server (tools, resources, prompts)
│   ├── context/                 # Cognitive Bounded Context (S,T,K,V)
│   ├── evaluation/              # LLM-as-Judge + EvaluationReport
│   └── patterns/                # Circuit breaker, bulkhead
├── notebooks/                   # One folder per chapter — .ipynb demos
├── tests/                       # pytest async suite
├── infra/                       # Azure Bicep IaC
└── docs/                        # Architecture, concepts, setup guides
```

## Concept → Code Mapping

| Chapter | Concept | Core Module | Test File | Notebook | Azure Resource |
|---------|---------|------------|-----------|----------|----------------|
| 1 | Circuit Breaker | `core/patterns/circuit_breaker.py` | `test_circuit_breaker.py` | `ch01` | Container Apps |
| 1 | Bulkhead | `core/patterns/circuit_breaker.py` | `test_circuit_breaker.py` | `ch01` | Container Apps |
| 2 | PEAS Framework | `core/agents/base.py` | — | `ch02` | Azure OpenAI |
| 2 | Memory Hierarchy | `core/memory/hierarchy.py` | `test_memory.py` | `ch02` | Azure OpenAI |
| 2 | Reflexion Agent | `core/agents/reflexion.py` | `test_reflexion.py` | `ch02` | Azure OpenAI |
| 3 | Star Topology | `core/topologies/multi_agent.py` | — | `ch03` | Container Apps |
| 3 | Mesh Topology | `core/topologies/multi_agent.py` | — | `ch03` | Container Apps |
| 3 | Ring Topology | `core/topologies/multi_agent.py` | — | `ch03` | Container Apps |
| 3 | Tree Topology | `core/topologies/multi_agent.py` | — | `ch03` | Container Apps |
| 4 | Well-Defined Agent | `core/agents/base.py` | — | `ch04` | — |
| 4 | Agent Registry | `core/agents/registry.py` | — | `ch04` | — |
| 4 | Anti-Corruption Layer | `core/agents/registry.py` | — | `ch04` | — |
| 5 | MCP Server | `core/mcp/server.py` | — | `ch05` | Container Apps |
| 5 | Tool Definitions | `core/mcp/server.py` | — | `ch05` | Azure OpenAI |
| 5 | Resource Definitions | `core/mcp/server.py` | — | `ch05` | — |
| 5 | Prompt Templates | `core/mcp/server.py` | — | `ch05` | — |
| 6 | Event vs Command | `core/messaging/events.py` | `test_messaging.py` | `ch06` | Service Bus |
| 6 | Agent Event Bus | `core/messaging/bus.py` | `test_messaging.py` | `ch06` | Service Bus |
| 6 | Dead-Letter Queue | `core/messaging/bus.py` | `test_messaging.py` | `ch06` | Service Bus |
| 6 | Causal Tracing | `core/messaging/events.py` | — | `ch06` | App Insights |
| 7 | Cognitive BC (S,T,K,V) | `core/context/bounded_context.py` | — | `ch07` | — |
| 7 | Scope Enforcement | `core/context/bounded_context.py` | — | `ch07` | — |
| 7 | Capability Levels | `core/context/bounded_context.py` | — | `ch07` | — |
| 8 | LLM-as-Judge | `core/evaluation/llm_judge.py` | — | `ch08` | Azure OpenAI |
| 8 | Quality Gate | `core/evaluation/llm_judge.py` | — | `ch08` | — |
| 8 | 6-Stage CI/CD | `.github/workflows/ci.yml` | — | `ch08` | Container Apps |

## Data Flow

```
User Request
    │
    ▼
[Agent Registry] ── semantic discovery ──► [WellDefinedAgent]
                                                │ scope check
                                                ▼
     [CognitiveBoundedContext.is_in_scope()]    ►  REJECT if out-of-domain
                                                │  PROCEED if in-domain
                                                ▼
                                          [BaseAgent.execute()]
                                                │ hot/warm/cold memory
                                                │ tool calls via MCP
                                                ▼
                                          [AgentEventBus.publish()]
                                                │ idempotency gate
                                                │ retries + backoff
                                                ▼
                                    downstream agents / Azure Service Bus
```

## Design Decisions

### Why `asyncio` throughout?
Agent systems are I/O-bound (LLM calls, DB queries, HTTP). Every operation that
may block uses `async/await` to keep the event loop free and support thousands
of concurrent agent invocations on limited hardware.

### Why Protocol over ABC in agent definitions?
Python `Protocol` enables structural subtyping — any class implementing the
correct interface is a valid agent without inheriting from a base class.
This avoids the tight coupling of classical inheritance in agent code.

### Why Bicep over Terraform?
Bicep has first-class ARM support, shorter feedback loops with `bicep build`,
and native VS Code tooling. The repository is Azure-native so Bicep is the
natural choice. Terraform users can use `az bicep decompile` to convert.
