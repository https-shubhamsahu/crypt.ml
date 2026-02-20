Anti-Money Laundering (AML) System: RAW & SAR Agents with A2A Communication
Welcome to the AML Agent Framework
This notebook implements a dual-agent anti-money laundering system where:

RAW Agent (Real-time Anomaly Watchdog): Rule-based detection engine for suspicious transactions
SAR Agent (Suspicious Activity Report): ML-based investigation and reporting engine
These agents communicate via Agent2Agent (A2A) Protocol to detect financial crimes and generate compliance reports.

🎯 Learning Objectives
By the end of this notebook, you will:

Build a rule-based RAW agent with real-time transaction monitoring
Create an ML-powered SAR agent for pattern detection
Implement A2A communication between agents
Generate automated Suspicious Activity Reports (SARs)
Create explainable AI decisions for compliance audits
📊 System Architecture
┌─────────────────┐         A2A Protocol        ┌──────────────────┐
│   RAW Agent     │  ─────────────────────────► │   SAR Agent      │
│  (Rules Engine) │◄─────────────────────────── │  (ML + Graph)    │
│  • Thresholds   │                             │  • ML Classifier │
│  • Watchlists   │                             │  • Graph Analysis│
│  • Velocity     │                             │  • Report Gen    │
└─────────────────┘                             └──────────────────┘
        ▲                                               ▲
        │                                               │
        └──────────────┬───────────────────────────────┘
                       │
              Transaction Stream
             (Real-time/Batch)
add Codeadd Markdown
⚙️ Section 1: Environment Setup & Dependencies
add Codeadd Markdown
# Install required dependencies
import subprocess
import sys

packages = [
    "pandas>=2.0",
    "numpy>=1.24",
    "scikit-learn>=1.3",
    "xgboost>=2.0",
    "lightgbm>=4.0",
    "networkx>=3.0",
    "shap>=0.42",
    "matplotlib>=3.7",
    "seaborn>=0.12",
    "plotly>=5.0",
    "pytest>=7.0",
    "python-dotenv>=1.0",
    "requests>=2.31",
    "httpx>=0.24",
]

print("📦 Installing required packages...")
for package in packages:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", package])
print("✅ All packages installed successfully!")
add Codeadd Markdown
# Import all required libraries
import os
import json
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Any, Optional
from enum import Enum
import logging
import uuid
from abc import ABC, abstractmethod

# Data processing
import pandas as pd
import numpy as np

# ML and preprocessing
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_recall_curve, auc, confusion_matrix, roc_auc_score, f1_score

# Models
import xgboost as xgb
import lightgbm as lgb
import shap

# Graph analysis
import networkx as nx
from collections import defaultdict, Counter

# Visualization
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AML_SYSTEM")

print("✅ All libraries imported successfully!")
add Codeadd Markdown
📊 Section 2: Synthetic Transaction Dataset Generation
add Codeadd Markdown
# Transaction data classes
            src = f"ACC_{np.random.randint(0, 1000):06d}"
            
            # Create realistic suspicious patterns
            pattern = np.random.choice(['structuring', 'high_amount', 'velocity', 'high_risk_country'])
            
            if pattern == 'structuring':  # Just below reporting threshold
                amount = np.random.uniform(9000, 9999)
                country = np.random.choice(list(HIGH_RISK_COUNTRIES))
                channel = 'ATM'
            elif pattern == 'high_amount':
                amount = np.random.uniform(500000, 5000000)
                country = np.random.choice(list(HIGH_RISK_COUNTRIES))
                channel = 'Wire'
            elif pattern == 'velocity':
                amount = np.random.uniform(1000, 50000)
                country = np.random.choice(list(HIGH_RISK_COUNTRIES))
                channel = 'Online'
            else:  # high_risk_country
                amount = np.random.uniform(5000, 100000)
                country = np.random.choice(list(HIGH_RISK_COUNTRIES))
                channel = np.random.choice(['Wire', 'Online'])
            
            dst = f"ACC_{np.random.randint(1200, 2000):06d}"
            is_suspicious = True
        
        timestamp = base_date + timedelta(
            hours=np.random.randint(0, 90*24),
            minutes=np.random.randint(0, 1440)
        )
        
        transactions.append({
            'transaction_id': f'TXN_{uuid.uuid4().hex[:8].upper()}',
            'timestamp': timestamp,
            'amount': round(amount, 2),
            'src_account': src,
            'dst_account': dst,
            'currency': 'USD',
            'channel': channel,
            'country': country,
            'is_suspicious': is_suspicious
        })
    
    df = pd.DataFrame(transactions)
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    return df

