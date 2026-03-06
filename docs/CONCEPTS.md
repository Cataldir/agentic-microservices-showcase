# Concepts Reference

A quick-reference glossary for every pattern and concept demonstrated in this repository.

---

## Resilience Patterns (Chapter 1)

### Circuit Breaker
Three-state finite state machine (CLOSED → OPEN → HALF_OPEN) that stops forwarding
requests to a failing downstream when the error rate exceeds a threshold, giving it
time to recover. Prevents **cascading failures** across agent chains.

**Core class**: `core/patterns/circuit_breaker.py — CircuitBreaker`

### Bulkhead
Limits the number of concurrent requests to a downstream service using a semaphore.
Isolates one failing dependency from consuming all available threads/connections.

**Core class**: `CircuitBreaker` uses `asyncio.Semaphore` internally.

### AgentCircuitBreaker
Extension of circuit breaker for LLM-specific signals: latency SLO, confidence
threshold, and token budget. Opens the circuit on poor LLM quality, not just errors.

---

## Agentic Foundations (Chapter 2)

### PEAS Framework
Agent specification in terms of **P**erformance, **E**nvironment, **A**ctuators, **S**ensors.
A structured way to define the scope and responsibilities of an agent before building it.

### Memory Hierarchy
- **Hot Memory**: In-process FIFO buffer (deque). Instant access, limited capacity. Used for the active conversation window.
- **Warm Memory**: Semantic vector retrieval (cosine similarity). Used for recent context beyond the hot window.
- **Cold Memory**: Persistent key-value store with tag search. Used for long-term knowledge and policies.

### Reflexion
Iterative self-correction loop where the agent critiques its own response and improves
it up to N times, stopping early when quality crosses a threshold. Based on the paper
*"Reflexion: Language Agents with Verbal Reinforcement Learning"* (Shinn et al., 2023).

---

## Multi-Agent Topologies (Chapter 3)

### Star Topology
One hub node receives all requests and fans out to leaf workers in parallel.
Optimal for independent subtasks. Single point of failure is the hub.

### Mesh Topology
Explicit directed edges between nodes. Each node routes only to its declared neighbours.
High resilience; any node can be a router. Used for pipeline-style workflows.

### Ring Topology
Nodes form a directed cycle; work circulates around the ring until a stopping condition
is met. Natural fit for ETL pipelines where each stage transforms the payload.

### Tree Topology
Hierarchical: root → branch managers → leaf workers. Mirrors org chart delegation.
Used for complex work decomposition with specialised sub-agents.

---

## Integration Patterns (Chapter 4)

### Well-Defined Agent
An agent with explicit scope constraints: allowed types of work are declared up front.
Any task outside the allowed set is rejected before an LLM call is made.

### Agent Registry
A service-discovery catalog for agents. Registers agent profiles (name, description,
capabilities) and routes incoming tasks to the best-match agent using semantic similarity.

### Anti-Corruption Layer (ACL)
Translation boundary between two agents from different domains. Converts the
field names and semantics of one domain's data model into the other's, preventing
domain leakage.

---

## Model Context Protocol (Chapter 5)

### MCP Server
A JSON-RPC 2.0 server that exposes tools, resources, and prompts to LLM clients.
Enables agents to call external functions with structured, validated inputs.

### Tool
A callable action with a declared JSON Schema. The LLM selects tools and populates
arguments; MCP validates and dispatches. Analogous to a REST POST endpoint.

### Resource
A data source addressed by URI (e.g., `orders://catalog`). Analogous to a REST GET
endpoint returning typed content (JSON, text, markdown).

### Prompt Template
A parameterized, version-controlled prompt stored on the server. Separates prompt
engineering from agent code; update the template without redeploying the agent.

---

## Async Messaging (Chapter 6)

### Event
An immutable fact describing something that *happened* (past participle: `OrderPlaced`).
Cannot be rejected by consumers. Produced by exactly one domain.

### Command
A request for an agent to perform an action (imperative verb: `ProcessOrder`).
Can be rejected. Has exactly one intended recipient.

### Idempotency Gate
Prevents double-processing by tracking processed `message_id` values. Essential when
a message broker delivers at-least-once.

### Dead-Letter Queue (DLQ)
Messages that exhaust all retry attempts are moved to the DLQ rather than discarded.
Operators can inspect, replay, or alert on DLQ contents.

### EventContext (Causal Tracing)
Carries `trace_id` and `span_id` through an event chain. `new_child()` creates a
child span for each downstream agent, reconstructing the full causal timeline in
Azure Application Insights.

---

## Domain Segregation (Chapter 7)

### Cognitive Bounded Context (S, T, K, V)
Formal 4-tuple defining an agent's domain:
- **S** — Semantic Context (vocabulary + ontology)
- **T** — Tool Permissions (AgentCapabilityLevel)
- **K** — Knowledge Bases (data sources it may access)
- **V** — Value Function (constrained optimization target)

### Scope Enforcement (`is_in_scope`)
Keyword-based check run before every LLM call. If the task does not match the
agent's semantic context, it is rejected or rerouted — preventing domain hallucinations.

### AgentCapabilityLevel
Ordered permission levels: `READ < WRITE < EXECUTE < ORCHESTRATE`.
An agent cannot perform operations above its granted level.

---

## CI/CD for Non-Deterministic Systems (Chapter 8)

### LLM-as-Judge
Using a separate (typically more capable) LLM to evaluate the quality of another
LLM's output across multiple dimensions: relevance, groundedness, coherence, fluency.

### EvaluationReport
Aggregates multiple `EvaluationResult` instances into summary statistics:
`pass_rate`, `avg_quality`, `quality_gate_passed(threshold)`.

### Quality Gate
A CI/CD stage that fails the pipeline if `EvaluationReport.quality_gate_passed()`
returns `False`. Prevents quality regressions from shipping to production even when
all deterministic tests pass.

### The 6-Stage Pipeline
1. Static analysis (ruff + mypy + git-secrets)
2. Unit tests (pytest)
3. LLM evaluation (quality gate)
4. Integration tests (end-to-end agent collaboration)
5. Container build + security scan (trivy)
6. Deployment (staging → production with smoke tests)
