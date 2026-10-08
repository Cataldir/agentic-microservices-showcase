# Agentic Microservices Showcase

Local examples for *Agentic Microservices*, with a Google Cloud deployment
proposal kept separate from the deterministic models.

| Chapter | Notebook |
|---|---|
| 1 — Microservices architecture | [Chapter 1](notebooks/chapter-01-microservices-architecture/) |
| 2 — Agent foundations | [Chapter 2](notebooks/chapter-02-agentic-foundations/) |
| 3 — Scalable agent topologies | [Chapter 3](notebooks/chapter-03-scalable-architectures/) |
| 4 — Agent integration | [Chapter 4](notebooks/chapter-04-agent-integration/) |
| 5 — Synchronous MCP mechanisms | [Chapter 5](notebooks/chapter-05-synchronous-mcp/) |
| 6 — Asynchronous messaging | [Chapter 6](notebooks/chapter-06-async-messaging/) |
| 7 — Domain boundaries | [Chapter 7](notebooks/chapter-07-domain-segregation/) |
| 8 — Evaluation and delivery | [Chapter 8](notebooks/chapter-08-cicd-production/) |

## Local models and tests

The [chapters 2–4 guide](docs/book-examples/chapters-02-04/README.md) describes the
complete functional models and their local contracts. With Python 3.11+ and
NumPy already available, run from the repository root:

```sh
python -m core.book_examples.verify
python -m core.book_examples.chapter02.demo
python -m core.book_examples.chapter03.demo
python scripts/validate_notebook_sources.py
python -m unittest discover -s tests/gcp_integration -v
```

The local support suite has 262 Python cases. The [Rust guide](docs/book-examples/chapter01/README.md)
describes three independent local models with ten embedded tests:

```sh
cargo test --offline --locked --manifest-path rust/book_examples/chapter01/Cargo.toml
```

The existing notebooks demonstrate other APIs. They are complementary examples;
they do not replace the contracts of `core.book_examples`. The notebook source
validator checks JSON and Python syntax; it does not execute inference or prove
that every notebook has been run end to end.

The six fake-client bridge cases are separate from the 262 local support cases and
from the 45 contracts in `examples/gcp`. The async bridge keeps the 512-token
example limit and adds no retries. Cancelling its awaiting task does not abort
an SDK request already running in a worker thread; the SDK timeout still applies.

## Google Cloud proposal

[examples/gcp/README-GCP.md](examples/gcp/README-GCP.md) contains the SDK adapter,
HTTP reference, local contract tests and Terraform JSON. Configuration uses a
project, location and model ID chosen by the reader. Credentials use Application
Default Credentials; no API key or credential file belongs in this repository.

| Capability | Google Cloud component | Boundary |
|---|---|---|
| Generative model calls | Google Gen AI SDK, enterprise API | Optional real client; fake-client contracts are local |
| HTTP agent container | Cloud Run | An HTTP service does not by itself run a persistent pull consumer |
| Container images | Artifact Registry | Use an existing image; deployment permissions remain prerequisites |
| Asynchronous events | Pub/Sub | At-least-once delivery by default; application idempotency remains necessary |
| Kafka protocol, partitions and offsets | Managed Service for Apache Kafka | Preserve Kafka semantics when those are the subject of the example |
| Secrets | Secret Manager | Metadata resource only; no secret payload, version or runtime consumption configured |
| Operational visibility | Cloud Logging, Cloud Monitoring, Cloud Trace | Configure instrumentation/exporters separately; local events do not prove cloud tracing |

See [Google Cloud setup](docs/GCP-SETUP.md), [infrastructure scope](infra/README.md)
and [architecture boundaries](docs/ARCHITECTURE.md). Real inference, messaging,
IAM, quotas, billing and deployments have not been exercised in this local
proposal. The SDK and IaC examples are separate from the offline teaching models.

## License

The existing [LICENSE](LICENSE) is preserved. Original source code and printed
code excerpts remain public, with their correspondence and execution limits in
the chapter guides. Manuscript prose, editorial records and diagrams reproduced
in the book are outside this active public tree.


## Original code and provider migration

The [Chapter 1 guide](docs/book-examples/chapter01/README.md) retains the complete
Rust sources and their excerpts; the [Chapters 2–4 guide](docs/book-examples/chapters-02-04/README.md)
retains the Python sources and excerpts. All 45 source/excerpt files are preserved.
An excerpt can require imports, types or helpers from its complete source; the
guides distinguish runnable local models from code that needs assembly.

Seven earlier Bicep sources under `infra/` remain available as legacy provider
examples. [The legacy setup guide](docs/AZURE-SETUP.md) is retained for reference;
the current entry `infra/deploy.sh` targets the GCP Terraform source and does not
implement the earlier provider commands. The legacy resources are not part of
the GCP reference or its local validation. Use [GCP-SETUP.md](docs/GCP-SETUP.md)
for the current optional integration boundary.

The existing GitHub workflow is preserved. Local GCP checks are explicit commands
in the guides; no deployment or cloud inference job is enabled by this change.
