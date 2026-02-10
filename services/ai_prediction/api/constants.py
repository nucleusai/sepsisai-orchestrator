"""
Feature lists used by the prediction model.

The order matters — it must match the order the model was trained on.
"""

LAB_ATTRIBUTES = [
    "pH", "PaCO2", "AST", "BUN", "Alkalinephos", "Chloride", "Creatinine",
    "Lactate", "Magnesium", "Potassium", "Bilirubin_total", "PTT", "WBC",
    "Fibrinogen", "Platelets",
]

VITAL_ATTRIBUTES = [
    "HR", "O2Sat", "Temp", "SBP", "MAP", "DBP", "Resp", "EtCO2",
]

DEMOGRAPHIC_ATTRIBUTES = [
    "Age", "ICULOS", "Gender",
]

# Combined feature vector expected by the model (26 features)
EXPECTED_KEYS = LAB_ATTRIBUTES + VITAL_ATTRIBUTES + DEMOGRAPHIC_ATTRIBUTES
