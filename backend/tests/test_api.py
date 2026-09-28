from fastapi.testclient import TestClient

from app.main import app


def test_health_and_agents():
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["scope"] == "Procurement R1-R5"
        agents = client.get("/api/v1/agents/status")
        assert agents.status_code == 200
        assert {a["agent_id"] for a in agents.json()} == {"R1","R2","R3","R4","R5"}


def test_api_recommend_and_approval():
    with TestClient(app) as client:
        result = client.post("/api/v1/procurement/recommend/SKU-100")
        assert result.status_code == 200
        data = result.json()
        assert data["agent_id"] == "R4"
        decision = client.post(f"/api/v1/recommendations/{data['recommendation_id']}/decision", json={"decision":"APPROVED","reason":"test"})
        assert decision.status_code == 200
        assert decision.json()["status"] == "APPROVED"


def test_dashboard():
    with TestClient(app) as client:
        result = client.get("/api/v1/dashboard")
        assert result.status_code == 200
        data = result.json()
        assert "active_suppliers" in data
        assert len(data["agent_status"]) == 5
