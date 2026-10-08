# Architecture and validation boundaries

The original `core/` modules and notebooks use local callables, in-memory stores,
stub embeddings and event handlers. Their APIs differ from the additional
`core.book_examples` models. Shared terminology does not prove source equivalence
or a deployed distributed architecture.

The deterministic chapter 2–4 support is described in
[its guide](book-examples/chapters-02-04/README.md); the Rust support is described
in [its guide](book-examples/chapter01/README.md). State, error and timeout policies
are exercised locally with explicit doubles. Services, durable brokers and model
quality remain separate integration responsibilities.

## Optional Google Cloud boundary

The [GCP support](../examples/gcp/README-GCP.md) provides a Google Gen AI client
adapter, HTTP reference and Terraform source. Cloud Run hosts the HTTP service;
Pub/Sub describes durable messaging outside the in-process AgentEventBus. Kafka
protocol/partition examples remain Kafka and can use Managed Service for Apache
Kafka when that infrastructure is the chosen target.

Artifact Registry stores an existing container image. Secret Manager has metadata
only; no secret version, runtime consumption or Secret Accessor is configured. Cloud Logging,
Cloud Monitoring and Cloud Trace are the operational destinations; collection,
metrics and tracing each require the relevant application/platform setup.

Cloud Run HTTP requests and a long-running pull subscriber have different
lifetimes. A dead-letter topic also needs its forwarding service-agent IAM and
inspection subscription. Neither local event loops nor Terraform JSON demonstrate
that those external contracts have been exercised.

## Why Terraform JSON here

The Google Cloud provider offers a declarative representation of resources and
IAM. JSON keeps the reference inspectable with the existing local toolchain.
Syntax/static checks do not replace Terraform provider validation and a reviewed
cloud plan. Credentials, secret contents and remote state are outside the source.

Sources: [Google Gen AI SDK](https://googleapis.github.io/python-genai/),
[Terraform on Google Cloud](https://docs.cloud.google.com/docs/terraform/terraform-overview),
[Pub/Sub delivery](https://docs.cloud.google.com/pubsub/docs/subscription-overview),
[Cloud Run CPU and billing](https://docs.cloud.google.com/run/docs/configuring/billing-settings).
