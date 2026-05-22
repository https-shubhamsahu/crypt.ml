"""
Synthetic Training Data Generator for crypt.ml.

Generates realistic AML/fraud transaction CSV data in three supported schemas:
  1. Unified  — direct model features (transaction_amount, tx_count_last_hour, has_upi, nlp_signal, label)
  2. PaySim  — mirrors Kaggle PaySim format (step, type, amount, nameOrig, oldbalanceOrg, …, isFraud)
  3. AML-CFT — IBM AML-CFT / India VDA format (Time, Date, Sender_account, …, Is_laundering)

Each schema produces configurable row counts and fraud ratios with controlled randomness
so the data is reproducible (seed-based) yet statistically diverse.
"""
from __future__ import annotations

import hashlib
import random
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import List, Optional

import pandas as pd


# ── Configuration ────────────────────────────────────────────────────────────

SCHEMA_UNIFIED = "unified"
SCHEMA_PAYSIM = "paysim"
SCHEMA_AML_CFT = "aml_cft"

SUPPORTED_SCHEMAS = [SCHEMA_UNIFIED, SCHEMA_PAYSIM, SCHEMA_AML_CFT]

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data"

# Risk lexicon terms used for NLP signal generation
_SUSPICIOUS_PHRASES = [
    "urgent cashout to mule wallet",
    "bypass otp verification immediately",
    "untraceable crypto transfer",
    "fake identity giftcard purchase",
    "mule ring cross-border laundering",
    "cash deposit layering via shell company",
    "fan_out to multiple accounts",
    "cross-border hawala transfer",
]
_BENIGN_PHRASES = [
    "regular salary transfer",
    "monthly rent payment",
    "grocery store purchase",
    "utility bill payment",
    "subscription renewal",
    "friend dinner split",
    "savings deposit",
    "loan EMI payment",
]

_PAYMENT_TYPES = ["Cross-border", "Cash deposit", "Cheque", "ACH", "Credit Card", "Debit Card", "Wire"]
_CURRENCIES = ["USD", "EUR", "INR", "GBP", "AED", "SGD", "JPY", "CNY"]
_COUNTRIES = ["US", "UK", "IN", "DE", "SG", "AE", "HK", "CH", "NL", "KY"]
_LAUNDERING_TYPES = ["", "Fan_out", "Fan_in", "Layering", "Cross-border Group", "Round-trip", "Shell Company"]


@dataclass
class GeneratorConfig:
    """Configuration for synthetic data generation."""
    num_rows: int = 1000
    fraud_ratio: float = 0.15
    schema: str = SCHEMA_AML_CFT
    seed: int = 42
    # PaySim / AML-CFT specific
    num_accounts: int = 200
    start_date: str = "2025-01-01"
    days_span: int = 90

    def __post_init__(self) -> None:
        if self.schema not in SUPPORTED_SCHEMAS:
            raise ValueError(f"schema must be one of {SUPPORTED_SCHEMAS}, got '{self.schema}'")
        self.num_rows = max(20, self.num_rows)
        self.fraud_ratio = max(0.01, min(0.95, self.fraud_ratio))
        self.num_accounts = max(10, self.num_accounts)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _rand_account_id(rng: random.Random, prefix: str = "acct") -> str:
    return f"{prefix}_{rng.randint(1000, 999999):06d}"


def _rand_upi(rng: random.Random) -> str:
    name = "".join(rng.choices(string.ascii_lowercase, k=rng.randint(4, 8)))
    bank = rng.choice(["upi", "paytm", "gpay", "phonepe"])
    return f"{name}@{bank}"


def _rand_date(rng: random.Random, start: datetime, days: int) -> datetime:
    offset = timedelta(
        days=rng.randint(0, max(0, days - 1)),
        hours=rng.randint(0, 23),
        minutes=rng.randint(0, 59),
        seconds=rng.randint(0, 59),
    )
    return start + offset


