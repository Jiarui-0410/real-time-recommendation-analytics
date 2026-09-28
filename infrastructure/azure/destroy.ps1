[CmdletBinding(SupportsShouldProcess, ConfirmImpact = "High")]
param(
    [string]$ResourceGroup = "rg-retail-recommendation-demo"
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI was not found."
}

if ($PSCmdlet.ShouldProcess($ResourceGroup, "Delete the Azure demo resource group")) {
    az group delete --name $ResourceGroup --yes --no-wait
    if ($LASTEXITCODE -ne 0) {
        throw "Azure resource-group deletion request failed."
    }
    Write-Host "Deletion requested for $ResourceGroup."
}
