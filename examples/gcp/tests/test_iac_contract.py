"""Verifica JSON e invariantes declarados; não substitui Terraform validate."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOCS = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "terraform").glob("*.tf.json")}
RESOURCES = DOCS["main.tf.json"]["resource"]
VARIABLES = DOCS["variables.tf.json"]["variable"]


class IaCContractTests(unittest.TestCase):
    def test_json_configuration_files_and_pinned_provider(self):
        self.assertEqual(set(DOCS), {"main.tf.json", "variables.tf.json", "versions.tf.json"})
        provider = DOCS["versions.tf.json"]["terraform"]["required_providers"]["google"]
        self.assertEqual(provider, {"source": "hashicorp/google", "version": "= 8.6.0"})

    def test_no_cloud_accounts_activation_credentials_or_secret_payload(self):
        forbidden_resources = {
            "google_project", "google_project_service", "google_project_service_identity",
            "google_service_account_key", "google_secret_manager_secret_version",
        }
        self.assertFalse(forbidden_resources & set(RESOURCES))
        raw = json.dumps(DOCS)
        self.assertNotIn("secret_data", raw)
        self.assertNotIn("credentials_json", raw)

    def test_runtime_disabled_until_image_and_model_are_supplied(self):
        self.assertFalse(VARIABLES["enable_runtime"]["default"])
        self.assertEqual(VARIABLES["container_image"]["default"], "")
        self.assertEqual(VARIABLES["inference_model"]["default"], "")
        service = RESOURCES["google_cloud_run_v2_service"]["http"]
        self.assertEqual(service["count"], "${var.enable_runtime ? 1 : 0}")
        self.assertEqual(len(service["lifecycle"]["precondition"]), 2)
        self.assertIn("@sha256:", service["lifecycle"]["precondition"][0]["condition"])
        self.assertIn("google_artifact_registry_repository.images", service["depends_on"])

    def test_container_uri_rule_refuses_bad_paths_and_non_digest_images(self):
        condition = RESOURCES["google_cloud_run_v2_service"]["http"]["lifecycle"]["precondition"][0]["condition"]
        pattern = condition.split('regex("', 1)[1].split('", var.container_image)', 1)[0]
        for name, value in dict(region="us-central1", project_id="example-project", prefix="agentic-demo").items():
            pattern = pattern.replace("${var." + name + "}", value)
        base = "us-central1-docker.pkg.dev/example-project/agentic-demo-images/"
        self.assertIsNotNone(re.fullmatch(pattern, base + "api@sha256:" + "a" * 64))
        self.assertIsNotNone(re.fullmatch(pattern, base + "apps/api-v1@sha256:" + "a" * 64))
        for suffix in ("@sha256:" + "a" * 64, "bad name@sha256:" + "a" * 64,
                       "api:latest", "apps//api@sha256:" + "a" * 64,
                       "api@sha256:" + "a" * 63):
            with self.subTest(suffix=suffix):
                self.assertIsNone(re.fullmatch(pattern, base + suffix))

    def test_runtime_identity_and_model_configuration(self):
        service = RESOURCES["google_cloud_run_v2_service"]["http"]
        self.assertEqual(service["template"]["service_account"], "${google_service_account.runtime.email}")
        env = {e["name"]: e["value"] for e in service["template"]["containers"][0]["env"]}
        self.assertEqual(env["GOOGLE_CLOUD_LOCATION"], "${var.inference_location}")
        self.assertEqual(env["GOOGLE_GENAI_MODEL"], "${var.inference_model}")
        self.assertNotEqual(service["location"], env["GOOGLE_CLOUD_LOCATION"])

    def test_runtime_has_only_generation_permission(self):
        roles = RESOURCES["google_project_iam_custom_role"]
        self.assertEqual(roles["generate_text"]["permissions"], ["aiplatform.endpoints.predict"])
        members = RESOURCES["google_project_iam_member"]
        self.assertEqual(len(members), 1)
        self.assertEqual(members["runtime_generate"]["member"], "serviceAccount:${google_service_account.runtime.email}")

    def test_http_service_has_no_public_invoker_or_background_worker(self):
        raw = json.dumps(DOCS)
        self.assertNotIn("allUsers", raw)
        self.assertNotIn("allAuthenticatedUsers", raw)
        self.assertNotIn("invoker_iam_disabled", raw)
        self.assertNotIn("roles/run.invoker", raw)
        service = RESOURCES["google_cloud_run_v2_service"]["http"]
        self.assertEqual(service["ingress"], "INGRESS_TRAFFIC_INTERNAL_ONLY")
        self.assertEqual(service["template"]["max_instance_request_concurrency"], 1)

    def test_pubsub_is_pull_at_least_once_unordered_with_retention(self):
        sub = RESOURCES["google_pubsub_subscription"]["tasks"]
        self.assertNotIn("push_config", sub)
        self.assertFalse(sub["enable_exactly_once_delivery"])
        self.assertFalse(sub["enable_message_ordering"])
        self.assertTrue(sub["retain_acked_messages"])
        self.assertEqual(sub["message_retention_duration"], "604800s")
        self.assertEqual(sub["ack_deadline_seconds"], 60)
        self.assertNotEqual(str(sub["ack_deadline_seconds"]) + "s", sub["message_retention_duration"])

    def test_dead_letter_policy_has_inspection_subscription_and_correct_service_agent_iam(self):
        dlq = RESOURCES["google_pubsub_topic"]["dead_letters"]
        source = RESOURCES["google_pubsub_subscription"]["tasks"]
        self.assertEqual(source["dead_letter_policy"]["dead_letter_topic"], "${google_pubsub_topic.dead_letters.id}")
        self.assertGreaterEqual(source["dead_letter_policy"]["max_delivery_attempts"], 5)
        self.assertLessEqual(source["dead_letter_policy"]["max_delivery_attempts"], 100)
        inspection = RESOURCES["google_pubsub_subscription"]["dead_letters"]
        self.assertEqual(inspection["topic"], "${google_pubsub_topic.dead_letters.id}")
        publisher = RESOURCES["google_pubsub_topic_iam_member"]["service_agent_dlq_publish"]
        subscriber = RESOURCES["google_pubsub_subscription_iam_member"]["service_agent_source_ack"]
        self.assertEqual(publisher["member"], subscriber["member"])
        self.assertEqual(publisher["member"], "serviceAccount:service-${var.project_number}@gcp-sa-pubsub.iam.gserviceaccount.com")
        self.assertEqual((publisher["topic"], publisher["role"]), ("${google_pubsub_topic.dead_letters.name}", "roles/pubsub.publisher"))
        self.assertEqual((subscriber["subscription"], subscriber["role"]), ("${google_pubsub_subscription.tasks.name}", "roles/pubsub.subscriber"))

    def test_application_identities_are_separate(self):
        self.assertEqual(set(RESOURCES["google_service_account"]), {"runtime", "publisher", "consumer", "inspector"})
        pub = RESOURCES["google_pubsub_topic_iam_member"]["app_publish"]
        subs = RESOURCES["google_pubsub_subscription_iam_member"]
        self.assertNotEqual(pub["member"], subs["app_consume"]["member"])
        self.assertNotEqual(subs["app_consume"]["member"], subs["dlq_inspect"]["member"])

    def test_all_declared_resource_and_variable_references_resolve(self):
        text = json.dumps(DOCS)
        for kind, name in re.findall(r"\b(google_[a-z0-9_]+)\.([a-z0-9_]+)\.", text):
            self.assertIn(kind, RESOURCES)
            self.assertIn(name, RESOURCES[kind])
        for name in re.findall(r"\bvar\.([a-z0-9_]+)\b", text):
            self.assertIn(name, VARIABLES)
        for resources in RESOURCES.values():
            for resource in resources.values():
                for address in resource.get("depends_on", []):
                    kind, name = address.split(".")
                    self.assertIn(name, RESOURCES[kind])

    def test_oidc_template_is_disabled_and_has_no_deploy_commands(self):
        path = ROOT / "ci" / "github-oidc.reference.yaml.example"
        text = path.read_text(encoding="utf-8")
        self.assertIn("if: ${{ false }}", text)
        self.assertIn("id-token: write", text)
        self.assertIn("workload_identity_provider:", text)
        self.assertNotIn("credentials_json:", text)
        self.assertNotIn("run:", text)
        self.assertFalse((ROOT / ".github" / "workflows").exists())
