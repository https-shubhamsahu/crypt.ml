from __future__ import annotations
from typing import Dict, Optional
from app.core import database

class CaseStore:
    def __init__(self) -> None:
        pass

    def put(self, case_id: str, data: dict) -> None:
        case = {
            "id": case_id,
            "account_id": data.get("account_id", data.get("src_account", "unknown")),
            "risk_score": data.get("combined_risk_score", data.get("risk_score", 0.0)),
            "exposure_level": data.get("exposure_level", "Medium"),
            "decision": data.get("final_decision", data.get("decision", "REVIEW")),
            "details": data,
            "status": data.get("status", "OPEN"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at")
        }
        database.insert_case(case)
        database.insert_audit_entry("CREATE_CASE", "system", {"case_id": case_id, "account_id": case["account_id"]})

    def get(self, case_id: str) -> Optional[dict]:
        case = database.get_case(case_id)
        if not case:
            return None
        # Return in the original format expected by services/controllers
        res = dict(case["details"])
        res["status"] = case["status"]
        res["updated_at"] = case["updated_at"]
        return res

    def update(self, case_id: str, fields: dict) -> Optional[dict]:
        case = database.get_case(case_id)
        if not case:
            return None
        
        # If updating status
        if "status" in fields:
            database.update_case_status(case_id, fields["status"])
            database.insert_audit_entry("UPDATE_CASE_STATUS", "analyst", {"case_id": case_id, "status": fields["status"]})

        # Get updated case details
        updated_case = database.get_case(case_id)
        if not updated_case:
            return None
            
        details = dict(updated_case["details"])
        details.update(fields)
        
        # Save back updated details
        conn = database.get_db_connection()
        cursor = conn.cursor()
        import json
        with database._lock:
            cursor.execute("UPDATE cases SET details = ?, updated_at = ? WHERE id = ?", (
                json.dumps(details),
                database.datetime.now(database.UTC).isoformat(),
                case_id
            ))
            conn.commit()
            conn.close()

        res = dict(details)
        res["status"] = updated_case["status"]
        res["updated_at"] = updated_case["updated_at"]
        return res

    def list_recent(self, limit: int = 200) -> list[dict]:
        cases = database.get_cases(limit)
        records = []
        for case in cases:
            row = {"case_id": case["id"]}
            row.update(case["details"])
            row["status"] = case["status"]
            row["updated_at"] = case["updated_at"]
            records.append(row)
        return records