# ── Schema Generators ────────────────────────────────────────────────────────


def generate_unified(config: GeneratorConfig) -> pd.DataFrame:
    """Generate data in the unified model-ready schema."""
    rng = random.Random(config.seed)
    fraud_count = int(config.num_rows * config.fraud_ratio)
    legit_count = config.num_rows - fraud_count

    rows: list[dict] = []

    # Fraudulent transactions
    for _ in range(fraud_count):
        rows.append({
            "transaction_amount": round(rng.uniform(25_000, 500_000), 2),
            "tx_count_last_hour": rng.randint(5, 25),
            "has_upi": rng.choice([0, 1]),
            "nlp_signal": round(rng.uniform(30, 100), 2),
            "label": 1,
            "transaction_note": rng.choice(_SUSPICIOUS_PHRASES),
        })

    # Legitimate transactions
    for _ in range(legit_count):
        rows.append({
            "transaction_amount": round(rng.uniform(100, 50_000), 2),
            "tx_count_last_hour": rng.randint(0, 4),
            "has_upi": rng.choice([0, 1]),
            "nlp_signal": round(rng.uniform(0, 25), 2),
            "label": 0,
            "transaction_note": rng.choice(_BENIGN_PHRASES),
        })

    rng.shuffle(rows)
    return pd.DataFrame(rows)


