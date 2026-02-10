FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Input PSV files are mounted at /input_data (read-only).
# Intermediate CSVs are written to /output_data.
RUN mkdir -p /input_data /output_data

CMD ["python", "-u", "main.py"]
