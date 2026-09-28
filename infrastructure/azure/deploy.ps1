[CmdletBinding()]
param(
    [string]$ResourceGroup = "rg-retail-recommendation-demo",
    [ValidateSet("eastasia", "indonesiacentral", "uaenorth", "centralindia", "indiasouthcentral")]
    [string]$Location = "eastasia",
    [Parameter(Mandatory)]
    [string]$AllowedApiCidr,
    [string]$VmSize = "Standard_B2ls_v2",
    [string]$ImageTag = "v1",
    [string]$ModelDirectory = "artifacts/model_full_v1",
    [string]$SshPublicKeyPath = "$env:USERPROFILE/.ssh/id_ed25519.pub"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$template = Join-Path $PSScriptRoot "main.bicep"
$modelPath = (Resolve-Path (Join-Path $projectRoot $ModelDirectory)).Path

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI was not found. Install it, reopen PowerShell, and run az login."
}

az account show --output none
if ($LASTEXITCODE -ne 0) {
    throw "Azure CLI is not signed in. Run az login first."
}

if ($AllowedApiCidr -notmatch "/") {
    $AllowedApiCidr = "$AllowedApiCidr/32"
}

if (-not (Test-Path -LiteralPath $SshPublicKeyPath)) {
    $sshDirectory = Split-Path $SshPublicKeyPath -Parent
    New-Item -ItemType Directory -Force -Path $sshDirectory | Out-Null
    $privateKeyPath = [System.IO.Path]::ChangeExtension($SshPublicKeyPath, $null)
    ssh-keygen -q -t ed25519 -N '""' -f $privateKeyPath
}
$sshPublicKey = (Get-Content -LiteralPath $SshPublicKeyPath -Raw).Trim()

$providers = @(
    "Microsoft.Compute",
    "Microsoft.ContainerRegistry",
    "Microsoft.ManagedIdentity",
    "Microsoft.Network",
    "Microsoft.Storage"
)
foreach ($provider in $providers) {
    az provider register --namespace $provider --wait --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to register resource provider $provider"
    }
}

az group create --name $ResourceGroup --location $Location --output none
$deployerObjectId = (az ad signed-in-user show --query id --output tsv).Trim()
if (-not $deployerObjectId) {
    throw "Could not determine the signed-in Microsoft Entra object ID."
}

$commonParameters = @(
    "location=$Location",
    "allowedApiCidr=$AllowedApiCidr",
    "sshPublicKey=$sshPublicKey",
    "deployerObjectId=$deployerObjectId",
    "vmSize=$VmSize",
    "imageTag=$ImageTag"
)

Write-Host "Creating the no-compute foundation (ACR, storage, identity, and network)..."
$foundationJson = az deployment group create `
    --resource-group $ResourceGroup `
    --template-file $template `
    --parameters deployVm=false @commonParameters `
    --output json
if ($LASTEXITCODE -ne 0) {
    throw "Foundation deployment failed."
}
$foundation = $foundationJson | ConvertFrom-Json
$acrName = $foundation.properties.outputs.acrName.value
$storageName = $foundation.properties.outputs.storageAccountName.value
$loginServer = $foundation.properties.outputs.acrLoginServer.value

Write-Host "Uploading model artifacts to private Blob Storage..."
$uploaded = $false
foreach ($attempt in 1..18) {
    az storage blob upload-batch `
        --account-name $storageName `
        --destination models `
        --destination-path model_full_v1 `
        --source $modelPath `
        --auth-mode login `
        --overwrite true `
        --only-show-errors
    if ($LASTEXITCODE -eq 0) {
        $uploaded = $true
        break
    }
    Start-Sleep -Seconds 10
}
if (-not $uploaded) {
    throw "Model upload failed. RBAC propagation can take several minutes; rerun the script."
}

Write-Host "Packaging API source for the VM-side Docker build..."
$sourceArchive = Join-Path $env:TEMP "retail-api-source.zip"
if (Test-Path -LiteralPath $sourceArchive) {
    Remove-Item -LiteralPath $sourceArchive -Force
}
Compress-Archive `
    -Path @(
        (Join-Path $projectRoot "Dockerfile.api"),
        (Join-Path $projectRoot "pyproject.toml"),
        (Join-Path $projectRoot "README.md"),
        (Join-Path $projectRoot "src")
    ) `
    -DestinationPath $sourceArchive `
    -CompressionLevel Optimal

az storage blob upload `
    --account-name $storageName `
    --container-name models `
    --name source/retail-api.zip `
    --file $sourceArchive `
    --auth-mode login `
    --overwrite true `
    --only-show-errors
$sourceUploadExit = $LASTEXITCODE
Remove-Item -LiteralPath $sourceArchive -Force
if ($sourceUploadExit -ne 0) {
    throw "API source upload failed."
}

Write-Host "Creating the VM and starting FastAPI plus Qdrant..."
$deploymentJson = az deployment group create `
    --resource-group $ResourceGroup `
    --template-file $template `
    --parameters deployVm=true @commonParameters `
    --output json
if ($LASTEXITCODE -ne 0) {
    throw "VM deployment failed."
}
$deployment = $deploymentJson | ConvertFrom-Json
$apiUrl = $deployment.properties.outputs.apiUrl.value

Write-Host "Deployment submitted successfully."
Write-Host "Image: $loginServer/retail-api:$ImageTag"
Write-Host "API:   $apiUrl"
Write-Host "Cloud-init can take several minutes to build the image, download the model, and build the Qdrant index."
