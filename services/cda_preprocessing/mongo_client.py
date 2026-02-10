"""
MongoDB helper for the CDA preprocessing pipeline.

Responsibilities:
  - Import CSV records into the raw collection (DataPacientes).
  - Run the CDA grouping aggregation   → VisualizacionGrupos.
  - Run the SIRS / SOFA scoring pipeline → NewDataComplet.
"""

import json
import logging
import os
from pathlib import Path

import pandas as pd
from pymongo import MongoClient

logger = logging.getLogger(__name__)


class MongoHelper:
    """Thin wrapper around PyMongo for the CDA pipeline."""

    def __init__(self, uri: str, db_name: str, collection_name: str):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.col = self.db[collection_name]

    # -----------------------------------------------------------------
    # Step 2: import CSV files
    # -----------------------------------------------------------------
    def import_csv(self, csv_dir: str = "/output_data"):
        """Read every CSV in *csv_dir* and insert rows into MongoDB."""
        csv_path = Path(csv_dir)
        if not csv_path.is_dir():
            logger.warning("CSV directory not found: %s", csv_dir)
            return

        for csv_file in sorted(csv_path.glob("*.csv")):
            try:
                df = pd.read_csv(csv_file)
                records = json.loads(df.to_json(orient="records"))
                for rec in records:
                    rec["notificado"] = True
                self.col.insert_many(records)
                logger.info("  Imported %s (%d rows)", csv_file.name, len(records))
            except Exception:
                logger.exception("  Error importing %s", csv_file.name)

        count = self.col.count_documents({})
        logger.info("Total documents in %s: %d", self.col.name, count)

    # -----------------------------------------------------------------
    # Step 3: CDA group aggregation  → VisualizacionGrupos
    # -----------------------------------------------------------------
    def group_aggregation(self):
        """
        Re-organise flat patient rows into CDA sections:
          x0_header, x1_demographics, x2_Admission_details,
          x3_Vital_Signs, x4_Laboratory_values,
          x5_engineering_variables, x6_Result_Sepsis.
        Output collection: VisualizacionGrupos
        """
        pipeline = [
            # -- header --
            {"$addFields": {
                "x0_header": {
                    "ID": "$_id", "Hora": "$Hora",
                    "patient": "$Paciente", "notificado": True,
                },
            }},
            {"$project": {"_id": 0, "Hora": 0, "Paciente": 0}},

            # -- demographics --
            {"$addFields": {
                "x1_demographics": {
                    "Age": "$Age", "Gender": "$Gender",
                    "Unit_1": "$Unit1", "Unit_2": "$Unit2",
                },
            }},
            {"$project": {"Age": 0, "Gender": 0, "Unit1": 0, "Unit2": 0}},

            # -- admission details --
            {"$addFields": {
                "x2_Admission_details": {
                    "Hospital": "$Hospital",
                    "HospAdmTime": "$HospAdmTime",
                    "ICULOS": "$ICULOS",
                },
            }},
            {"$project": {"Hospital": 0, "HospAdmTime": 0, "ICULOS": 0}},

            # -- vital signs --
            {"$addFields": {
                "x3_Vital_Signs": {
                    "Heart_rate": "$HR", "Pulse_oximetry": "$O2Sat",
                    "Temperature": "$Temp", "Systolic_BP": "$SBP",
                    "Mean_arterial_pressure": "$MAP", "Diastolic_BP": "$DBP",
                    "Respiration_rate": "$Resp",
                    "End_tidal_carbon_dioxide": "$EtCO2",
                },
            }},
            {"$project": {
                "HR": 0, "O2Sat": 0, "Temp": 0, "SBP": 0,
                "MAP": 0, "DBP": 0, "Resp": 0, "EtCO2": 0,
            }},

            # -- laboratory values --
            {"$addFields": {
                "x4_Laboratory_values": {
                    "Excess_bicarbonate": "$BaseExcess",
                    "Bicarbonate": "$HCO3",
                    "Fraction_of_inspired_oxygen": "$FiO2",
                    "pH": "$pH",
                    "Partial_pressure_of_carbon_dioxide_from_arterial_blood": "$PaCO2",
                    "Oxygen_saturation_from_arterial_blood": "$SaO2",
                    "Aspartate_transaminase": "$AST",
                    "Blood_urea_nitrogen": "$BUN",
                    "Alkaline_phosphatase": "$Alkalinephos",
                    "Calcium": "$Calcium", "Chloride": "$Chloride",
                    "Creatinine": "$Creatinine",
                    "Direct_bilirubin": "$Bilirubin_direct",
                    "Serum_glucose": "$Glucose",
                    "Lactic_acid": "$Lactate", "Magnesium": "$Magnesium",
                    "Phosphate": "$Phosphate", "Potassium": "$Potassium",
                    "Total_bilirubin": "$Bilirubin_total",
                    "Troponin": "$TroponinI",
                    "Hematocrit": "$Hct", "Hemoglobin": "$Hgb",
                    "Partial_thromboplastin_time": "$PTT",
                    "Leukocyte_count": "$WBC",
                    "Fibrinogen_concentration": "$Fibrinogen",
                    "Platelet_count": "$Platelets",
                },
            }},
            {"$project": {
                "BaseExcess": 0, "HCO3": 0, "FiO2": 0, "pH": 0,
                "PaCO2": 0, "SaO2": 0, "AST": 0, "BUN": 0,
                "Alkalinephos": 0, "Calcium": 0, "Chloride": 0,
                "Creatinine": 0, "Bilirubin_direct": 0, "Glucose": 0,
                "Lactate": 0, "Magnesium": 0, "Phosphate": 0,
                "Potassium": 0, "Bilirubin_total": 0, "TroponinI": 0,
                "Hct": 0, "Hgb": 0, "PTT": 0, "WBC": 0,
                "Fibrinogen": 0, "Platelets": 0, "notificado": 0,
            }},

            # -- engineering variables --
            {"$addFields": {
                "x5_engineering_variables": {
                    "HR_SIRS": "$HR_SIRS",
                    "TEMP_SIRS": "$TEMP_SIRS",
                    "WBC_SIRS": "$WBC_SIRS",
                },
            }},
            {"$project": {"HR_SIRS": 0, "TEMP_SIRS": 0, "WBC_SIRS": 0}},

            # -- sepsis results --
            {"$addFields": {
                "x6_Result_Sepsis": {
                    "SepsisLabel": "$SepsisLabel",
                    "Sepsis_SOFA": "$Sepsis_SOFA",
                    "Sepsis_SIRS": "$Sepsis_SIRS",
                },
            }},
            {"$project": {"SepsisLabel": 0, "Sepsis_SOFA": 0, "Sepsis_SIRS": 0}},

            {"$out": "VisualizacionGrupos"},
        ]
        list(self.col.aggregate(pipeline))

    # -----------------------------------------------------------------
    # Step 4: SIRS / SOFA scoring  → NewDataComplet
    # -----------------------------------------------------------------
    def aggregation_variables(self):
        """
        Calculate SIRS and SOFA component scores from raw vitals/labs
        and write the enriched records to **NewDataComplet**.
        """
        pipeline = [
            # ── First stage: binary SIRS flags + Respiracion ratio ──
            {"$addFields": {
                "notificado": False,
                "HR_SIRS": {"$switch": {"branches": [
                    {"case": {"$eq": ["$HR", 0]}, "then": 0},
                    {"case": {"$and": [{"$gte": ["$HR", 60.0]}, {"$lte": ["$HR", 100.0]}]}, "then": 0},
                ], "default": 1}},
                "TEMP_SIRS": {"$switch": {"branches": [
                    {"case": {"$eq": ["$Temp", 0]}, "then": 0},
                    {"case": {"$and": [{"$gte": ["$Temp", 36.0]}, {"$lte": ["$Temp", 38.3]}]}, "then": 0},
                ], "default": 1}},
                "WBC_SIRS": {"$switch": {"branches": [
                    {"case": {"$eq": ["$WBC", 0]}, "then": 0},
                    {"case": {"$and": [{"$gte": ["$WBC", 4.0]}, {"$lte": ["$WBC", 12.0]}]}, "then": 0},
                ], "default": 1}},
                "Respiracion": {"$switch": {"branches": [
                    {"case": {"$eq": ["$FiO2", 0]}, "then": "No valido"},
                    {"case": {"$ne": ["$FiO2", 0]}, "then": {"$divide": ["$SaO2", "$FiO2"]}},
                ]}},
            }},

            # ── Second stage: SOFA component scores (0-4 each) ──────
            {"$addFields": {
                "Respiracion_SOFA": {"$switch": {"branches": [
                    {"case": {"$eq": ["$Respiracion", "No valido"]}, "then": 0},
                    {"case": {"$eq": ["$Respiracion", "N.A"]}, "then": 0},
                    {"case": {"$gte": ["$Respiracion", 400]}, "then": 0},
                    {"case": {"$and": [{"$gt": ["$Respiracion", 300]}, {"$lt": ["$Respiracion", 400]}]}, "then": 1},
                    {"case": {"$and": [{"$gt": ["$Respiracion", 200]}, {"$lt": ["$Respiracion", 300]}]}, "then": 2},
                    {"case": {"$and": [{"$gt": ["$Respiracion", 100]}, {"$lt": ["$Respiracion", 200]}]}, "then": 3},
                    {"case": {"$and": [{"$gt": ["$Respiracion", 1]}, {"$lt": ["$Respiracion", 100]}]}, "then": 4},
                ], "default": 0}},
                "Platelets_SOFA": {"$switch": {"branches": [
                    {"case": {"$eq": ["$Platelets", 0]}, "then": 0},
                    {"case": {"$gte": ["$Platelets", 150]}, "then": 0},
                    {"case": {"$and": [{"$gt": ["$Platelets", 100]}, {"$lt": ["$Platelets", 150]}]}, "then": 1},
                    {"case": {"$and": [{"$gt": ["$Platelets", 50]}, {"$lt": ["$Platelets", 100]}]}, "then": 2},
                    {"case": {"$and": [{"$gt": ["$Platelets", 20]}, {"$lt": ["$Platelets", 50]}]}, "then": 3},
                    {"case": {"$and": [{"$gt": ["$Platelets", 1]}, {"$lt": ["$Platelets", 20]}]}, "then": 4},
                ], "default": 0}},
                "Bilirubin_total_SOFA": {"$switch": {"branches": [
                    {"case": {"$eq": ["$Bilirubin_total", 0]}, "then": 0},
                    {"case": {"$lt": ["$Bilirubin_total", 1.2]}, "then": 0},
                    {"case": {"$and": [{"$gt": ["$Bilirubin_total", 1.2]}, {"$lt": ["$Bilirubin_total", 2.0]}]}, "then": 1},
                    {"case": {"$and": [{"$gt": ["$Bilirubin_total", 2.0]}, {"$lt": ["$Bilirubin_total", 6.0]}]}, "then": 2},
                    {"case": {"$and": [{"$gt": ["$Bilirubin_total", 6.0]}, {"$lt": ["$Bilirubin_total", 12.0]}]}, "then": 3},
                    {"case": {"$gt": ["$Bilirubin_total", 12.0]}, "then": 4},
                ], "default": 0}},
                "MAP_SOFA": {"$switch": {"branches": [
                    {"case": {"$eq": ["$MAP", 0]}, "then": 0},
                    {"case": {"$gt": ["$MAP", 70]}, "then": 0},
                    {"case": {"$lt": ["$MAP", 70]}, "then": 1},
                ], "default": 0}},
                "Creatinine_SOFA": {"$switch": {"branches": [
                    {"case": {"$eq": ["$Creatinine", 0]}, "then": 0},
                    {"case": {"$lt": ["$Creatinine", 1.2]}, "then": 0},
                    {"case": {"$and": [{"$gte": ["$Creatinine", 1.2]}, {"$lt": ["$Creatinine", 2.0]}]}, "then": 1},
                    {"case": {"$and": [{"$gte": ["$Creatinine", 2.0]}, {"$lt": ["$Creatinine", 3.4]}]}, "then": 2},
                    {"case": {"$and": [{"$gte": ["$Creatinine", 3.4]}, {"$lt": ["$Creatinine", 5.0]}]}, "then": 3},
                    {"case": {"$gte": ["$Creatinine", 5.0]}, "then": 4},
                ], "default": 0}},
            }},

            # ── Third stage: project all fields + compute Sepsis_SIRS ─
            {"$project": {
                "_id": 1, "notificado": 1,
                "Paciente": 1, "Hora": 1, "Hospital": 1,
                # vitals
                "HR": 1, "Temp": 1, "WBC": 1, "O2Sat": 1,
                "SBP": 1, "MAP": 1, "DBP": 1, "Resp": 1, "EtCO2": 1,
                # labs
                "BaseExcess": 1, "HCO3": 1, "FiO2": 1, "pH": 1,
                "PaCO2": 1, "SaO2": 1, "AST": 1, "BUN": 1,
                "Alkalinephos": 1, "Calcium": 1, "Chloride": 1,
                "Creatinine": 1, "Bilirubin_direct": 1, "Glucose": 1,
                "Lactate": 1, "Magnesium": 1, "Phosphate": 1,
                "Potassium": 1, "Bilirubin_total": 1, "TroponinI": 1,
                "Hct": 1, "Hgb": 1, "PTT": 1, "Fibrinogen": 1,
                "Platelets": 1,
                # demographics
                "Age": 1, "Gender": 1, "Unit1": 1, "Unit2": 1,
                "HospAdmTime": 1, "ICULOS": 1,
                # calculated scores
                "HR_SIRS": 1, "TEMP_SIRS": 1, "WBC_SIRS": 1,
                "Respiracion": 1,
                "Respiracion_SOFA": 1, "Platelets_SOFA": 1,
                "Bilirubin_total_SOFA": 1, "MAP_SOFA": 1,
                "Creatinine_SOFA": 1,
                "SepsisLabel": 1,
                # Sepsis_SIRS = 1 when ≥ 2 of the 3 SIRS criteria are met
                "Sepsis_SIRS": {"$cond": [
                    {"$or": [
                        {"$and": [{"$eq": ["$HR_SIRS", 1]}, {"$eq": ["$TEMP_SIRS", 1]}]},
                        {"$and": [{"$eq": ["$HR_SIRS", 1]}, {"$eq": ["$WBC_SIRS", 1]}]},
                        {"$and": [{"$eq": ["$TEMP_SIRS", 1]}, {"$eq": ["$WBC_SIRS", 1]}]},
                    ]},
                    "1", "0",
                ]},
            }},

            {"$out": "NewDataComplet"},
        ]
        list(self.col.aggregate(pipeline))