def generate_paysim(config: GeneratorConfig) -> pd.DataFrame:
    """Generate data in PaySim-compatible schema."""
    rng = random.Random(config.seed)
    fraud_count = int(config.num_rows * config.fraud_ratio)
    legit_count = config.num_rows - fraud_count
    tx_types = ["PAYMENT", "TRANSFER", "CASH_OUT", "DEBIT", "CASH_IN"]

    accounts = [_rand_account_id(rng, "C") for _ in range(config.num_accounts)]
    merchants = [_rand_account_id(rng, "M") for _ in range(max(20, config.num_accounts // 5))]

    rows: list[dict] = []

    for is_fraud in ([1] * fraud_count + [0] * legit_count):
        sender = rng.choice(accounts)
        receiver = rng.choice(merchants) if rng.random() < 0.6 else rng.choice(accounts)
        step = rng.randint(1, 744)  # hour within a month

        if is_fraud:
            amount = round(rng.uniform(50_000, 1_000_000), 2)
            tx_type = rng.choice(["TRANSFER", "CASH_OUT"])
            old_bal_orig = round(rng.uniform(amount * 0.8, amount * 2), 2)
            new_bal_orig = round(old_bal_orig - amount, 2)
            note = rng.choice(_SUSPICIOUS_PHRASES)
        else:
            amount = round(rng.uniform(50, 80_000), 2)
            tx_type = rng.choice(tx_types)
            old_bal_orig = round(rng.uniform(amount, amount * 10), 2)
            new_bal_orig = round(old_bal_orig - amount, 2)
            note = rng.choice(_BENIGN_PHRASES)

        old_bal_dest = round(rng.uniform(0, 500_000), 2)
        new_bal_dest = round(old_bal_dest + amount, 2)

        rows.append({
            "step": step,
            "type": tx_type,
            "amount": amount,
            "nameOrig": sender,
            "oldbalanceOrg": max(0, old_bal_orig),
            "newbalanceOrig": max(0, new_bal_orig),
            "nameDest": receiver,
            "oldbalanceDest": old_bal_dest,
            "newbalanceDest": new_bal_dest,
            "isFraud": is_fraud,
            "isFlaggedFraud": 1 if is_fraud and amount > 200_000 else 0,
            "transaction_note": note,
        })

    rng.shuffle(rows)
    return pd.DataFrame(rows)


def generate_aml_cft(config: GeneratorConfig) -> pd.DataFrame:
    """Generate data in AML-CFT / India VDA schema."""
    rng = random.Random(config.seed)
    fraud_count = int(config.num_rows * config.fraud_ratio)
    legit_count = config.num_rows - fraud_count
    start_dt = datetime.strptime(config.start_date, "%Y-%m-%d")

    accounts = [_rand_account_id(rng, "SA") for _ in range(config.num_accounts)]

    rows: list[dict] = []

    for is_fraud in ([1] * fraud_count + [0] * legit_count):
        dt = _rand_date(rng, start_dt, config.days_span)
        sender = rng.choice(accounts)
        receiver = rng.choice([a for a in accounts if a != sender]) if len(accounts) > 1 else sender

        if is_fraud:
            amount = round(rng.uniform(100_000, 5_000_000), 2)
            pay_currency = rng.choice(_CURRENCIES)
            recv_currency = rng.choice(_CURRENCIES)  # may differ → cross-currency
            sender_loc = rng.choice(_COUNTRIES)
            receiver_loc = rng.choice([c for c in _COUNTRIES if c != sender_loc])  # cross-border
            payment_type = rng.choice(["Cross-border", "Cash deposit", "Wire"])
            laundering_type = rng.choice([lt for lt in _LAUNDERING_TYPES if lt])
        else:
            amount = round(rng.uniform(500, 200_000), 2)
            currency = rng.choice(_CURRENCIES)
            pay_currency = currency
            recv_currency = currency  # same currency
            loc = rng.choice(_COUNTRIES)
            sender_loc = loc
            receiver_loc = loc if rng.random() < 0.7 else rng.choice(_COUNTRIES)
            payment_type = rng.choice(_PAYMENT_TYPES)
            laundering_type = ""

        rows.append({
            "Time": dt.strftime("%H:%M:%S"),
            "Date": dt.strftime("%Y-%m-%d"),
            "Sender_account": sender,
            "Receiver_account": receiver,
            "Amount": amount,
            "Payment_currency": pay_currency,
            "Received_currency": recv_currency,
            "Sender_bank_location": sender_loc,
            "Receiver_bank_location": receiver_loc,
            "Payment_type": payment_type,
            "Is_laundering": is_fraud,
            "Laundering_type": laundering_type,
        })

    rng.shuffle(rows)
    return pd.DataFrame(rows)


# ── Public API ───────────────────────────────────────────────────────────────


def generate_data(config: GeneratorConfig) -> pd.DataFrame:
    """Dispatch to the appropriate schema generator."""
    generators = {
        SCHEMA_UNIFIED: generate_unified,
        SCHEMA_PAYSIM: generate_paysim,
        SCHEMA_AML_CFT: generate_aml_cft,
    }
    return generators[config.schema](config)


def generate_and_save(
    config: GeneratorConfig,
    output_path: Optional[Path] = None,
) -> Path:
    """Generate data and write to CSV. Returns the output path."""
    df = generate_data(config)
    if output_path is None:
        output_path = DEFAULT_OUTPUT_DIR / "training_transactions.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


def generate_to_csv_string(config: GeneratorConfig) -> str:
    """Generate data and return as CSV string (for API/download responses)."""
    df = generate_data(config)
    buf = StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def get_schema_preview(schema: str) -> list[str]:
    """Return the column names for a given schema."""
    previews = {
        SCHEMA_UNIFIED: [
            "transaction_amount", "tx_count_last_hour", "has_upi",
            "nlp_signal", "label", "transaction_note",
        ],
        SCHEMA_PAYSIM: [
            "step", "type", "amount", "nameOrig", "oldbalanceOrg",
            "newbalanceOrig", "nameDest", "oldbalanceDest", "newbalanceDest",
            "isFraud", "isFlaggedFraud", "transaction_note",
        ],
        SCHEMA_AML_CFT: [
            "Time", "Date", "Sender_account", "Receiver_account", "Amount",
            "Payment_currency", "Received_currency", "Sender_bank_location",
            "Receiver_bank_location", "Payment_type", "Is_laundering",
            "Laundering_type",
        ],
    }
    return previews.get(schema, [])
