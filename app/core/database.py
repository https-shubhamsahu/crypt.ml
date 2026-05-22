import os
import sqlite3
import json
import threading
import uuid
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional

DB_FILE = "data/crypt_ml.db"
_lock = threading.Lock()

def get_db_connection() -> sqlite3.Connection:
    """Creates a connection to the SQLite database with dict row factory."""
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Initializes the database tables if they do not exist."""
    with _lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Table: orchestration_runs
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orchestration_runs (
            id TEXT PRIMARY KEY,
            transaction_id TEXT,
            account_id TEXT,
            amount REAL,
            final_score REAL,
            final_decision TEXT,
            reasoning TEXT,
            agent_results TEXT, -- JSON array
            timeline TEXT, -- JSON array
            messages TEXT, -- JSON array
            created_at TEXT
        )
        """)

        # Table: agent_decisions
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_decisions (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            agent_name TEXT,
            score REAL,
            confidence REAL,
            decision TEXT,
            reasoning TEXT,
            evidence TEXT, -- JSON
            tools_used TEXT, -- JSON
            execution_time_ms REAL,
            created_at TEXT
        )
        """)

        # Table: cases (replacing volatile CaseStore)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY,
            account_id TEXT,
            risk_score REAL,
            exposure_level TEXT,
            decision TEXT,
            details TEXT, -- JSON payload details
            status TEXT, -- OPEN, INVESTIGATING, ESCALATED, FILED, CLOSED
            created_at TEXT,
            updated_at TEXT
        )
        """)

        # Table: audit_log
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            action TEXT,
            actor TEXT,
            details TEXT, -- JSON
            created_at TEXT
        )
        """)

        conn.commit()
        conn.close()

# Database helper functions

def insert_orchestration_run(run: Dict[str, Any]) -> None:
    with _lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO orchestration_runs (
            id, transaction_id, account_id, amount, final_score, final_decision, reasoning, agent_results, timeline, messages, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run["id"],
            run["transaction_id"],
            run["account_id"],
            run["amount"],
            run["final_score"],
            run["final_decision"],
            run["reasoning"],
            json.dumps(run["agent_results"]),
            json.dumps(run["timeline"]),
            json.dumps(run["messages"]),
            run.get("created_at", datetime.now(UTC).isoformat())
        ))
        conn.commit()
        conn.close()

def get_orchestration_runs(limit: int = 50) -> List[Dict[str, Any]]:
    with _lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orchestration_runs ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        runs = []
        for row in rows:
            run = dict(row)
            run["agent_results"] = json.loads(run["agent_results"] or "[]")
            run["timeline"] = json.loads(run["timeline"] or "[]")
            run["messages"] = json.loads(run["messages"] or "[]")
            runs.append(run)
        return runs

def get_orchestration_run(run_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orchestration_runs WHERE id = ?", (run_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        run = dict(row)
        run["agent_results"] = json.loads(run["agent_results"] or "[]")
        run["timeline"] = json.loads(run["timeline"] or "[]")
        run["messages"] = json.loads(run["messages"] or "[]")
        return run

def insert_agent_decision(decision: Dict[str, Any]) -> None:
    with _lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO agent_decisions (
            id, run_id, agent_name, score, confidence, decision, reasoning, evidence, tools_used, execution_time_ms, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            decision.get("id", str(uuid.uuid4())),
            decision["run_id"],
            decision["agent_name"],
            decision["score"],
            decision["confidence"],
            decision["decision"],
            decision["reasoning"],
            json.dumps(decision.get("evidence", [])),
            json.dumps(decision.get("tools_used", [])),
            decision.get("execution_time_ms", 0.0),
            decision.get("created_at", datetime.now(UTC).isoformat())
        ))
        conn.commit()
        conn.close()

# Case Store Operations

def insert_case(case: Dict[str, Any]) -> None:
    with _lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO cases (
            id, account_id, risk_score, exposure_level, decision, details, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            case["id"],
            case["account_id"],
            case["risk_score"],
            case["exposure_level"],
            case["decision"],
            json.dumps(case.get("details", {})),
            case.get("status", "OPEN"),
            case.get("created_at", datetime.now(UTC).isoformat()),
            case.get("updated_at", datetime.now(UTC).isoformat())
        ))
        conn.commit()
        conn.close()

def update_case_status(case_id: str, status: str) -> bool:
    with _lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE cases SET status = ?, updated_at = ? WHERE id = ?", (
            status,
            datetime.now(UTC).isoformat(),
            case_id
        ))
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

def get_cases(limit: int = 100) -> List[Dict[str, Any]]:
    with _lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cases ORDER BY updated_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        cases = []
        for row in rows:
            case = dict(row)
            case["details"] = json.loads(case["details"] or "{}")
            cases.append(case)
        return cases

def get_case(case_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        case = dict(row)
        case["details"] = json.loads(case["details"] or "{}")
        return case

# Audit Log Operations

def insert_audit_entry(action: str, actor: str, details: Dict[str, Any]) -> None:
    with _lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO audit_log (id, action, actor, details, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            action,
            actor,
            json.dumps(details),
            datetime.now(UTC).isoformat()
        ))
        conn.commit()
        conn.close()
