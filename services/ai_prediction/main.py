"""
AI Prediction Service — FastAPI application for real-time sepsis inference.

Exposes REST endpoints that accept patient data (directly or via MongoDB)
and return sepsis risk predictions using a pre-trained LightGBM / GBDT model.
"""

from fastapi import FastAPI
from contextlib import asynccontextmanager

from api.prediction import router as prediction_router
from models.model_loader import load_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the ML model once at startup."""
    load_model()
    yield


app = FastAPI(
    title="SepsisAI — Prediction Service",
    description="Real-time sepsis risk prediction via LightGBM.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(prediction_router)


@app.get("/health", tags=["Ops"])
async def health():
    """Liveness / readiness probe for Docker & Kubernetes."""
    return {"status": "ok"}
