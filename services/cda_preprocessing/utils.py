"""
Utility functions for PSV ↔ CSV conversion and data validation.
"""

import csv
import logging
import os
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Sentinel value used to represent missing data in the CSV / MongoDB pipeline.
MISSING_VALUE = -9999


def psv_to_csv(input_dir: str, output_dir: str) -> None:
    """
    Convert every ``*.psv`` file in *input_dir* to a CSV in *output_dir*.

    Additional columns added per row:
      - ``Paciente`` — filename stem (e.g. ``p000001``)
      - ``Hora``     — zero-based row index within the file
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    psv_files = sorted(input_path.glob("*.psv"))
    if not psv_files:
        logger.warning("No .psv files found in %s", input_dir)
        return

    for psv_file in psv_files:
        df = pd.read_csv(psv_file, sep="|")
        df = df.fillna(MISSING_VALUE)

        patient_name = psv_file.stem
        df["Hora"] = range(len(df))
        df["Paciente"] = patient_name

        out_file = output_path / f"{patient_name}.csv"
        df.to_csv(out_file, index=False)
        logger.info("  %s → %s (%d rows)", psv_file.name, out_file.name, len(df))


def validate_data(
    psv_dir: str,
    mongo_uri: str,
    db_name: str,
    collection_name: str,
) -> None:
    """
    Spot-check that every row in the source PSV files has a matching
    document in *collection_name*.  Raises on the first mismatch.
    """
    from pymongo import MongoClient  # local import to keep the dep optional

    client = MongoClient(mongo_uri)
    col = client[db_name][collection_name]

    psv_path = Path(psv_dir)
    total, matched = 0, 0

    for psv_file in sorted(psv_path.glob("*.psv")):
        patient_name = psv_file.stem
        with open(psv_file, "r") as fh:
            reader = csv.reader(fh, delimiter="|")
            headers = next(reader)
            hora = 0
            for row in reader:
                query: dict = {"Paciente": patient_name, "Hora": hora}
                for header, value in zip(headers, row):
                    query[header] = MISSING_VALUE if value == "NaN" else float(value)

                total += 1
                if col.find_one(query):
                    matched += 1
                else:
                    logger.warning("Mismatch for %s hora=%d", patient_name, hora)
                hora += 1

    logger.info("Validation: %d / %d rows matched.", matched, total)
