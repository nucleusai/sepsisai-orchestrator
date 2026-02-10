"""
Smoke tests — verify all services respond after `docker compose up`.

Usage:
    pip install httpx pytest
    pytest tests/test_smoke.py -v

These tests assume the platform is running on localhost with default ports.
"""

import httpx
import pytest

AI_BASE = "http://localhost:8000"
DASHBOARD_BASE = "http://localhost:8501"


@pytest.fixture(scope="module")
def client():
    with httpx.Client(timeout=10) as c:
        yield c


class TestAIService:
    def test_health(self, client):
        r = client.get(f"{AI_BASE}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_docs_available(self, client):
        r = client.get(f"{AI_BASE}/docs")
        assert r.status_code == 200

    def test_patients_endpoint(self, client):
        r = client.get(f"{AI_BASE}/predict/patients")
        assert r.status_code == 200
        data = r.json()
        assert "patients" in data

    def test_predict_by_patient(self, client):
        """Try a prediction; 404 is acceptable if no data is loaded."""
        r = client.post(
            f"{AI_BASE}/predict/by-patient",
            json={"patient": "p000001", "hour": "1"},
        )
        assert r.status_code in (200, 404)


class TestDashboard:
    def test_responds(self, client):
        r = client.get(DASHBOARD_BASE)
        assert r.status_code == 200
