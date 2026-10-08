# Google Cloud setup — optional integrations

The local Python and Rust models do not require a cloud project, credentials or
SDK installation. Start with the reproduction commands in the repository README.

For a later real integration, use an existing Google Cloud project, permitted
location, available model, service identities and quotas. [Application Default
Credentials](https://docs.cloud.google.com/docs/authentication/provide-credentials-adc)
is the authentication boundary. Local login or workload identity must be arranged
outside the examples; no credential or API key is stored here.

The optional Python requirements are declared by the `gcp` extra and
[requirements-sdk.txt](../examples/gcp/requirements-sdk.txt). The adapter uses
`google-genai==2.29.0`, `enterprise=True` and API version `v1`. Configuration
requires GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION and GOOGLE_GENAI_MODEL. A
model ID is selected outside the source so availability and region constraints
can be checked for the target project.

The [SDK/infrastructure guide](../examples/gcp/README-GCP.md) describes the local
contracts, HTTP reference, Terraform inputs and IAM assumptions. Terraform
defines metadata and service wiring; it does not supply a secret version, model
quota, existing image or a persistent pull worker. Its provider/schema validation
and deployment require a separately prepared environment. No cloud deployment,
paid request or installation was performed to create this proposal.

## Boundaries to review before deployment

- Cloud Run is the HTTP container target. A continuous pull subscriber has a
  different execution lifetime; do not hide it inside the HTTP service.
- Pub/Sub subscription delivery and retry are not Kafka partition offsets or
  provider session/scheduled-delivery APIs. Preserve message identity and apply
  idempotency to business effects.
- Secret Manager is metadata only in this reference. There is no secret version,
  runtime secret reference or Secret Accessor role. An application that consumes
  a secret needs a separately reviewed version, reference and IAM policy.
- Cloud Logging stdout collection does not by itself create custom metrics or
  OpenTelemetry traces. Instrumentation and exporter configuration are separate.

The active examples have no cloud resources to clean up. After a future deployment,
use the project's approved resource lifecycle process and inspect a destroy plan;
there is no automatic deletion command in this guide.
