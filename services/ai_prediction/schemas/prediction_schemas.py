"""Pydantic models for request / response validation."""

from pydantic import BaseModel


class PredictionRequest(BaseModel):
    """Full feature vector sent directly in the request body."""

    # Vital signs
    HR: float
    O2Sat: float
    Temp: float
    SBP: float
    MAP: float
    DBP: float
    Resp: float
    EtCO2: float

    # Laboratory results
    pH: float
    PaCO2: float
    AST: float
    BUN: float
    Alkalinephos: float
    Chloride: float
    Creatinine: float
    Lactate: float
    Magnesium: float
    Potassium: float
    Bilirubin_total: float
    PTT: float
    WBC: float
    Fibrinogen: float
    Platelets: float

    # Demographics
    Age: float
    ICULOS: float
    Gender: float


class PatientHourRequest(BaseModel):
    """Identify a patient record in MongoDB by patient ID and hour."""

    patient: str
    hour: str


class PredictionResponse(BaseModel):
    """Prediction result returned to the client."""

    prediction: int
    patient: str
