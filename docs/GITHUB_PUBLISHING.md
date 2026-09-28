# GitHub publishing checklist

## Suggested repository metadata

**Repository name**

```text
real-time-recommendation-analytics
```

**Description**

```text
End-to-end retail analytics and recommendation platform using PySpark, Kafka,
PostgreSQL, Power BI, PyTorch Two-Tower, Qdrant, FastAPI, Docker and Azure.
```

**Topics**

```text
pyspark kafka postgresql power-bi pytorch recommender-system two-tower qdrant
fastapi docker azure data-engineering machine-learning
```

Make the repository public only after the secret and tracked-file checks below pass.

## Local checks

```powershell
python -m ruff check .
python -m pytest -q
git status --short
git check-ignore -v .env artifacts/model_full_v1/two_tower.pt
```

Expected: lint passes, 14 tests pass, and both `.env` and model weights are ignored.

## First publish

Create an empty GitHub repository without a generated README, license, or `.gitignore`,
then run from the project root:

```powershell
git add .
git commit -m "Build end-to-end retail recommendation platform"
git remote add origin https://github.com/<username>/real-time-recommendation-analytics.git
git push -u origin main
```

Do not choose a license casually. Add one only after deciding how other people may reuse
the code and confirming that the Retailrocket dataset itself is not being redistributed.

## GitHub page review

- Confirm the Executive Overview screenshot renders near the top of the README.
- Confirm the Mermaid architecture diagram renders.
- Confirm the four Power BI screenshots contain no account details.
- Confirm the CI workflow passes.
- Add the repository description and topics listed above.
- Pin the repository on the profile.
- Do not publish the live Azure IP; the VM is normally deallocated and CIDR-restricted.
- Do not upload raw Retailrocket files, processed Parquet, model binaries, `.env`, local
  Power BI caches, Qdrant storage, or Spark checkpoints.
