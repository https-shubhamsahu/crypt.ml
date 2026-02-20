from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_scam_exposure_endpoint() -> None:
    payload = {
        "account_id": "acct_1001",
        "upi_id": "user@upi",
        "transaction_amount": 62000,
        "tx_count_last_hour": 7,
        "transaction_note": "urgent cashout to mule wallet",
    }

    response = client.post("/api/v1/scam-exposure", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert "risk_score" in body
    assert "trust_score" in body
    assert "case_id" in body
    assert "weights_used" in body
    assert "orchestrator_trace" in body
    assert "analyst_decision" in body
    assert body["exposure_level"] in {"Low", "Medium", "High"}
    assert "raw" in body["risk_breakdown"]
    assert "ml" in body["risk_breakdown"]
    assert "graph" in body["risk_breakdown"]
    assert isinstance(body["risk_breakdown"]["raw"]["contributions"], dict)


def test_feedback_recalibration_loop() -> None:
    initial_weights_response = client.get("/api/v1/weights")
    assert initial_weights_response.status_code == 200
    initial_weights = initial_weights_response.json()["weights"]

    run_payload = {
        "account_id": "acct_1001",
        "upi_id": "user@upi",
        "transaction_amount": 62000,
        "tx_count_last_hour": 7,
        "transaction_note": "possible mule ring transfer",
    }
    scan_response = client.post("/api/v1/scam-exposure", json=run_payload)
    assert scan_response.status_code == 200
    case_id = scan_response.json()["case_id"]

    feedback_response = client.post(
        "/api/v1/feedback",
        json={"case_id": case_id, "outcome": "confirmed_fraud", "notes": "Analyst validated mule behavior."},
    )
    assert feedback_response.status_code == 200
    body = feedback_response.json()
    assert body["status"] == "updated"

    updated_weights = body["updated_weights"]
    assert updated_weights["graph"] != initial_weights["graph"] or updated_weights["ml"] != initial_weights["ml"]
