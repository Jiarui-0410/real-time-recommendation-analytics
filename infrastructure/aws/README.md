# AWS deployment

> Reference template only. This path was not used for the verified portfolio deployment;
> the completed deployment is documented under `infrastructure/azure/`.

The cloud layer has two explicit responsibilities:

- S3 stores versioned model artifacts and, optionally, processed Parquet datasets.
- EC2 runs the containerized FastAPI service.

## Deploy

1. Build and publish `Dockerfile.api` to a registry reachable from EC2.
2. Deploy `cloudformation.yaml`, setting `ContainerImage` and your public IP as
   `AllowedCidr` (for example `203.0.113.10/32`).
3. Upload the trained artifacts:

   ```bash
   pip install -e ".[aws]"
   python -m retail_stream.cloud.upload_artifacts artifacts/model \
     --bucket <stack-output-bucket> --prefix models/current
   ```

4. Reboot the demo instance, or rerun its sync/container commands, after replacing a
   model. For a portfolio demo, stop the instance when it is not in use.

The template defaults to localhost-only ingress deliberately. Never expose the API to
the world without authentication, TLS, rate limiting, and a deliberate cost budget.

