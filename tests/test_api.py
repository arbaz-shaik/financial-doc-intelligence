
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_get():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "Healthy"}

def test_add_company():
    response = client.post("/companies", json={
        "name": "Test Company", 
        "ticker": "TEST", 
        "sector":"Technology"})
    assert response.status_code == 200
    assert response.json() ["company"]["name"] == "Test Company"

def test_get_company():
    response = client.get("/companies/TEST")
    assert response.status_code == 200
    assert response.json() ["ticker"] == "TEST"


def test_company_not_found():
    response = client.get("/companies/XXXX")
    assert response.status_code == 404

def test_invalid_ticker():
    response = client.post("/companies", json ={"name": "Bad Company",
        "ticker": "TOOLONG",
        "sector": "Tech"})
    assert response.status_code == 422