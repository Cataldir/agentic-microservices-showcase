# Infrastructure — Azure Bicep

This directory contains Infrastructure-as-Code for the Agentic Microservices Showcase.
All resources are deployed to a single Azure resource group in one Bicep deployment.

## Resources Deployed

| Module | Azure Resource | Used In |
|--------|---------------|--------|
| `appinsights.bicep` | Log Analytics Workspace + Application Insights | Ch08 observability |
| `keyvault.bicep` | Azure Key Vault (RBAC) | Ch08 secret management |
| `openai.bicep` | Azure OpenAI (gpt-4o + text-embedding-3-small) | Ch02, Ch05, Ch08 |
| `servicebus.bicep` | Service Bus namespace + 2 queues | Ch06 messaging |
| `container-apps.bicep` | Container Apps Environment + ACR | Ch01, Ch03, Ch04, Ch08 |

## Prerequisites

- Azure CLI ≥ 2.61 — `az --version`
- Bicep CLI ≥ 0.28 — `az bicep version` (auto-installed by Azure CLI)
- Azure subscription with **Contributor** role on the resource group
- `jq` installed (for `.env` extraction in `deploy.sh`)

## Quick Deploy

```bash
# 1. Log in
az login

# 2. Set your subscription (optional if you have only one)
export AZURE_SUBSCRIPTION_ID="<your-subscription-id>"
export AZURE_RESOURCE_GROUP="rg-agentic-showcase-dev"
export AZURE_LOCATION="eastus2"

# 3. Deploy
bash infra/deploy.sh

# 4. Load environment variables
source .env
```

## Customization

Edit `parameters/dev.bicepparam` to change the environment tag or location.

For staging/prod, create `parameters/staging.bicepparam` and `parameters/prod.bicepparam`
following the same pattern.

## Security Notes

- Key Vault uses **RBAC authorization** (not legacy access policies)
- Service Bus uses **Entra ID authentication only** (`disableLocalAuth: true`)
- Container Registry has **admin user disabled** (managed identity for pulls)
- The generated `.env` file is listed in `.gitignore` — never commit it
