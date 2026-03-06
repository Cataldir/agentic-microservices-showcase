# Azure Setup Guide

Step-by-step instructions for provisioning the Azure infrastructure and configuring
your local environment to run all eight notebooks.

## Prerequisites

| Tool | Minimum Version | Check |
|------|-----------------|-------|
| Azure CLI | 2.61.0 | `az --version` |
| Python | 3.11.0 | `python --version` |
| jq | any | `jq --version` |
| Git | any | `git --version` |

### Install Azure CLI

```bash
# macOS
brew install azure-cli

# Ubuntu / Debian
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Windows (PowerShell)
winget install Microsoft.AzureCLI
```

## Step 1 — Authenticate

```bash
az login
az account show  # confirm correct subscription
```

## Step 2 — Set Variables

```bash
export AZURE_SUBSCRIPTION_ID="<your-subscription-id>"
export AZURE_RESOURCE_GROUP="rg-agentic-showcase-dev"
export AZURE_LOCATION="eastus2"
```

## Step 3 — Deploy Infrastructure

```bash
bash infra/deploy.sh
```

This creates:
- Log Analytics Workspace + Application Insights
- Azure Key Vault (RBAC mode)
- Azure OpenAI (gpt-4o + text-embedding-3-small)
- Service Bus namespace + `agent-events` queue + `agent-commands` queue
- Container Apps Environment + Container Registry

At the end, `infra/deploy.sh` writes a `.env` file at the repo root.

## Step 4 — RBAC Permissions

The Bicep modules create resources but do not assign RBAC roles.
Run these commands to grant yourself the necessary permissions:

```bash
USER_ID=$(az ad signed-in-user show --query id -o tsv)
RG_ID=$(az group show --name $AZURE_RESOURCE_GROUP --query id -o tsv)

# Azure OpenAI: Cognitive Services OpenAI User
az role assignment create \
  --assignee $USER_ID \
  --role "Cognitive Services OpenAI User" \
  --scope $RG_ID

# Key Vault: Key Vault Secrets User
KV_URI=$(az keyvault list --resource-group $AZURE_RESOURCE_GROUP --query '[0].id' -o tsv)
az role assignment create \
  --assignee $USER_ID \
  --role "Key Vault Secrets User" \
  --scope $KV_URI

# Service Bus: Azure Service Bus Data Owner
SB_ID=$(az servicebus namespace list --resource-group $AZURE_RESOURCE_GROUP --query '[0].id' -o tsv)
az role assignment create \
  --assignee $USER_ID \
  --role "Azure Service Bus Data Owner" \
  --scope $SB_ID
```

## Step 5 — Install Python Dependencies

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Core dependencies
pip install -e .

# Azure-specific extras (needed for chapters 02, 05, 06, 08)
pip install -e ".[azure]"

# Development tools (linting, testing)
pip install -e ".[dev]"
```

## Step 6 — Load Environment and Launch Notebooks

```bash
source .env
jupyter lab notebooks/
```

Or in VS Code: open any `.ipynb` file and select the `.venv` kernel.

## Running Without Azure

All notebooks are designed to run **offline** when Azure credentials are not available.
Azure-specific cells contain a guard:

```python
if os.environ.get('AZURE_OPENAI_ENDPOINT'):
    # real Azure call
else:
    # mock demonstration
```

The CI pipeline sets `NOTEBOOK_OFFLINE_MODE=true` to skip live Azure calls.

## Cleaning Up

To avoid ongoing costs, delete the resource group when done:

```bash
az group delete --name $AZURE_RESOURCE_GROUP --yes --no-wait
```

> **Note**: Azure OpenAI quota is released within a few minutes of deletion.
> Key Vault soft-delete retains the vault for 7 days but incurs no cost.
