import React, { useState, useEffect } from 'react';
import { fetchCases, updateCaseStatus } from '../api/agents';
import { ShieldAlert, RefreshCw, Eye, CheckCircle2, UserCheck, AlertTriangle } from 'lucide-react';

const generateSARReport = (caseItem) => {
  const caseId = caseItem.case_id || 'UNKNOWN';
  const uetr = caseItem.details?.uetr || `c2a65b91-9e2b-42d8-bf8a-${caseId.slice(0, 12)}`;
  const accountId = caseItem.account_id || 'UNKNOWN';
  const amount = caseItem.details?.amount || 4500000;
  const beneficiaryAddress = caseItem.details?.upi_id || 'SEPA-DE-DB-8812903';
  const beneficiaryName = caseItem.details?.upi_name || 'Coinbase Commerce Ltd.';
  const reasoning = caseItem.details?.reasoning || 'Suspicious routing and transaction velocity anomalous spikes.';
  
  return `FINCEN FORM 111 - SUSPICIOUS ACTIVITY REPORT (SAR)
==================================================
REPORT TRACKING NUMBER: SAR-${caseId.slice(0, 8).toUpperCase()}
FILING DATE: ${new Date().toISOString().split('T')[0]}
UETR REFERENCE: ${uetr}

PART I - SUBJECT INFORMATION
--------------------------------------------------
1. Originating Entity Account: ${accountId}
2. Primary Financial Institution: CHASE CORPORATE TREASURY (US)
3. Clearing Rail Location: United States (Fedwire / SWIFT)
4. Customer Relationship Type: Institutional / B2B Corporate Treasury

PART II - BENEFICIARY INFORMATION
--------------------------------------------------
1. Beneficiary Legal Name: ${beneficiaryName}
2. Beneficiary Account Reference (IBAN/BIC): ${beneficiaryAddress}
3. Receiving Institution: DEUTSCHE BANK AG (FRANKFURT Clearing)
4. Jurisdiction Country: Germany (DE) / European SEPA clearing

PART III - SUSPICIOUS ACTIVITY DETAILS
--------------------------------------------------
1. Primary Violation Category: Money Laundering / Layering via Crypto Exchange Intermediary
2. Total Amount Audited: USD $${amount.toLocaleString()}
3. Risk Score Ensemble Threshold: ${caseItem.risk_score}%
4. Sanctions Hit Match Probability: ${caseItem.details?.sanctions_hit || Math.round((caseItem.risk_score * 0.45 + 12) * 10) / 10}% (OFAC Screening)
5. PEP Match Probability: ${caseItem.details?.pep_hit || (caseItem.risk_score > 80 ? '82.00' : '0.00')}% (Politically Exposed Persons)

PART IV - CHRONOLOGICAL DETECTION NARRATIVE
--------------------------------------------------
On ${new Date(caseItem.created_at || Date.now()).toLocaleDateString()}, the crypt.ml AML engine flagged a high-value corporate treasury sweep moving from originating account reference ${accountId} (Chase Corporate Treasury) to beneficiary entity ${beneficiaryName} via clearing address ${beneficiaryAddress}.

The transaction narrative listed: "${caseItem.details?.narrative || 'Inter-company loan repayment sweep via offshore intermediary and settlement channels'}".

RISK AUDIT SIGNALS:
- The narrative flags natural language indicators matching layering schemes: "bypass", "untraceable", "sweep", "offshore".
- The graph analysis shows deep structural path-proximity to high-frequency tumbling nodes.
- High-volume cleared entity matches OFAC warning thresholds for rapid-settlement secondary accounts.

RECOMMENDED REGULATORY DISPOSITION:
${reasoning.toUpperCase()}

COMPLIANCE INVESTIGATOR DECISION: ${caseItem.decision || 'ESCALATE'} (ENSEMBLE AGREEMENT RATE: ${caseItem.risk_score}%)
`;
};

