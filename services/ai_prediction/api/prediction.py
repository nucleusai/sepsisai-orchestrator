"""
Prediction endpoints.

- POST /predict          — predict from a full JSON payload
- POST /predict/by-patient — predict by querying MongoDB (patient + hour)
- POST /predict/reload-model — hot-reload a new model from disk
- GET  /predict/patients  — list available patient IDs in the database
"""

import os

from fastapi import APIRouter, HTTPException, Query

from schemas.prediction_schemas import (
    PredictionRequest,
    PatientHourRequest,
    PredictionResponse,
)
from services.prediction_service import predict_from_input, predict_from_mongo
from models.model_loader import load_model
from database.mongo import get_collection

router = APIRouter(prefix="/predict", tags=["Prediction"])


@router.post("", response_model=PredictionResponse, summary="Predict from JSON payload")
async def predict(input_data: PredictionRequest):
    """Receive all 26 features in the request body and return a prediction."""
    return predict_from_input(input_data)


@router.post(
    "/by-patient",
    response_model=PredictionResponse,
    summary="Predict from MongoDB record",
)
async def predict_by_patient(data: PatientHourRequest):
    """Look up a patient record in MongoDB and return a prediction."""
    return predict_from_mongo(data)


@router.post("/reload-model", summary="Hot-reload model from disk")
def reload_model_endpoint(
    path: str = Query(..., description="Filesystem path to a .pkl model file"),
):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Model file not found")
    load_model(path)
    return {"message": f"Model reloaded from {path}"}


@router.get("/patients", summary="List patient IDs available in MongoDB")
async def list_patients():
    """Return distinct patient identifiers stored in the database."""
    col = get_collection()
    patients = col.distinct("Paciente")
    return {"patients": patients}
