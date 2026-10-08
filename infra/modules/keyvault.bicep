// Azure Key Vault with RBAC authorization model

param env string
param location string
param suffix string

var kvName = 'kv-agents-${env}-${take(suffix, 6)}'

resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: kvName
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true   // RBAC preferred over access policies
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: false    // Set true for production
    publicNetworkAccess: 'Enabled'  // Restrict via privateEndpoints in prod
  }
  tags: { environment: env, project: 'agentic-microservices' }
}

output uri string = keyVault.properties.vaultUri
output resourceId string = keyVault.id
