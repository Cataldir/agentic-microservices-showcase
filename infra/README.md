# Google Cloud infrastructure proposal

The executable reference is [examples/gcp/terraform](../examples/gcp/terraform/),
with its inputs and limits in [README-GCP.md](../examples/gcp/README-GCP.md).

It describes an authenticated Cloud Run HTTP service, Artifact Registry,
Secret Manager metadata and Pub/Sub pull/DLQ resources with separate identities.
Provide an existing image to enable the HTTP runtime. Secret Manager has metadata
only, without secret versions, runtime references or Secret Accessor. The reference
does not create payloads, model endpoints or quotas, nor deploy a persistent pull worker.

Terraform JSON is a source representation for review. Local checks validate JSON
and declared boundaries; they do not replace provider-backed terraform validate,
plan or a cloud integration test. No Terraform provider was installed and no
resources were created during this editorial work.

The compatibility entry `infra/deploy.sh` prints help by default. Its explicit
validate/plan/apply modes operate on this Terraform directory only when called
by an operator with an already prepared toolchain and credentials. No apply or
destroy is run by the CI configuration supplied here.

This proposal does not expose the HTTP service through allUsers. The runtime,
deployer and Google-managed service agents have different roles; review the IAM
bindings and Pub/Sub dead-letter forwarding requirements before any deployment.

References: [Terraform on Google Cloud](https://docs.cloud.google.com/docs/terraform/terraform-overview),
[Cloud Run deployment](https://docs.cloud.google.com/run/docs/deploying),
[Pub/Sub dead-letter topics](https://docs.cloud.google.com/pubsub/docs/dead-letter-topics).
