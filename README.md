# SepsisAI-Orchestrator

A containerized, scalable platform for deploying AI models and real-time monitoring in early sepsis detection.


SepsisAI-Orchestrator is an open-source, containerized platform for deploying and scaling clinical AI models. It standardizes heterogeneous EHR data using an CDA preprocessing service, stores structured data in a NoSQL database, serves AI inference through REST APIs, and provides real-time visualization via a web dashboard. The platform is built with Docker and orchestrated with Kubernetes to enable horizontal scaling, fault tolerance, and reproducible deployments, and has been validated under high concurrency using k6 load testing.

---

## Architecture

The platform implements three sequential stages as independent containerized services:

```
 ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
 │  1. CDA       │      │  2. AI        │      │  3. Monitoring │
 │  Preprocessing│─────▶│  Prediction   │◀────▶│  Dashboard     │
 │  Service      │      │  Service      │      │  (Streamlit)   │
 └───────┬───────┘      └───────┬───────┘      └───────┬───────┘
         │                      │                      │
         ▼                      ▼                      ▼
    ┌─────────────────────────────────────────────────────┐
    │                   MongoDB (NoSQL)                   │
    └─────────────────────────────────────────────────────┘
```

| Service | Description | Port |
|---------|-------------|------|
| **CDA Preprocessing** | Converts PSV patient files into HL7 FHIR-inspired CDA structures; calculates SIRS & SOFA scores; stores in MongoDB | Run-once job |
| **AI Prediction** | FastAPI + LightGBM model; REST endpoints for real-time sepsis inference | `8000` |
| **Dashboard** | Streamlit clinical interface; vital signs, lab data, scores, AI query | `8501` |
| **MongoDB** | NoSQL data layer shared by all services | `27017` |

---

