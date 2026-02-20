from app.services.agentic_aml import AMLOrchestratorA2A


def test_agentic_pipeline_basic_decision() -> None:
    orchestrator = AMLOrchestratorA2A()

    txn = {
        "transaction_id": "TXN_DEMO_1",
        "amount": 82000,
        "src_account": "acct_1001",
        "dst_account": "acct_2002",
        "tx_count_last_hour": 8,
        "transaction_note": "urgent mule transfer",
        "country": "high-risk",
        "channel": "Wire",
    }

    result = orchestrator.process(txn)

    assert result.transaction_id == "TXN_DEMO_1"
    assert result.final_decision in {"ALLOW", "REVIEW", "ESCALATE", "BLOCK"}
    assert 0.0 <= result.combined_risk_score <= 1.0
    assert 0.0 <= result.raw_decision.risk_score <= 1.0
    assert 0.0 <= result.sar_decision.ensemble_score <= 1.0
