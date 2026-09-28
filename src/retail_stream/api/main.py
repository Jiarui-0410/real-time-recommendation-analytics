from __future__ import annotations

import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from retail_stream.api.engine import RecommendationEngine


class ServiceMetrics:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.requests = 0
        self.errors = 0
        self.total_latency_seconds = 0.0

    def observe(self, latency: float, error: bool = False) -> None:
        with self.lock:
            self.requests += 1
            self.errors += int(error)
            self.total_latency_seconds += latency

    def render(self) -> str:
        with self.lock:
            average = self.total_latency_seconds / self.requests if self.requests else 0.0
            return (
                f"recommendation_requests_total {self.requests}\n"
                f"recommendation_errors_total {self.errors}\n"
                f"recommendation_latency_seconds_sum {self.total_latency_seconds:.6f}\n"
                f"recommendation_latency_seconds_avg {average:.6f}\n"
            )


metrics = ServiceMetrics()


@asynccontextmanager
async def lifespan(app: FastAPI):
    model_dir = os.getenv("MODEL_DIR", "artifacts/model")
    vector_index = None
    if os.getenv("USE_QDRANT", "false").lower() == "true":
        from retail_stream.retrieval.qdrant_index import QdrantVectorIndex

        vector_index = QdrantVectorIndex(
            os.getenv("QDRANT_URL", "http://localhost:6333"),
            os.getenv("QDRANT_COLLECTION", "retail_items"),
        )
    app.state.engine = RecommendationEngine(model_dir, vector_index)
    yield


app = FastAPI(
    title="Retail Recommendation API", version="1.0.0", lifespan=lifespan
)


@app.middleware("http")
async def measure_requests(request: Request, call_next):
    start = time.perf_counter()
    error = False
    try:
        response = await call_next(request)
        error = response.status_code >= 500
        return response
    except Exception:
        error = True
        raise
    finally:
        if request.url.path.startswith("/recommendations/"):
            metrics.observe(time.perf_counter() - start, error)


@app.get("/health")
def health(request: Request):
    engine = getattr(request.app.state, "engine", None)
    return {
        "status": "ok" if engine is not None else "starting",
        "model_loaded": engine is not None,
    }


@app.get("/recommendations/{user_id}")
def recommendations(
    user_id: int,
    request: Request,
    k: int = Query(10, ge=1, le=100),
    filter_seen: bool = True,
):
    try:
        return request.app.state.engine.recommend(user_id, k, filter_seen)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/metrics", response_class=PlainTextResponse)
def service_metrics():
    return metrics.render()


def run() -> None:
    import uvicorn

    uvicorn.run("retail_stream.api.main:app", host="0.0.0.0", port=8000, reload=False)
