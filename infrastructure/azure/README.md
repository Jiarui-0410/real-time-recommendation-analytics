# Azure for Students deployment

This deployment runs only the online recommendation path. PySpark, Kafka,
PostgreSQL, Power BI, and model training remain local.

## Architecture

- Azure Container Registry (Basic) stores the FastAPI image. Azure for Students
  blocks ACR Tasks in this subscription, so the VM performs the first build and push.
- Private Blob Storage stores `artifacts/model_full_v1`.
- One Linux B-series VM runs FastAPI and Qdrant with Docker Compose.
- A managed identity pulls the image and reads model blobs without embedded secrets.
- The network security group exposes only TCP 8000 to one caller CIDR. SSH is not
  opened, matching the NTU policy visible on the student subscription.
- Qdrant port 6333 stays inside the Docker network.

All resources default to `eastasia` (Hong Kong). Although the NTU management-group
initiative mentions Singapore, that initiative is `DoNotEnforce`. The enforced
student-subscription assignment currently permits `eastasia`, `indonesiacentral`,
`uaenorth`, `centralindia`, and `indiasouthcentral`; it does not permit Singapore.

## Before deployment

1. Keep the Azure for Students spending limit enabled.
2. Create a monthly Cost Management budget and email alerts.
3. Install Azure CLI, reopen PowerShell, and run `az login`.
4. Find your public IPv4 address and express it as a `/32` CIDR.
5. Confirm that the subscription allows a 4-GiB B-series VM in East Asia.

The template deliberately does not open SSH. Use Azure Portal **Run command** for
diagnostics after the VM exists.

## Deploy

From the project root in PowerShell:

```powershell
./infrastructure/azure/deploy.ps1 -AllowedApiCidr "203.0.113.10/32"
```

The script uses two phases so the VM is not billed while the image and model are
being prepared:

1. Create ACR, storage, identity, RBAC, and networking.
2. Upload the API source bundle and model to Blob Storage.
3. Create the VM. Cloud-init builds and pushes the API image, then starts Qdrant,
   the idempotent indexer, and FastAPI.

Do not run the example CIDR unchanged. Replace it with your actual public IPv4.

## Verify

Wait for cloud-init and Qdrant indexing, then call the URL printed by the deploy
script:

```powershell
Invoke-RestMethod "http://<public-ip>:8000/health"
Invoke-RestMethod "http://<public-ip>:8000/recommendations/<known-user-id>?k=10"
Invoke-RestMethod "http://<public-ip>:8000/recommendations/999999999?k=10"
```

Expected strategies are `two_tower_retrieval` for a known user and
`popularity_cold_start` for an unknown user.

To inspect the containers, Qdrant point count, API metrics, and indexer result without
opening SSH, run the bundled read-only script through Azure Run Command:

```powershell
az vm run-command invoke `
  --resource-group rg-retail-recommendation-demo `
  --name vm-retail-recommendation `
  --command-id RunShellScript `
  --scripts '@infrastructure/azure/verify-remote.sh' `
  --query 'value[0].message' `
  --output tsv
```

The verified v2 deployment contained 212,915 Qdrant points in `green` state. A
22-request validation run recorded zero errors, about 13.1 ms average server latency,
and about 86.4 ms average client-observed latency from the test location.

## Stop or remove

Deallocate the VM in Azure Portal when the demo is idle. Compute billing stops after
deallocation, but disks, Blob Storage, ACR, and the public IP can still incur costs.

To remove the complete demo resource group:

```powershell
./infrastructure/azure/destroy.ps1
```

PowerShell asks for confirmation because this deletes the cloud resources in that
resource group. The local model and project files are not touched.
