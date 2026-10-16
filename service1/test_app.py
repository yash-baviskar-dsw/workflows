from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()

    assert data["service"] == "service1"
    assert data["version"] == "0.1.9"
    assert data["status"] == "healthy"


def test_info():
    response = client.get("/info")

    assert response.status_code == 200

    data = response.json()

    assert data["service"] == "service1"
    assert data["environment"] == "dev"
