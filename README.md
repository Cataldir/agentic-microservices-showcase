# Agentic Microservices Showcase

> Companion repository for the book **"Agentic Microservices"** — demonstrating every concept, pattern, and architecture from all 8 chapters through runnable Python notebooks and Azure infrastructure.

## Book Structure → This Repository

| Chapter | Topic | Notebook |
|---------|-------|----------|
| 1 | Microservices Architecture | [Chapter 01](notebooks/chapter-01-microservices-architecture/) |
| 2 | Agentic AI Foundations | [Chapter 02](notebooks/chapter-02-agentic-foundations/) |
| 3 | Scalable Architectures with AI | [Chapter 03](notebooks/chapter-03-scalable-architectures/) |
| 4 | Agent Integration Patterns | [Chapter 04](notebooks/chapter-04-agent-integration/) |
| 5 | Synchronous Agents & MCP | [Chapter 05](notebooks/chapter-05-synchronous-mcp/) |
| 6 | Asynchronous Agentic Microservices | [Chapter 06](notebooks/chapter-06-async-messaging/) |
| 7 | Domain Segregation & Context Mapping | [Chapter 07](notebooks/chapter-07-domain-segregation/) |
| 8 | CI/CD, IaC & Production Architecture | [Chapter 08](notebooks/chapter-08-cicd-production/) |

## Repository Structure

```
agentic-microservices-showcase/
├── core/                    # Shared Python package used by all notebooks
│   ├── agents/              # Agent base classes (Ch02, Ch04)
│   ├── memory/              # Hot/Warm/Cold memory hierarchy (Ch02)
│   ├── messaging/           # Events, Commands, and event bus (Ch06)
│   ├── topologies/          # Multi-agent topology implementations (Ch03)
│   ├── mcp/                 # Model Context Protocol server (Ch05)
│   ├── context/             # Cognitive Bounded Context (Ch07)
│   ├── evaluation/          # LLM-as-Judge evaluation framework (Ch08)
│   └── patterns/            # Circuit breaker and resilience patterns (Ch01, Ch07)
├── notebooks/               # Chapter-by-chapter Jupyter notebooks
├── infra/                   # Azure Bicep infrastructure as code
└── docs/                    # Architecture docs and concept maps
```

## Quick Start

### Prerequisites
- Python 3.11+
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) (for infrastructure deployment)
- An Azure subscription (optional — all notebooks run locally with mocks)

### Install

```bash
git clone https://github.com/Cataldir/agentic-microservices-showcase
cd agentic-microservices-showcase

# Install all dependencies (including Jupyter)
pip install -e ".[dev]"

# Copy and edit environment variables (only needed for Azure features)
cp .env.example .env

# Launch JupyterLab
jupyter lab
```

### Run a Notebook

Open any chapter notebook from `notebooks/` in JupyterLab and run all cells. Most notebooks work fully offline using the mock implementations in `core/`.

### Deploy Azure Infrastructure (optional)

```bash
cd infra
az login
bash deploy.sh dev  # or: prod
```

## Concepts Demonstrated

### Architectural Patterns
- Monolith → Microservices migration (Strangler Fig)
- Database-per-Service pattern
- Bounded Contexts and Domain-Driven Design (DDD)
- Saga pattern for distributed transactions
- Circuit Breaker, Retry, and Bulkhead patterns
- API Gateway pattern

### Agentic Patterns
- Reflexion pattern (iterative self-correction)
- ReAct (Reasoning + Acting) loop
- Tree-of-Thoughts paradigm
- Hot/Warm/Cold memory hierarchy
- Cognitive Bounded Context
- PEAS framework (Performance, Environment, Actuators, Sensors)

### Communication Protocols
- Model Context Protocol (MCP) — Tools, Resources, Prompts
- Agent-to-Agent (A2A) protocol
- Event-driven messaging (pub/sub, Event Sourcing)
- Causal traceability (correlation_id, causation_id)
- Idempotent message handling and dead-letter queues

### Production Patterns
- Six-stage CI/CD pipeline for non-deterministic agents
- LLM-as-Judge semantic evaluation
- Infrastructure as Code with Azure Bicep
- Progressive deployment (canary, shadow routing)
- SLO management and error budgets
- FinOps and token cost monitoring

## Azure Services Used

| Service | Chapters | Use Case |
|---------|----------|----------|
| Azure OpenAI | Ch02, Ch05, Ch08 | LLM inference for agents |
| Azure Container Apps | Ch03, Ch04, Ch08 | Agent container deployment |
| Azure Service Bus | Ch06 | Async message broker (at-least-once) |
| Azure Event Hubs | Ch03, Ch06 | High-throughput event streaming |
| Azure Key Vault | Ch08 | Secrets management |
| Azure Application Insights | Ch08 | Distributed tracing & observability |
| Azure AI Foundry | Ch08 | Agent evaluation and governance |
| Azure Container Registry | Ch08 | Container image storage |

## Architecture Decision Records

Key design decisions documented in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md):
- Every pattern maps to a specific chapter, notebook, and Azure resource
- All notebooks run locally without Azure using stub implementations
- The `core/` package mirrors real production code, not toy examples
- Bicep modules follow the [Azure Well-Architected Framework](https://learn.microsoft.com/en-us/azure/well-architected/)

## License

MIT License — see [LICENSE](LICENSE)

## Book Reference

*Agentic Microservices* — Ricardo Cataldi  
All chapter code examples in this repo are validated against the book's canonical implementations.
