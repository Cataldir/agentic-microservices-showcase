// Azure Container Apps Environment for agent workloads

param env string
param location string
param suffix string
param logAnalyticsWorkspaceId string

var environmentName = 'cae-agents-${env}-${suffix}'
var registryName = 'cracagents${env}${take(suffix, 6)}'

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false  // Use managed identity for pulls
    anonymousPullEnabled: false
  }
  tags: { environment: env, project: 'agentic-microservices' }
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: reference(logAnalyticsWorkspaceId, '2023-09-01').customerId
        sharedKey: listKeys(logAnalyticsWorkspaceId, '2023-09-01').primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
  tags: { environment: env, project: 'agentic-microservices' }
}

output environmentId string = containerAppsEnvironment.id
output environmentName string = containerAppsEnvironment.name
output registryLoginServer string = containerRegistry.properties.loginServer
output registryId string = containerRegistry.id