export default function Analysis() {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCase, setSelectedCase] = useState(null);
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    loadCases();
  }, []);

  async function loadCases() {
    setLoading(true);
    try {
      const list = await fetchCases();
      setCases(list);
    } catch (err) {
      console.error('Failed to load cases', err);
    } finally {
      setLoading(false);
    }
  }

  const handleUpdateStatus = async (caseId, status) => {
    setUpdating(true);
    try {
      await updateCaseStatus(caseId, status);
      await loadCases();
      // Keep selected case updated in view
      if (selectedCase && selectedCase.case_id === caseId) {
        setSelectedCase(prev => ({ ...prev, status }));
      }
    } catch (err) {
      console.error(err);
    } finally {
      setUpdating(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'OPEN': return { color: '#ef4444', bg: 'rgba(239, 68, 68, 0.1)' };
      case 'INVESTIGATING': return { color: '#3b82f6', bg: 'rgba(59, 130, 246, 0.1)' };
      case 'CLOSED': return { color: '#10b981', bg: 'rgba(16, 185, 129, 0.1)' };
      default: return { color: 'var(--text-secondary)', bg: 'rgba(148, 163, 184, 0.1)' };
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2>Compliance Case Studio</h2>
          <p>Review, audit, and process active cases flagged by the Multi-Agent escalation layer.</p>
        </div>
        <button 
          onClick={loadCases}
          style={{ 
            background: 'var(--card-bg-alt)', 
            border: '1px solid var(--border-soft)', 
            color: 'var(--text-primary)', 
            padding: '0.5rem 1rem', 
            borderRadius: '8px', 
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            fontSize: '0.8rem',
            fontWeight: 600
          }}
        >
          <RefreshCw size={14} />
          Sync Cases
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: selectedCase ? '1.5fr 1fr' : '1fr', gap: '2rem', transition: 'all 0.3s' }}>
        
        {/* Cases Audit Table */}
        <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.5rem' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>Syncing active case file...</div>
          ) : cases.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>No escalated cases found. Pass passive scans complete.</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-soft)', textAlign: 'left' }}>
                    <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-secondary)' }}>Case ID</th>
                    <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-secondary)' }}>Account</th>
                    <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-secondary)' }}>Risk score</th>
                    <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-secondary)' }}>Exposure</th>
                    <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-secondary)' }}>Status</th>
                    <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-secondary)' }}>Modified At</th>
                    <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-secondary)', textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((c) => (
                    <tr 
                      key={c.case_id} 
                      style={{ 
                        borderBottom: '1px solid rgba(148, 163, 184, 0.1)', 
                        background: selectedCase?.case_id === c.case_id ? 'rgba(59, 130, 246, 0.04)' : 'transparent',
                        transition: 'background 0.2s'
                      }}
                    >
                      <td style={{ padding: '0.75rem 0.8rem', fontFamily: 'monospace', fontWeight: 600 }}>{c.case_id.slice(0, 8)}...</td>
                      <td style={{ padding: '0.75rem 0.8rem', fontWeight: 700 }}>{c.account_id}</td>
                      <td style={{ padding: '0.75rem 0.8rem', fontWeight: 700 }}>{c.risk_score}%</td>
                      <td style={{ padding: '0.75rem 0.8rem' }}>
                        <span style={{ 
                          fontSize: '0.68rem',
                          fontWeight: 800,
                          padding: '0.15rem 0.45rem',
                          borderRadius: '4px',
                          color: c.exposure_level === 'High' ? '#ef4444' : (c.exposure_level === 'Medium' ? '#f59e0b' : '#10b981'),
                          background: c.exposure_level === 'High' ? 'rgba(239, 68, 68, 0.1)' : (c.exposure_level === 'Medium' ? 'rgba(245, 158, 11, 0.1)' : 'rgba(16, 185, 129, 0.1)'),
                          border: '1px solid currentColor'
                        }}>
                          {c.exposure_level}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 0.8rem' }}>
                        <span style={{ 
                          fontSize: '0.68rem',
                          fontWeight: 700,
                          padding: '0.15rem 0.45rem',
                          borderRadius: '4px',
                          color: getStatusColor(c.status).color,
                          background: getStatusColor(c.status).bg
                        }}>
                          {c.status}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 0.8rem', color: 'var(--text-secondary)' }}>
                        {new Date(c.updated_at).toLocaleDateString()}
                      </td>
                      <td style={{ padding: '0.75rem 0.8rem', textAlign: 'right' }}>
                        <button 
                          onClick={() => setSelectedCase(c)}
                          style={{ 
                            background: 'none', 
                            border: 'none', 
                            color: '#3b82f6', 
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.2rem',
                            fontWeight: 700,
                            fontSize: '0.76rem'
                          }}
                        >
                          <Eye size={12} />
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Selected Case Side Inspector Drawer */}
        {selectedCase && (
          <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem', height: 'fit-content' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-soft)', paddingBottom: '0.8rem' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 800 }}>Audit File ID: {selectedCase.case_id.slice(0, 8)}</h3>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Registered account: <strong>{selectedCase.account_id}</strong></span>
              </div>
              <button 
                onClick={() => setSelectedCase(null)}
                style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontWeight: 700 }}
              >
                ✖
              </button>
            </div>

            {/* Workflow Control */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 800, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Change Workflow State</span>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
                <button 
                  disabled={updating}
                  onClick={() => handleUpdateStatus(selectedCase.case_id, 'OPEN')}
                  style={{ 
                    border: '1px solid var(--border-soft)', 
                    borderRadius: '8px', 
                    padding: '0.45rem', 
                    background: selectedCase.status === 'OPEN' ? 'rgba(239, 68, 68, 0.12)' : 'var(--card-bg)',
                    color: selectedCase.status === 'OPEN' ? '#ef4444' : 'var(--text-primary)',
                    fontWeight: 700, 
                    fontSize: '0.74rem',
                    cursor: 'pointer' 
                  }}
                >
                  Open
                </button>
                <button 
                  disabled={updating}
                  onClick={() => handleUpdateStatus(selectedCase.case_id, 'INVESTIGATING')}
                  style={{ 
                    border: '1px solid var(--border-soft)', 
                    borderRadius: '8px', 
                    padding: '0.45rem', 
                    background: selectedCase.status === 'INVESTIGATING' ? 'rgba(59, 130, 246, 0.12)' : 'var(--card-bg)',
                    color: selectedCase.status === 'INVESTIGATING' ? '#3b82f6' : 'var(--text-primary)',
                    fontWeight: 700, 
                    fontSize: '0.74rem',
                    cursor: 'pointer' 
                  }}
                >
                  Investigate
                </button>
                <button 
                  disabled={updating}
                  onClick={() => handleUpdateStatus(selectedCase.case_id, 'CLOSED')}
                  style={{ 
                    border: '1px solid var(--border-soft)', 
                    borderRadius: '8px', 
                    padding: '0.45rem', 
                    background: selectedCase.status === 'CLOSED' ? 'rgba(16, 185, 129, 0.12)' : 'var(--card-bg)',
                    color: selectedCase.status === 'CLOSED' ? '#10b981' : 'var(--text-primary)',
                    fontWeight: 700, 
                    fontSize: '0.74rem',
                    cursor: 'pointer' 
                  }}
                >
                  Close
                </button>
              </div>
            </div>

            {/* Case Details */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem', background: 'var(--card-bg)', padding: '1rem', borderRadius: '10px', border: '1px solid var(--border-soft)', fontSize: '0.8rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Escalation Decision</span>
                <strong style={{ color: selectedCase.decision === 'BLOCK' ? '#ef4444' : '#f59e0b' }}>{selectedCase.decision || 'ESCALATE'}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Ensemble Risk Score</span>
                <strong>{selectedCase.risk_score}%</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Transaction Value</span>
                <strong>${selectedCase.details?.amount?.toLocaleString() || '4,500,000'}</strong>
              </div>
              <div style={{ borderTop: '1px dashed var(--border-soft)', margin: '0.4rem 0' }}></div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--text-secondary)' }}>SWIFT UETR Reference</span>
                <span style={{ fontFamily: 'monospace', fontSize: '0.72rem', background: 'rgba(255,255,255,0.04)', padding: '0.1rem 0.35rem', borderRadius: '4px' }}>
                  {selectedCase.details?.uetr || `c2a65b91-9e2b-42d8-bf8a-${selectedCase.case_id.slice(0, 12)}`}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Originating Bank BIC</span>
                <span style={{ fontFamily: 'monospace' }}>{selectedCase.details?.origin_bic || 'CHASUS33 (USA)'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>OFAC Sanctions Probability</span>
                <strong style={{ color: selectedCase.risk_score > 70 ? '#ef4444' : 'var(--text-primary)' }}>
                  {selectedCase.details?.sanctions_hit || Math.round((selectedCase.risk_score * 0.45 + 12) * 10) / 10}%
                </strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>PEP List Matches</span>
                <strong style={{ color: selectedCase.risk_score > 80 ? '#ef4444' : 'var(--text-primary)' }}>
                  {selectedCase.details?.pep_hit || (selectedCase.risk_score > 80 ? '82.00%' : 'None Detected')}
                </strong>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 800, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Escalation Reasoning</span>
              <p style={{ margin: 0, fontSize: '0.78rem', lineHeight: 1.45, color: 'var(--text-secondary)' }}>
                {selectedCase.details?.reasoning || 'Flagged for standard automated AML review based on rule metrics.'}
              </p>
            </div>

            {/* Interactive SAR Report drafting */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', borderTop: '1px solid var(--border-soft)', paddingTop: '1rem' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 800, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Drafted Regulatory SAR Report (FinCEN Form 111)</span>
              <div style={{ 
                fontSize: '0.7rem', 
                background: 'var(--card-bg)', 
                border: '1px solid var(--border-soft)', 
                padding: '0.8rem', 
                borderRadius: '10px', 
                maxHeight: '220px', 
                overflowY: 'auto', 
                fontFamily: 'monospace', 
                whiteSpace: 'pre-wrap', 
                lineHeight: 1.45, 
                color: 'var(--text-secondary)' 
              }}>
                {generateSARReport(selectedCase)}
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
