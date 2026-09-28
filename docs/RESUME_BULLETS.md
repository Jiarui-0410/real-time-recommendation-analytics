# Resume and interview packaging

Use two or three bullets, depending on available space. Keep the accuracy claim honest:
the model's strongest measured result is catalog discovery, not a large ranking lift.

## English resume bullets

- Built an end-to-end retail analytics and recommendation platform that processed
  **2.76M behavioral events** with PySpark, Kafka, Parquet, and PostgreSQL, including
  temporal item-category joins, deterministic event IDs, and idempotent streaming sinks.
- Trained and evaluated a PyTorch **Two-Tower** recommender over **1.12M users** and
  **212.9K items**; implemented seen-item filtering and popularity cold-start fallback,
  increasing Catalog Coverage@10 from **0.0061% to 0.505% (82.8x)** while reporting the
  nearly flat Top-10 accuracy result transparently.
- Deployed FastAPI and Qdrant to Azure with Docker, Bicep, private Blob Storage, ACR,
  managed identity, and IP-restricted networking; verified **212,915 green vectors**,
  zero errors in the cloud validation run, and approximately **13 ms server latency**.
- Designed a four-page Power BI dashboard backed by PostgreSQL for executive KPIs,
  funnel trends, user/product engagement, and baseline-versus-model evaluation.

## 中文简历表述

- 搭建端到端电商实时分析与推荐平台，使用 PySpark、Kafka、Parquet 与 PostgreSQL
  处理 **275 万条用户行为**，实现时序商品类别关联、确定性事件 ID 与幂等写入。
- 基于 PyTorch 训练 Two-Tower 推荐模型，覆盖 **112 万用户和 21.3 万商品**，实现
  已交互商品过滤与冷启动 Popularity fallback；Catalog Coverage@10 从 **0.0061%**
  提升至 **0.505%（约 82.8 倍）**，并如实报告准确率提升有限。
- 使用 Docker、Bicep、Azure VM、Blob Storage、ACR 与托管身份部署 FastAPI +
  Qdrant；验证 **212,915 个向量**状态正常，云端测试零错误，服务端平均延迟约
  **13 ms**。
- 构建四页 Power BI 看板，展示核心业务 KPI、行为漏斗、用户/商品参与度以及
  Popularity 与 Two-Tower 的离线评估对比。

## 30-second interview summary

I built the project to connect data engineering, analytics, recommendation modeling, and
serving in one reproducible system. The pipeline processes the full Retailrocket event
set with Spark, loads PostgreSQL datasets for Power BI, trains a temporally evaluated
Two-Tower model, indexes item embeddings in Qdrant, and serves Top-K results through
FastAPI on Azure. The important modeling lesson was that 93.3% of evaluated users were
cold-start users: accuracy stayed nearly flat, but the hybrid system expanded catalog
coverage by 82.8x, so I kept popularity as an explicit production fallback.

## Defensible claims

- Say **"streaming analytics and online serving"**, not continuous online learning.
- Say **"82.8x catalog coverage lift"**, not 82.8 percentage points.
- Say ranking accuracy was **nearly flat**, not significantly improved.
- State that Power BI funnel stages are independent user populations, not a causal or
  ordered customer journey.
- State that Azure latency was measured from one test location and is not a formal SLA.
