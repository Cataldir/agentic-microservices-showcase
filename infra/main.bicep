// =============================================================================
// Agentic Microservices Showcase — Azure Infrastructure
// Deploys: Azure OpenAI, Container Apps Environment, Service Bus,
//          Key Vault, Log Analytics, Application Insights
// =============================================================================

targetScope = 'resourceGroup'

@description('Environment tag (dev | staging | prod)')
param env string = 'dev'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Short alphanumeric suffix for globally-unique names')
param suffix string = uniqueString(resourceGroup().id)

// ---------------------------------------------------------------------------
// Modules
// ---------------------------------------------------------------------------

module observability 'modules/appinsights.bicep' = {
  name: 'observability'
  params: {
    env: env
    location: location
    suffix: suffix
  }
}

module keyvault 'modules/keyvault.bicep' = {
  name: 'keyvault'
  params: {
    env: env
    location: location
    suffix: suffix
  }
}

module openai 'modules/openai.bicep' = {
  name: 'openai'
  params: {
    env: env
    location: location
    suffix: suffix
  }
}

module messaging 'modules/servicebus.bicep' = {
  name: 'messaging'
  params: {
    env: env
    location: location
    suffix: suffix
  }
}

module compute 'modules/container-apps.bicep' = {
  name: 'compute'
  params: {
    env: env
    location: location
    suffix: suffix
    logAnalyticsWorkspaceId: observability.outputs.logAnalyticsWorkspaceId
  }
}

// ---------------------------------------------------------------------------
// Outputs (referenced by notebooks and .env.example)
// ---------------------------------------------------------------------------

output openAiEndpoint string = openai.outputs.endpoint
output serviceBusNamespace string = messaging.outputs.namespaceFqdn
output containerAppsEnvironmentId string = compute.outputs.environmentId
output appInsightsConnectionString string = observability.outputs.connectionString
output keyVaultUri string = keyvault.outputs.uri
