# Training Data

Place your local real dataset here before training.

## Option A: Unified schema (recommended)
File: `data/training_transactions.csv`

Required columns:
- `transaction_amount`
- `tx_count_last_hour`
- `has_upi`
- `nlp_signal`
- `label` (0/1)

## Option B: PaySim-like schema (auto-detected)
Also supported by `scripts/train_ml.py`:
- `amount`
- `step`
- `nameOrig`
- `isFraud`

The training script will transform these into the model feature schema automatically.

## Option C: AML-CFT format (auto-detected)
Also supported by `scripts/train_ml.py`:
- `Time`
- `Date`
- `Sender_account`
- `Receiver_account`
- `Amount`
- `Payment_currency`
- `Received_currency`
- `Sender_bank_location`
- `Receiver_bank_location`
- `Payment_type`
- `Is_laundering`
- `Laundering_type`

## Local-only policy
- Keep training data local in this folder.
- Do not fetch datasets during runtime training commands.
