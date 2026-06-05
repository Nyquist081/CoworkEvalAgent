from fastapi.testclient import TestClient


def test_health_endpoint():
    from src.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_prefix():
    from src.main import app
    client = TestClient(app)
    # Test that router is mounted at /coworkeval/v1
    response = client.get("/coworkeval/v1/runs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_manifests_endpoint():
    from src.main import app
    client = TestClient(app)
    response = client.get("/coworkeval/v1/manifests")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
