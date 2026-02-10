"""
CDA Preprocessing Service — entry point.

Pipeline:
  1. Convert PSV files to CSV  (utils.psv_to_csv)
  2. Import CSV records into MongoDB  (mongo_client.import_csv)
  3. Build the CDA-grouped collection  (mongo_client.group_aggregation)
  4. Calculate SIRS / SOFA scores  (mongo_client.aggregation_variables)
  5. (Optional) Validate data consistency  (utils.validate_data)
"""

import logging
import os
import sys

from dotenv import load_dotenv

from mongo_client import MongoHelper
from utils import psv_to_csv, validate_data

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    # ── Configuration (all via env vars, see .env.example) ────────────
    mongo_host = os.getenv("MONGO_HOST", "localhost")
    mongo_port = os.getenv("MONGO_PORT", "27017")
    mongo_db = os.getenv("MONGO_DB", "SepsisTraining")

    input_dir = os.getenv("INPUT_DATA_DIR", "/input_data")
    output_dir = os.getenv("OUTPUT_DATA_DIR", "/output_data")

    mongo_uri = f"mongodb://{mongo_host}:{mongo_port}"

    # ── Step 1: PSV → CSV ────────────────────────────────────────────
    logger.info("Step 1/4 — Converting PSV files to CSV …")
    if not os.path.isdir(input_dir):
        logger.error("Input directory does not exist: %s", input_dir)
        sys.exit(1)
    psv_to_csv(input_dir, output_dir)
    logger.info("PSV → CSV conversion complete.")

    # ── Step 2: CSV → MongoDB ────────────────────────────────────────
    logger.info("Step 2/4 — Importing CSV into MongoDB …")
    mongo = MongoHelper(mongo_uri, mongo_db, "DataPacientes")
    mongo.import_csv(output_dir)
    logger.info("CSV import complete.")

    # ── Step 3: CDA grouping aggregation ─────────────────────────────
    logger.info("Step 3/4 — Running CDA group aggregation …")
    mongo.group_aggregation()
    logger.info("CDA grouping complete → collection 'VisualizacionGrupos'.")

    # ── Step 4: SIRS / SOFA scoring aggregation ──────────────────────
    logger.info("Step 4/4 — Calculating SIRS & SOFA scores …")
    mongo.aggregation_variables()
    logger.info("Scoring complete → collection 'NewDataComplet'.")

    # ── Optional: data consistency check ─────────────────────────────
    if os.getenv("VALIDATE_DATA", "").lower() in ("1", "true", "yes"):
        logger.info("Running data validation …")
        validate_data(input_dir, mongo_uri, mongo_db, "NewDataComplet")
        logger.info("Validation finished.")

    logger.info("CDA preprocessing pipeline finished successfully.")


if __name__ == "__main__":
    main()
