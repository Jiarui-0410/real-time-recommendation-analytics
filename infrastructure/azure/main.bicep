targetScope = 'resourceGroup'

@description('Region allowed by the Azure for Students subscription policy.')
@allowed([
  'eastasia'
  'indonesiacentral'
  'uaenorth'
  'centralindia'
  'indiasouthcentral'
])
param location string = 'eastasia'

@description('Deploy the VM after the image and model artifacts have been uploaded.')
param deployVm bool = false

@description('Public IPv4 CIDR allowed to call the demo API, for example 203.0.113.10/32.')
param allowedApiCidr string

@description('SSH public key stored on the VM. Port 22 is intentionally not opened.')
param sshPublicKey string

@description('Microsoft Entra object ID of the person deploying the stack.')
param deployerObjectId string

param adminUsername string = 'azureuser'
param vmSize string = 'Standard_B2ls_v2'
param imageTag string = 'v1'
param modelPrefix string = 'model_full_v1'

var suffix = take(uniqueString(subscription().id, resourceGroup().id), 10)
var storageName = 'streco${suffix}'
var acrName = 'acrretail${suffix}'
var identityName = 'id-retail-recommendation'
var vnetName = 'vnet-retail-recommendation'
var subnetName = 'snet-api'
var nsgName = 'nsg-retail-recommendation'
var publicIpName = 'pip-retail-recommendation'
var nicName = 'nic-retail-recommendation'
var vmName = 'vm-retail-recommendation'
var apiImage = '${acr.properties.loginServer}/retail-api:${imageTag}'
var allowedStorageIp = replace(allowedApiCidr, '/32', '')

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.20.0.0/16'
      ]
    }
    subnets: [
      {
        name: subnetName
        properties: {
          addressPrefix: '10.20.1.0/24'
          networkSecurityGroup: {
            id: nsg.id
          }
          serviceEndpoints: [
            {
              service: 'Microsoft.Storage'
              locations: [
                location
              ]
            }
          ]
        }
      }
    ]
  }
}

resource nsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: nsgName
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowApiFromOwner'
        properties: {
          priority: 100
          access: 'Allow'
          direction: 'Inbound'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '8000'
          sourceAddressPrefix: allowedApiCidr
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

resource subnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = {
  parent: vnet
  name: subnetName
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
      ipRules: [
        {
          action: 'Allow'
          value: allowedStorageIp
        }
      ]
      virtualNetworkRules: [
        {
          action: 'Allow'
          id: subnet.id
        }
      ]
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

resource modelContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'models'
  properties: {
    publicAccess: 'None'
  }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

var acrPushRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '8311e382-0749-4cb8-b61a-304f252e45ec'
)
var blobReaderRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
)
var blobContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)

resource acrPushAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, identity.id, acrPushRoleId)
  scope: acr
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPushRoleId
  }
}

resource blobReaderAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, identity.id, blobReaderRoleId)
  scope: storage
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: blobReaderRoleId
  }
}

resource deployerBlobAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, deployerObjectId, blobContributorRoleId)
  scope: storage
  properties: {
    principalId: deployerObjectId
    principalType: 'User'
    roleDefinitionId: blobContributorRoleId
  }
}

resource publicIp 'Microsoft.Network/publicIPAddresses@2024-05-01' = if (deployVm) {
  name: publicIpName
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
  }
}

resource nic 'Microsoft.Network/networkInterfaces@2024-05-01' = if (deployVm) {
  name: nicName
  location: location
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          subnet: {
            id: subnet.id
          }
          publicIPAddress: {
            id: publicIp.id
          }
        }
      }
    ]
  }
}

var bootstrapTemplate = loadTextContent('bootstrap.sh')
var bootstrapWithImage = replace(bootstrapTemplate, '__API_IMAGE__', apiImage)
var bootstrapWithAcr = replace(bootstrapWithImage, '__ACR_NAME__', acr.name)
var bootstrapWithStorage = replace(bootstrapWithAcr, '__STORAGE_ACCOUNT__', storage.name)
var bootstrapWithModel = replace(bootstrapWithStorage, '__MODEL_PREFIX__', modelPrefix)
var bootstrap = replace(bootstrapWithModel, '__IDENTITY_CLIENT_ID__', identity.properties.clientId)
var cloudInitTemplate = loadTextContent('cloud-init.yaml')
var cloudInitWithCompose = replace(
  cloudInitTemplate,
  '__COMPOSE_B64__',
  base64(loadTextContent('../../compose.azure.yaml'))
)
var cloudInit = replace(cloudInitWithCompose, '__BOOTSTRAP_B64__', base64(bootstrap))

resource vm 'Microsoft.Compute/virtualMachines@2024-07-01' = if (deployVm) {
  name: vmName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    osProfile: {
      computerName: 'retail-reco'
      adminUsername: adminUsername
      customData: base64(cloudInit)
      linuxConfiguration: {
        disablePasswordAuthentication: true
        provisionVMAgent: true
        ssh: {
          publicKeys: [
            {
              path: '/home/${adminUsername}/.ssh/authorized_keys'
              keyData: sshPublicKey
            }
          ]
        }
      }
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'ubuntu-24_04-lts'
        sku: 'server'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        managedDisk: {
          storageAccountType: 'StandardSSD_LRS'
        }
        diskSizeGB: 32
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic.id
        }
      ]
    }
  }
  dependsOn: [
    acrPushAssignment
    blobReaderAssignment
  ]
}

output acrName string = acr.name
output acrLoginServer string = acr.properties.loginServer
output storageAccountName string = storage.name
output modelContainerName string = modelContainer.name
output managedIdentityClientId string = identity.properties.clientId
output publicIpAddress string = deployVm ? publicIp!.properties.ipAddress : ''
output apiUrl string = deployVm ? 'http://${publicIp!.properties.ipAddress}:8000' : ''