## Quick Start (Docker Compose)

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (v20+) and Docker Compose v2
- At least one `.psv` file from the [PhysioNet/CinC 2019 Challenge](https://physionet.org/content/challenge-2019/1.0.0/) dataset

### 1. Clone & configure

```bash
git clone https://github.com/your-org/sepsisai-orchestrator.git
cd sepsisai-orchestrator
cp .env.example .env
```

### 2. Add patient data

Two small sample files (`p000001.psv`, `p000002.psv`) are included for quick testing. For realistic evaluation, copy additional PSV files:

```bash
cp /path/to/training_setA/p00*.psv data/sample/
```

### 3. Build

```bash
docker compose build
```

### 4. Seed the database

This runs the CDA preprocessing pipeline once and exits:

```bash
docker compose run --rm cda-preprocessing
```

### 5. Start the platform

```bash
docker compose up -d
```

### 6. Open

| URL | Service |
|-----|---------|
| [http://localhost:8501](http://localhost:8501) | Clinical Dashboard |
| [http://localhost:8000/docs](http://localhost:8000/docs) | AI API (Swagger UI) |
| [http://localhost:8000/health](http://localhost:8000/health) | Health check |

### 7. Stop

```bash
docker compose down -v
```

---

## Project Structure

```
sepsisai-orchestrator/
├── docker-compose.yml          # Single entry-point for the whole platform
├── .env.example                # Environment variable template
├── Makefile                    # Developer shortcuts (make up, make seed, …)
│
├── services/
│   ├── cda_preprocessing/      # Stage 1: PSV → CDA → MongoDB
│   │   ├── main.py             #   Pipeline entry-point
│   │   ├── mongo_client.py     #   MongoDB operations & aggregation
│   │   ├── utils.py            #   PSV/CSV conversion helpers
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── ai_prediction/          # Stage 2: FastAPI + LightGBM
│   │   ├── main.py             #   FastAPI app with /health endpoint
│   │   ├── api/
│   │   │   ├── prediction.py   #   REST endpoints (/predict, /predict/by-patient)
│   │   │   └── constants.py    #   Feature lists (26 model features)
│   │   ├── database/
│   │   │   └── mongo.py        #   MongoDB connection singleton
│   │   ├── models/
│   │   │   └── model_loader.py #   Thread-safe model loading
│   │   ├── schemas/
│   │   │   └── prediction_schemas.py
│   │   ├── services/
│   │   │   └── prediction_service.py
│   │   ├── model_store/
│   │   │   └── gbdt_model.pkl  #   Pre-trained LightGBM model
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── dashboard/              # Stage 3: Streamlit clinical UI
│       ├── app.py              #   Dashboard with 5 tabs + real-time alerts
│       ├── Dockerfile
│       └── requirements.txt
│
├── k8s/                        # Kubernetes manifests (scalable architecture)
│   ├── namespace.yaml
│   ├── configmap.yaml          #   Shared environment variables
│   ├── mongo-statefulset.yaml
│   ├── mongo-service.yaml
│   ├── cda-job.yaml            #   K8s Job (run-once)
│   ├── ai-deployment.yaml      #   Deployment (3 replicas default)
│   ├── ai-service.yaml         #   NodePort :30001
│   ├── dashboard-deployment.yaml
│   └── dashboard-service.yaml  #   NodePort :30003
│
├── data/sample/                # Sample PSV files for testing
├── scripts/seed_data.sh        # Convenience seed script
├── tests/                      # Smoke tests
├── paper/                      # Research paper
└── third_party/                # Original source repositories (reference)
```

---

## API Reference

The AI Prediction Service exposes these endpoints (full Swagger docs at `/docs`):

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness / readiness probe |
| `POST` | `/predict` | Predict from a full 26-feature JSON body |
| `POST` | `/predict/by-patient` | Predict by patient ID + hour (fetches from MongoDB) |
| `POST` | `/predict/reload-model` | Hot-reload a different `.pkl` model |
| `GET` | `/predict/patients` | List available patient IDs |

### Example: predict by patient

```bash
curl -X POST http://localhost:8000/predict/by-patient \
  -H "Content-Type: application/json" \
  -d '{"patient": "p000001", "hour": "1"}'
```

---

## Deploying with Kubernetes

For production-grade deployments with horizontal scaling:

```bash
# 1. Build and tag images
docker build -t sepsisai/cda-preprocessing:latest services/cda_preprocessing/
docker build -t sepsisai/ai-prediction:latest     services/ai_prediction/
docker build -t sepsisai/dashboard:latest          services/dashboard/

# 2. Push to your registry (optional)
# docker push sepsisai/ai-prediction:latest  ...

# 3. Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/mongo-statefulset.yaml
kubectl apply -f k8s/mongo-service.yaml
kubectl apply -f k8s/cda-job.yaml
kubectl apply -f k8s/ai-deployment.yaml
kubectl apply -f k8s/ai-service.yaml
kubectl apply -f k8s/dashboard-deployment.yaml
kubectl apply -f k8s/dashboard-service.yaml

# 4. Scale the AI service (match to CPU thread count for optimal throughput)
kubectl scale deployment ai-prediction -n sepsisai --replicas=12

# 5. Access
kubectl get svc -n sepsisai
# Dashboard at NodePort :30003, AI API at NodePort :30001
```

---

## Replacing the AI Model

To use a different model:

1. Train your model and export it with `joblib.dump(model, "my_model.pkl")`
2. Ensure it accepts the same 26 features (see `services/ai_prediction/api/constants.py`)
3. Either:
   - **Replace the file:** copy `my_model.pkl` into `services/ai_prediction/model_store/gbdt_model.pkl` and rebuild
   - **Hot-reload at runtime:** `POST /predict/reload-model?path=/app/model_store/my_model.pkl`

---

## Configuration

All services read from environment variables. See [`.env.example`](.env.example) for the full list:

| Variable | Default | Used by |
|----------|---------|---------|
| `MONGO_HOST` | `mongo` | All services |
| `MONGO_PORT` | `27017` | All services |
| `MONGO_DB` | `SepsisTraining` | All services |
| `AI_SERVICE_HOST` | `ai-prediction` | Dashboard |
| `AI_SERVICE_PORT` | `8000` | Dashboard |
| `INPUT_DATA_DIR` | `/input_data` | CDA Preprocessing |
| `OUTPUT_DATA_DIR` | `/output_data` | CDA Preprocessing |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-change`
3. Make changes in the relevant `services/` directory
4. Test locally: `docker compose build && docker compose up`
5. Open a Pull Request

### Developer shortcuts

```bash
make help       # Show all available commands
make build      # Build all Docker images
make up         # Start the platform
make seed       # Load sample data
make logs       # Tail all service logs
make test       # Quick smoke test
make down       # Stop everything
```

---

## References

- Ospitia, S., Sanabria, J., & Garcia-Henao, J. (2026). *A Containerized and Scalable Platform for Deploying AI Models and Real-Time Monitoring in Early Sepsis Detection.*
- Toro Beltran et al. (2022). *A Machine Learning-Based Missing Data Imputation with FHIR Interoperability Approach in Sepsis Prediction.* Springer CCIS.
- Reyna et al. (2020). *Early Prediction of Sepsis from Clinical Data: The PhysioNet/CinC Challenge 2019.* Critical Care Medicine.

## License

See [LICENSE](LICENSE).
