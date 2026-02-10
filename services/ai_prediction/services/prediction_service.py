"""
Core prediction logic.

Two entry-points:
  - predict_from_input  — caller supplies the full feature vector
  - predict_from_mongo  — features are fetched from MongoDB
"""

import numpy as np
from fastapi import HTTPException

from api.constants import EXPECTED_KEYS
from database.mongo import get_collection
from models.model_loader import get_model

# Sentinel value used during preprocessing to represent missing data
MISSING_SENTINEL = -9999


def predict_from_input(input_data) -> dict:
    """Run inference on a feature vector provided in the request body."""
    try:
        features = [getattr(input_data, key) for key in EXPECTED_KEYS]
        features_array = np.array(features).reshape(1, -1)
        model = get_model()
        prediction = model.predict(features_array)
        return {"prediction": int(prediction[0]), "patient": "direct-input"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def predict_from_mongo(data) -> dict:
    """Fetch a patient record from MongoDB and run inference."""
    try:
        collection = get_collection()
        query = {"Paciente": data.patient, "Hora": data.hour}
        projection = {key: 1 for key in EXPECTED_KEYS}
        records = list(collection.find(query, projection))

        if not records:
            # Try hour as int (some records store it numerically)
            try:
                query["Hora"] = int(data.hour)
                records = list(collection.find(query, projection))
            except ValueError:
                pass

        if not records:
            raise HTTPException(
                status_code=404,
                detail=f"No records found for patient={data.patient}, hour={data.hour}",
            )

        record = records[0]
        features = [record.get(key, MISSING_SENTINEL) for key in EXPECTED_KEYS]
        features_array = np.array(features).reshape(1, -1)
        model = get_model()
        prediction = model.predict(features_array)

        return {"prediction": int(prediction[0]), "patient": data.patient}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