# Generate dataset
print("📊 Generating synthetic transaction dataset...")
df_transactions = generate_synthetic_transactions(n_samples=10000, random_seed=42)
print(f"✅ Generated {len(df_transactions)} transactions")
print(f"   Suspicious transactions: {df_transactions['is_suspicious'].sum()} ({df_transactions['is_suspicious'].sum()/len(df_transactions)*100:.2f}%)")
print(f"\n📋 Sample transactions:")
print(df_transactions.head(10).to_string())
add Codeadd Markdown
🔧 Section 3: Data Preprocessing & Feature Engineering
add Codeadd Markdown
def engineer_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Engineer features for ML model"""
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Time-based features
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
    df['is_night'] = ((df['hour'] >= 22) | (df['hour'] <= 5)).astype(int)
    
    # Amount-based features
    df['log_amount'] = np.log1p(df['amount'])
    df['amount_bin'] = pd.cut(df['amount'], bins=[0, 1000, 5000, 10000, np.inf], labels=[0, 1, 2, 3])
    
    # Risk flags
    df['is_high_risk_country'] = df['country'].isin(HIGH_RISK_COUNTRIES).astype(int)
    df['is_high_amount'] = (df['amount'] > 10000).astype(int)
    
    # Velocity features (rolling aggregations)
    df['src_daily_count'] = df.groupby(['src_account', df['timestamp'].dt.date])['transaction_id'].transform('count')
    df['src_daily_volume'] = df.groupby(['src_account', df['timestamp'].dt.date])['amount'].transform('sum')
    df['dst_daily_count'] = df.groupby(['dst_account', df['timestamp'].dt.date])['transaction_id'].transform('count')
    
    # Channel features
    df['channel_encoded'] = pd.Categorical(df['channel']).codes
    
    # Country features (encode high risk)
    df['country_risk_score'] = df['country'].apply(
        lambda x: 1.0 if x in HIGH_RISK_COUNTRIES else 0.3
    )
    
    feature_cols = [
        'amount', 'log_amount', 'hour', 'day_of_week', 'is_weekend', 'is_night',
        'is_high_risk_country', 'is_high_amount', 'src_daily_count', 
        'src_daily_volume', 'dst_daily_count', 'channel_encoded', 'country_risk_score'
    ]
    
    return df, feature_cols

# Engineer features
print("🔧 Engineering features...")
df_features, feature_columns = engineer_features(df_transactions)
print(f"✅ Created {len(feature_columns)} features: {feature_columns}")
print(f"\n📊 Feature statistics:")
print(df_features[feature_columns].describe().to_string())
add Codeadd Markdown
📈 Section 4: Exploratory Data Analysis
add Codeadd Markdown
# Create visualizations
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Plot 1: Transaction amount distribution
axes[0, 0].hist(df_features[df_features['is_suspicious']==False]['amount'], bins=50, alpha=0.7, label='Normal')
axes[0, 0].hist(df_features[df_features['is_suspicious']==True]['amount'], bins=50, alpha=0.7, label='Suspicious')
axes[0, 0].set_xlabel('Amount (USD)')
axes[0, 0].set_ylabel('Count')
axes[0, 0].set_title('Transaction Amount Distribution')
axes[0, 0].set_yscale('log')
axes[0, 0].legend()

# Plot 2: Transactions by hour
hourly_dist = df_features.groupby('hour')['transaction_id'].count()
axes[0, 1].bar(hourly_dist.index, hourly_dist.values)
axes[0, 1].set_xlabel('Hour of Day')
axes[0, 1].set_ylabel('Transaction Count')
axes[0, 1].set_title('Transactions by Hour')

# Plot 3: Suspicious by country
country_risk = df_features.groupby('country')['is_suspicious'].mean().sort_values(ascending=False).head(10)
axes[1, 0].barh(country_risk.index, country_risk.values)
axes[1, 0].set_xlabel('Proportion Suspicious')
axes[1, 0].set_title('Top 10 Countries by Suspicious %')

# Plot 4: Channel distribution
channel_dist = df_features['channel'].value_counts()
axes[1, 1].bar(channel_dist.index, channel_dist.values, color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'])
axes[1, 1].set_xlabel('Channel')
axes[1, 1].set_ylabel('Count')
axes[1, 1].set_title('Transactions by Channel')

plt.tight_layout()
plt.savefig('aml_eda.png', dpi=100, bbox_inches='tight')
plt.show()

print("✅ EDA visualizations saved to 'aml_eda.png'")
add Codeadd Markdown
🚨 Section 5: Rule-Based RAW Agent (Real-time Anomaly Watchdog)
add Codeadd Markdown
class RuleAction(Enum):
                ))
        
        # Calculate overall risk score
        if violations:
            risk_score = min(1.0, max(v.severity for v in violations))
            # Determine final action (highest priority)
            final_action = self._determine_action(violations)
        else:
            risk_score = 0.0
            final_action = RuleAction.ALLOW
        
        decision = RAWDecision(
            transaction_id=transaction.get('transaction_id', f'TXN_{uuid.uuid4().hex[:8]}'),
            timestamp=timestamp_str,
            final_action=final_action,
            risk_score=risk_score,
            violations=violations
        )
        
        logger.info(f"RAW Decision: {decision.transaction_id} -> {final_action.value} (risk: {risk_score:.2f})")
        return decision
    
    @staticmethod
    def _determine_action(violations: List[RuleViolation]) -> RuleAction:
        """Determine final action from violations"""
        if not violations:
            return RuleAction.ALLOW
        
        actions_priority = {
            RuleAction.BLOCK: 4,
            RuleAction.ESCALATE: 3,
            RuleAction.REVIEW: 2,
            RuleAction.ALLOW: 1
        }
        
        return max(violations, key=lambda v: actions_priority[v.action]).action

# Initialize RAW Agent
raw_agent = RAWAgent()

# Test on sample transactions
print("🚨 Testing RAW Agent on sample transactions...\n")
test_transactions = df_transactions.head(10).to_dict('records')
raw_agent._recent_transactions = df_transactions.head(100).to_dict('records')

for i, txn in enumerate(test_transactions[:5]):
    decision = raw_agent.evaluate_transaction(txn)
    print(f"Transaction {i+1}: {decision.final_action.value.upper()} (Risk: {decision.risk_score:.2f})")
    if decision.violations:
        for v in decision.violations:
            print(f"  ⚠️  {v.rule_name}: {v.violation_text}")
    print()
add Codeadd Markdown
🤖 Section 6: ML-Based SAR Agent (ML Classifier & Graph Analysis)
add Codeadd Markdown
@dataclass
            ensemble_score=ensemble_score,
            is_flagged=ensemble_score > 0.5,
            top_features=top_features
        )
        
        return prediction
    
    def _compute_graph_anomaly_score(self, account: str) -> float:
        """Compute anomaly score based on graph position"""
        if not self.graph_features or account not in self.graph:
            return 0.5  # Neutral score for unknown accounts
        
        # Higher centrality = higher risk (more connected in suspicious patterns)
        degree_score = self.graph_features['degree_centrality'].get(account, 0)
        betweenness_score = self.graph_features['betweenness'].get(account, 0)
        pagerank_score = self.graph_features['pagerank'].get(account, 0)
        
        # Normalize and combine
        anomaly_score = 0.4 * degree_score + 0.3 * betweenness_score + 0.3 * pagerank_score
        return min(1.0, anomaly_score)

# Initialize and train SAR Agent
print("🤖 Training SAR Agent...\n")
sar_agent = SARAgent()

# Prepare data
X = df_features[feature_columns].fillna(0)
y = df_features['is_suspicious'].astype(int)

# Train ML model
auc_score = sar_agent.train_ml_model(X, y, feature_columns)

# Build transaction graph
sar_agent.build_transaction_graph(df_features)

print("✅ SAR Agent ready!")
add Codeadd Markdown
🔗 Section 7: A2A Communication Setup (Exposing Agents)
add Codeadd Markdown
# Note: In a production setting, we would use google-adk library for A2A
# For this demonstration, we'll create REST API endpoints and simulated A2A communication

# Define serializable decision objects for A2A communication
class A2ADecisionMessage:
    """A2A protocol message for agent communication"""
    
    @staticmethod
    def create_raw_request(transaction_data: Dict) -> Dict:
        """Create A2A request to RAW agent"""
        return {
            "message_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "agent": "RAW",
            "action": "evaluate_transaction",
            "payload": transaction_data
        }
    
    @staticmethod
    def create_sar_request(transaction_data: Dict, raw_decision: Dict) -> Dict:
        """Create A2A request to SAR agent with RAW decision context"""
        return {
            "message_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "agent": "SAR",
            "action": "predict_and_report",
            "payload": {
                "transaction": transaction_data,
                "raw_decision": raw_decision
            }
        }
    
    @staticmethod
    def create_response(success: bool, data: Dict) -> Dict:
        """Create A2A response message"""
        return {
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }

# Simulated A2A agent endpoints
def raw_agent_endpoint(request_message: Dict) -> Dict:
    """A2A endpoint for RAW agent - receives transaction, returns decision"""
    try:
        txn_data = request_message.get('payload', {})
        raw_agent._recent_transactions = df_transactions.head(100).to_dict('records')
        decision = raw_agent.evaluate_transaction(txn_data)
        return A2ADecisionMessage.create_response(True, decision.to_dict())
    except Exception as e:
        logger.error(f"RAW agent error: {e}")
        return A2ADecisionMessage.create_response(False, {"error": str(e)})

def sar_agent_endpoint(request_message: Dict) -> Dict:
    """A2A endpoint for SAR agent - receives transaction & RAW decision, returns SAR prediction"""
    try:
        payload = request_message.get('payload', {})
        txn_data = payload.get('transaction', {})
        
        # Create DataFrame from transaction data for ML prediction
        txn_df = pd.DataFrame([txn_data])[feature_columns].fillna(0)
        txn_df['transaction_id'] = txn_data.get('transaction_id', 'UNKNOWN')
        txn_df['src_account'] = txn_data.get('src_account', 'UNKNOWN')
        
        # Make SAR prediction
        sar_prediction = sar_agent.predict(txn_df)
        return A2ADecisionMessage.create_response(True, sar_prediction.to_dict())
    except Exception as e:
        logger.error(f"SAR agent error: {e}")
        return A2ADecisionMessage.create_response(False, {"error": str(e)})

print("✅ A2A Endpoint interfaces defined")
print("   - RAW Agent endpoint ready")
print("   - SAR Agent endpoint ready")
add Codeadd Markdown
🎯 Section 8: Agent Orchestration & Decision Logic
add Codeadd Markdown
class AMLOrchestrator:
    
    def _combine_decisions(self, transaction: Dict, raw_decision: Dict, sar_decision: Dict) -> Dict:
        """Combine RAW and SAR decisions into final AML decision"""
        
        raw_action = raw_decision.get('final_action', 'unknown')
        raw_score = raw_decision.get('risk_score', 0)
        
        sar_score = sar_decision.get('ensemble_score', 0)
        sar_flagged = sar_decision.get('is_flagged', False)
        
        # Decision logic:
        if raw_action == 'block':
            final_decision = 'BLOCK'
            action_reason = "Blocked by rule-based detection"
        elif raw_action == 'escalate' or sar_score > 0.7:
            final_decision = 'ESCALATE'
            action_reason = "Escalated due to high-risk indicators"
        elif raw_action == 'review' or sar_flagged:
            final_decision = 'REVIEW'
            action_reason = "Flagged for manual review"
        else:
            final_decision = 'ALLOW'
            action_reason = "Passed all checks"
        
        combined_score = 0.6 * raw_score + 0.4 * sar_score
        
        return {
            'transaction_id': transaction.get('transaction_id'),
            'timestamp': transaction.get('timestamp'),
            'final_decision': final_decision,
            'combined_risk_score': min(1.0, combined_score),
            'action_reason': action_reason,
            'raw_agent': {
                'action': raw_action,
                'risk_score': raw_score,
                'violations': raw_decision.get('violations', [])
            },
            'sar_agent': {
                'ml_score': sar_decision.get('ml_score', 0),
                'graph_score': sar_decision.get('graph_score', 0),
                'ensemble_score': sar_score,
                'is_flagged': sar_flagged,
                'top_features': sar_decision.get('top_features', [])
            }
        }
    
    def batch_process(self, transactions: List[Dict], show_summary: bool = True) -> List[Dict]:
        """Process batch of transactions"""
        results = []
        for txn in transactions:
            result = self.process_transaction(txn)
            results.append(result)
        
        if show_summary:
            self._print_batch_summary(results)
        
        return results
    
    def _print_batch_summary(self, results: List[Dict]):
        """Print summary of batch processing"""
        decisions = [r['final_decision'] for r in results]
        print(f"\n📊 Batch Processing Summary:")
        print(f"   Total processed: {len(results)}")
        print(f"   BLOCK: {decisions.count('BLOCK')}")
        print(f"   ESCALATE: {decisions.count('ESCALATE')}")
        print(f"   REVIEW: {decisions.count('REVIEW')}")
        print(f"   ALLOW: {decisions.count('ALLOW')}")

# Initialize orchestrator
orchestrator = AMLOrchestrator(raw_agent, sar_agent)

print("✅ AML Orchestrator initialized")
print("   Ready to process transactions using A2A communication between agents")
add Codeadd Markdown
📋 Section 9: SAR Report Generation & Explainability
add Codeadd Markdown
class SARReportGenerator:
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"✅ Report saved: {filename}")
        return filename
    
    @staticmethod
    def print_report(report: Dict):
        """Pretty print SAR report"""
        print("\n" + "="*80)
        print(f"🏦 SUSPICIOUS ACTIVITY REPORT (SAR)")
        print("="*80)
        print(f"\nReport ID: {report['report_id']}")
        print(f"Generated: {report['generated_at']}")
        
        print(f"\n📝 TRANSACTION SUMMARY:")
        ts = report['transaction_summary']
        print(f"  Transaction ID: {ts['transaction_id']}")
        print(f"  Amount: ${ts['amount']:,.2f} {ts['currency']}")
        print(f"  From: {ts['source_account']} → To: {ts['destination_account']}")
        print(f"  Channel: {ts['channel']}")
        print(f"  Country: {ts['country']}")
        print(f"  Time: {ts['timestamp']}")
        
        print(f"\n⚠️  AML DECISION:")
        ad = report['aml_decision']
        print(f"  Final Decision: {ad['final_decision']}")
        print(f"  Combined Risk Score: {ad['combined_risk_score']:.2%}")
        print(f"  Reason: {ad['action_reason']}")
        
        print(f"\n🚨 RULE ENGINE ANALYSIS:")
        ra = report['rule_engine_analysis']
        print(f"  RAW Action: {ra['raw_action']}")
        print(f"  Risk Score: {ra['raw_risk_score']:.2%}")
        if ra['rule_violations']:
            print(f"  Triggered Rules:")
            for v in ra['rule_violations']:
                print(f"    • {v['rule_name']}: {v['violation_text']}")
        
        print(f"\n🤖 ML ANALYSIS:")
        ma = report['ml_analysis']
        print(f"  ML Score: {ma['ml_score']:.2%}")
        print(f"  Graph Score: {ma['graph_score']:.2%}")
        print(f"  Ensemble Score: {ma['ensemble_score']:.2%}")
        print(f"  Top Features:")
        for feat, importance in ma['top_contributing_features'][:3]:
            print(f"    • {feat}: {importance:.4f}")
        
        print(f"\n📋 COMPLIANCE:")
        cm = report['compliance_metadata']
        print(f"  Filing Required: {cm['filing_required']}")
        print(f"  Priority: {cm['priority_level']}")
        print("\n" + "="*80 + "\n")

# Test report generation
print("📋 Testing SAR Report Generation...\n")

# Process a sample transaction
test_transaction = df_transactions.iloc[200].to_dict()
test_decision = orchestrator.process_transaction(test_transaction)

# Generate and display report
report = SARReportGenerator.generate_report(test_decision, test_transaction)
SARReportGenerator.print_report(report)
add Codeadd Markdown
📊 Section 10: Batch Processing & Metrics
add Codeadd Markdown
# Process batch of transactions and collect metrics
batch_transactions = df_transactions.head(100).to_dict('records')
batch_results = orchestrator.batch_process(batch_transactions, show_summary=False)

# Calculate metrics
decisions = [r['final_decision'] for r in batch_results]
risk_scores = [r['combined_risk_score'] for r in batch_results]
ground_truth = [df_transactions.iloc[i]['is_suspicious'] for i in range(len(batch_results))]

# Extract predictions (treat ESCALATE/BLOCK as positive predictions)
aml_predictions = [r['final_decision'] in ['ESCALATE', 'BLOCK'] for r in batch_results]

# Classification metrics
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

precision = precision_score(ground_truth, aml_predictions, zero_division=0)
recall = recall_score(ground_truth, aml_predictions, zero_division=0)
f1 = f1_score(ground_truth, aml_predictions, zero_division=0)

# Print metrics
print("="*80)
print("📊 AML SYSTEM BATCH PROCESSING METRICS")
print("="*80)

print(f"\n🎯 DECISION BREAKDOWN:")
print(f"  ALLOW:    {decisions.count('ALLOW'):3d} transactions")
print(f"  REVIEW:   {decisions.count('REVIEW'):3d} transactions")
print(f"  ESCALATE: {decisions.count('ESCALATE'):3d} transactions")
print(f"  BLOCK:    {decisions.count('BLOCK'):3d} transactions")

print(f"\n📈 DETECTION PERFORMANCE:")
print(f"  Precision: {precision:.4f}")
print(f"  Recall:    {recall:.4f}")
print(f"  F1-Score:  {f1:.4f}")

# Confusion matrix
tn, fp, fn, tp = confusion_matrix(ground_truth, aml_predictions).ravel()
print(f"\n🔢 CONFUSION MATRIX:")
print(f"  True Negatives:  {tn}")
print(f"  False Positives: {fp}")
print(f"  False Negatives: {fn}")
print(f"  True Positives:  {tp}")

# Risk score distribution
print(f"\n📊 RISK SCORE DISTRIBUTION:")
print(f"  Mean: {np.mean(risk_scores):.4f}")
print(f"  Std:  {np.std(risk_scores):.4f}")
print(f"  Min:  {np.min(risk_scores):.4f}")
print(f"  Max:  {np.max(risk_scores):.4f}")

print("="*80 + "\n")

# Visualize decision distribution
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Decision distribution
decision_counts = pd.Series(decisions).value_counts()
colors = {'ALLOW': 'green', 'REVIEW': 'yellow', 'ESCALATE': 'orange', 'BLOCK': 'red'}
bar_colors = [colors.get(d, 'gray') for d in decision_counts.index]
axes[0].bar(decision_counts.index, decision_counts.values, color=bar_colors)
axes[0].set_title('AML Decision Distribution')
axes[0].set_ylabel('Count')
axes[0].grid(axis='y', alpha=0.3)

# Risk score histogram
axes[1].hist(risk_scores, bins=30, edgecolor='black', alpha=0.7)
axes[1].axvline(np.mean(risk_scores), color='red', linestyle='--', label=f'Mean: {np.mean(risk_scores):.3f}')
axes[1].set_title('Risk Score Distribution')
axes[1].set_xlabel('Risk Score')
axes[1].set_ylabel('Frequency')
axes[1].legend()
axes[1].grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('aml_batch_metrics.png', dpi=100, bbox_inches='tight')
plt.show()

print("✅ Batch metrics visualization saved!")
add Codeadd Markdown
🧪 Section 11: Unit Tests & Validation
add Codeadd Markdown
def test_raw_agent_high_amount():
    prediction = sar_agent.predict(test_txn_df)
    assert 0 <= prediction.ensemble_score <= 1, "Ensemble score out of range"
    assert len(prediction.top_features) > 0, "Expected top features"
    print("✅ test_sar_agent_prediction passed")

def test_orchestrator_combines_decisions():
    """Test orchestrator combines RAW and SAR decisions"""
    test_txn = {
        'transaction_id': 'TEST_004',
        'timestamp': datetime.now().isoformat(),
        'amount': 50000,
        'src_account': 'ACC_001000',
        'dst_account': 'ACC_001001',
        'currency': 'USD',
        'channel': 'Wire',
        'country': 'Russia',
        'hour': 10,
        'day_of_week': 2,
        'is_weekend': 0,
        'is_night': 0,
        'log_amount': np.log1p(50000),
        'amount_bin': 2,
        'is_high_risk_country': 1,
        'is_high_amount': 1,
        'src_daily_count': 5,
        'src_daily_volume': 100000,
        'dst_daily_count': 2,
        'channel_encoded': 3,
        'country_risk_score': 1.0,
    }
    
    decision = orchestrator.process_transaction(test_txn)
    assert 'final_decision' in decision, "Missing final decision"
    assert decision['final_decision'] in ['ALLOW', 'REVIEW', 'ESCALATE', 'BLOCK']
    assert 'raw_agent' in decision, "Missing RAW agent decision"
    assert 'sar_agent' in decision, "Missing SAR agent decision"
    print("✅ test_orchestrator_combines_decisions passed")

def test_sar_report_generation():
    """Test SAR report generation"""
    test_txn = df_transactions.iloc[0].to_dict()
    test_decision = orchestrator.process_transaction(test_txn)
    
    report = SARReportGenerator.generate_report(test_decision, test_txn)
    assert 'report_id' in report, "Missing report ID"
    assert 'transaction_summary' in report, "Missing transaction summary"
    assert 'aml_decision' in report, "Missing AML decision"
    assert 'rule_engine_analysis' in report, "Missing rule engine analysis"
    assert 'ml_analysis' in report, "Missing ML analysis"
    print("✅ test_sar_report_generation passed")

# Run all tests
print("🧪 Running Unit Tests...\n")
try:
    test_raw_agent_high_amount()
    test_raw_agent_high_risk_country()
    test_raw_agent_normal_transaction()
    test_sar_agent_prediction()
    test_orchestrator_combines_decisions()
    test_sar_report_generation()
    print("\n✅ All tests passed!")
except AssertionError as e:
    print(f"\n❌ Test failed: {e}")
add Codeadd Markdown
arrow_upwardarrow_downwarddelete
🎓 Key Concepts & Summary
System Architecture
This AML system demonstrates a production-ready multi-agent architecture for financial crime detection:

RAW Agent (Rule-based)

Real-time rule evaluation
Configurable thresholds
Fast execution
Zero latency decisions
SAR Agent (ML-based)

Statistical anomaly detection
Graph-based network analysis
Ensemble scoring
Explainable predictions
Orchestrator

Combines both agents via A2A protocol
Configurable decision logic
Audit trail generation
Report compilation
A2A Protocol Benefits in AML
Separation of Concerns: Rules and ML can evolve independently
Scalability: Agents can run on different servers
Compliance: Clear audit trail of agent communication
Integration: Easy to add new agents (Payment Risk, Fraud Detection, etc.)
Testing: Agents can be tested in isolation
Deployment Strategies
Local Development (current): Both agents in same notebook

Microservices:

RAW Agent → Microservice on port 8001
SAR Agent → Microservice on port 8002
Orchestrator → API Gateway receiving transactions
Cloud Deployment:

Deploy RAW Agent to Cloud Run
Deploy SAR Agent to Cloud Run
Use Cloud Tasks for orchestration
Store decisions in BigQuery
Next Steps
Add More Agents: Velocity check agent, network analysis agent
Real Data: Connect to actual banking data streams
Model Improvement: Implement federated learning for regulatory compliance
Integration: Connect to compliance reporting systems
Monitoring: Add alerting for model drift and performance degradation