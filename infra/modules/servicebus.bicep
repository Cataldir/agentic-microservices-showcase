// Azure Service Bus — Standard tier with agent-events queue

param env string
param location string
param suffix string

var namespaceName = 'sb-agents-${env}-${suffix}'

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: namespaceName
  location: location
  sku: { name: 'Standard', tier: 'Standard' }
  properties: {
    minimumTlsVersion: '1.2'
    disableLocalAuth: true  // Enforce Entra ID authentication only
  }
  tags: { environment: env, project: 'agentic-microservices' }
}

resource agentEventsQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: serviceBusNamespace
  name: 'agent-events'
  properties: {
    maxDeliveryCount: 5
    deadLetteringOnMessageExpiration: true
    lockDuration: 'PT1M'
    defaultMessageTimeToLive: 'P7D'
    requiresDuplicateDetection: true
    duplicateDetectionHistoryTimeWindow: 'PT1H'
  }
}

resource commandsQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: serviceBusNamespace
  name: 'agent-commands'
  properties: {
    maxDeliveryCount: 3
    deadLetteringOnMessageExpiration: true
    lockDuration: 'PT30S'
    requiresSession: true  // FIFO per agent session
  }
}

output namespaceFqdn string = '${serviceBusNamespace.name}.servicebus.windows.net'
output resourceId string = serviceBusNamespace.id
output agentEventsQueueName string = agentEventsQueue.name
output commandsQueueName string = commandsQueue.name
