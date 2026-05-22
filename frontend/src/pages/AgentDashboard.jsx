import React, { useState, useEffect } from 'react';
import { analyzeTransaction, fetchDecisions } from '../api/agents';
import { 
  Play, 
  Cpu, 
  Clock, 
  AlertCircle, 
  CheckCircle2, 
  XCircle, 
  MessageSquare, 
  Database,
  ArrowRight,
  ShieldAlert
} from 'lucide-react';

export default function AgentDashboard() {
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Simulator State
  const [accountId, setAccountId] = useState('CHASE-US-DE-99201948');
  const [upiId, setUpiId] = useState('SEPA-DE-DB-8812903');
  const [upiName, setUpiName] = useState('Coinbase Commerce Ltd.');
  const [amount, setAmount] = useState('4500000');
  const [note, setNote] = useState('Inter-company loan repayment sweep via offshore intermediary and settlement channels');
  
  // Pipeline Analysis State
  const [analyzing, setAnalyzing] = useState(false);
  const [runId, setRunId] = useState(null);
  const [result, setResult] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [messages, setMessages] = useState([]);
  const [agentResults, setAgentResults] = useState({});
  const [activeStep, setActiveStep] = useState(null);
  
  // Past Audits list
  const [audits, setAudits] = useState([]);
  const [loadingAudits, setLoadingAudits] = useState(true);

  // Load audit history on startup
  useEffect(() => {
    loadAuditHistory();
  }, []);

  async function loadAuditHistory() {
    try {
      const list = await fetchDecisions();
      setAudits(list);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingAudits(false);
    }
  }

  // Trigger real multi-agent analysis pipeline
  const handleSimulate = async (e) => {
    e.preventDefault();
    if (analyzing) return;
    
    setAnalyzing(true);
    setResult(null);
    setRunId(null);
    setTimeline([]);
    setMessages([]);
    setAgentResults({});
    
    const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    
    try {
      const payload = {
        account_id: accountId,
        transaction_amount: parseFloat(amount),
        upi_id: upiId,
        upi_name: upiName,
        narrative: note
      };
      
      // Dispatch API call in the background so it runs in parallel with the sequential stepping flow
      const apiPromise = analyzeTransaction(payload);
      
      // Visual Step 0: Orchestrator dispatching
      setActiveStep('OrchestratorAgent');
      await delay(800);
      
      // Visual Step 1: RAW & NLP tier
      setActiveStep('RAWAgent_NLPAgent');
      await delay(800);
      
      // Visual Step 2: ML & Graph tier
      setActiveStep('MLAgent_GraphAgent');
      await delay(800);

      // Visual Step 3: SAR tier
      setActiveStep('SARAgent');
      await delay(800);

      // Await final API response
      const res = await apiPromise;
      
      if (res.status === 'success') {
        setResult(res);
        setRunId(res.run_id);
        setTimeline(res.timeline || []);
        setMessages(res.messages || []);
        setAgentResults(res.agent_results || {});
        // Refresh audit table
        loadAuditHistory();
      }
    } catch (err) {
      console.error('Simulation failed', err);
    } finally {
      setAnalyzing(false);
      setActiveStep(null);
    }
  };

  // Helper to get decision color
  const getDecisionStyles = (decision) => {
    switch (decision) {
      case 'BLOCK': return { color: '#ef4444', bg: 'rgba(239, 68, 68, 0.12)', border: 'rgba(239, 68, 68, 0.3)' };
      case 'ESCALATE': return { color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.12)', border: 'rgba(245, 158, 11, 0.3)' };
      case 'REVIEW': return { color: '#3b82f6', bg: 'rgba(59, 130, 246, 0.12)', border: 'rgba(59, 130, 246, 0.3)' };
      default: return { color: '#10b981', bg: 'rgba(16, 185, 129, 0.12)', border: 'rgba(16, 185, 129, 0.3)' };
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <div>
        <h2>Multi-Agent Orchestration Studio</h2>
        <p>Observe five autonomous compliance agents cooperating via the compliance EventBus to audit transactions.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1.6fr', gap: '2rem' }}>
        
        {/* Left Side: Transaction Input & Simulator */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.5rem' }}>
            <h3 style={{ margin: '0 0 1rem', fontSize: '1.05rem', fontWeight: 800 }}>Simulate Live Transaction</h3>
            
            <form onSubmit={handleSimulate} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="form-group">
                <label>Originating Account Reference (IBAN/BIC)</label>
                <input type="text" value={accountId} onChange={(e) => setAccountId(e.target.value)} required />
              </div>

              <div className="inline-row">
                <div className="form-group">
                  <label>Amount (USD)</label>
                  <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} required />
                </div>
                <div className="form-group">
                  <label>Beneficiary Clearing Address (IBAN/BIC)</label>
                  <input type="text" value={upiId} onChange={(e) => setUpiId(e.target.value)} required />
                </div>
              </div>

              <div className="form-group">
                <label>Beneficiary Legal Name</label>
                <input type="text" value={upiName} onChange={(e) => setUpiName(e.target.value)} required />
              </div>

              <div className="form-group">
                <label>Transaction Narrative / Clearing Reference (NLP Target)</label>
                <textarea rows="3" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Enter clearing reference or payment purpose narrative..."></textarea>
              </div>

              <button 
                type="submit" 
                disabled={analyzing}
                style={{ 
                  background: analyzing ? 'rgba(59, 130, 246, 0.4)' : '#3b82f6', 
                  border: 'none', 
                  borderRadius: '10px', 
                  color: 'white', 
                  fontWeight: 700, 
                  padding: '0.75rem', 
                  cursor: analyzing ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                  marginTop: '0.5rem'
                }}
              >
                <Play size={16} />
                {analyzing ? 'Agents Coordinating...' : 'Dispatch to Agents'}
              </button>
            </form>
          </div>
        </div>

        {/* Right Side: Multi-Agent Interaction Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          
          {/* Agent Connection Graph */}
          <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.5rem', minHeight: '340px', display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ margin: '0 0 1.5rem', fontSize: '1.05rem', fontWeight: 800 }}>Cooperative Agent Flow</h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1.2rem', flex: 1, justifyContent: 'center' }}>
              
              {/* Orchestrator Agent Node */}
              <div style={{ 
                border: '2px solid',
                borderColor: activeStep === 'OrchestratorAgent' ? '#3b82f6' : 'var(--border-soft)',
                background: activeStep === 'OrchestratorAgent' ? 'rgba(59, 130, 246, 0.08)' : 'var(--card-bg)',
                boxShadow: activeStep === 'OrchestratorAgent' ? '0 0 15px rgba(59, 130, 246, 0.4)' : 'none',
                borderRadius: '12px',
                padding: '0.6rem 1.2rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.6rem',
                transition: 'all 0.3s'
              }}>
                <Cpu size={16} color="#3b82f6" />
                <strong style={{ fontSize: '0.85rem' }}>OrchestratorAgent</strong>
                <span style={{ fontSize: '0.65rem', background: 'rgba(59, 130, 246, 0.12)', color: '#3b82f6', padding: '0.1rem 0.4rem', borderRadius: '4px' }}>MASTER</span>
              </div>

              <div style={{ display: 'flex', flexDirection: isMobile ? 'column' : 'row', gap: '1rem', width: '100%', justifyContent: 'space-around', alignItems: 'center' }}>
                {/* RAW Compliance Agent Node */}
                <div style={{ 
                  border: '2px solid',
                  borderColor: activeStep === 'RAWAgent_NLPAgent' ? '#3b82f6' : (result ? '#10b981' : 'var(--border-soft)'),
                  background: activeStep === 'RAWAgent_NLPAgent' ? 'rgba(59, 130, 246, 0.08)' : 'var(--card-bg)',
                  borderRadius: '12px',
                  padding: '0.6rem 1.2rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.6rem',
                  flex: 1,
                  width: isMobile ? '100%' : 'auto',
                  maxWidth: '180px',
                  justifyContent: 'center',
                  transition: 'all 0.3s'
                }}>
                  <ShieldAlert size={14} color="#60a5fa" />
                  <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>RAWAgent</span>
                </div>

                {/* NLP Analysis Agent Node */}
                <div style={{ 
                  border: '2px solid',
                  borderColor: activeStep === 'RAWAgent_NLPAgent' ? '#3b82f6' : (result ? '#10b981' : 'var(--border-soft)'),
                  background: activeStep === 'RAWAgent_NLPAgent' ? 'rgba(59, 130, 246, 0.08)' : 'var(--card-bg)',
                  borderRadius: '12px',
                  padding: '0.6rem 1.2rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.6rem',
                  flex: 1,
                  width: isMobile ? '100%' : 'auto',
                  maxWidth: '180px',
                  justifyContent: 'center',
                  transition: 'all 0.3s'
                }}>
                  <MessageSquare size={14} color="#60a5fa" />
                  <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>NLPAgent</span>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: isMobile ? 'column' : 'row', gap: '1rem', width: '100%', justifyContent: 'space-around', alignItems: 'center' }}>
                {/* ML Scoring Agent Node */}
                <div style={{ 
                  border: '2px solid',
                  borderColor: activeStep === 'MLAgent_GraphAgent' ? '#3b82f6' : (result ? '#10b981' : 'var(--border-soft)'),
                  background: activeStep === 'MLAgent_GraphAgent' ? 'rgba(59, 130, 246, 0.08)' : 'var(--card-bg)',
                  borderRadius: '12px',
                  padding: '0.6rem 1.2rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.6rem',
                  flex: 1,
                  width: isMobile ? '100%' : 'auto',
                  maxWidth: '180px',
                  justifyContent: 'center',
                  transition: 'all 0.3s'
                }}>
                  <Database size={14} color="#60a5fa" />
                  <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>MLAgent</span>
                </div>

                {/* Graph Intelligence Agent Node */}
                <div style={{ 
                  border: '2px solid',
                  borderColor: activeStep === 'MLAgent_GraphAgent' ? '#3b82f6' : (result ? '#10b981' : 'var(--border-soft)'),
                  background: activeStep === 'MLAgent_GraphAgent' ? 'rgba(59, 130, 246, 0.08)' : 'var(--card-bg)',
                  borderRadius: '12px',
                  padding: '0.6rem 1.2rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.6rem',
                  flex: 1,
                  width: isMobile ? '100%' : 'auto',
                  maxWidth: '180px',
                  justifyContent: 'center',
                  transition: 'all 0.3s'
                }}>
                  <Clock size={14} color="#60a5fa" />
                  <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>GraphAgent</span>
                </div>
              </div>

              {/* SAR Reporting Agent Node */}
              <div style={{ 
                border: '2px solid',
                borderColor: activeStep === 'SARAgent' ? '#3b82f6' : (result ? '#10b981' : 'var(--border-soft)'),
                background: activeStep === 'SARAgent' ? 'rgba(59, 130, 246, 0.08)' : 'var(--card-bg)',
                borderRadius: '12px',
                padding: '0.6rem 1.2rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.6rem',
                transition: 'all 0.3s'
              }}>
                <CheckCircle2 size={14} color="#10b981" />
                <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>SARAgent</span>
              </div>

            </div>
          </div>
        </div>

      </div>

      {/* Live Decision Panel */}
      {result && (
        <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800 }}>Orchestrator Decision Summary</h3>
            <span style={{ 
              fontSize: '0.78rem',
              fontWeight: 800,
              padding: '0.35rem 0.8rem',
              borderRadius: '8px',
              color: getDecisionStyles(result.final_decision).color,
              background: getDecisionStyles(result.final_decision).bg,
              border: `1px solid ${getDecisionStyles(result.final_decision).border}`
            }}>
              {result.final_decision} (Ensemble: {result.final_score}%)
            </span>
          </div>

          <div style={{ fontSize: '0.9rem', lineHeight: 1.5, background: 'var(--card-bg)', padding: '1rem', borderRadius: '10px', border: '1px solid var(--border-soft)' }}>
            <strong>Reasoning Rationale:</strong> {result.reasoning}
          </div>

          {/* Sub-Agent Decisive Contributions */}
          <div>
            <h4 style={{ margin: '0 0 0.8rem', fontSize: '0.92rem', fontWeight: 700 }}>Decisive Contributions</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
              {Object.keys(agentResults).map((name) => {
                const agent = agentResults[name];
                return (
                  <div key={name} style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg)', borderRadius: '10px', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong style={{ fontSize: '0.82rem' }}>{name}</strong>
                      <span style={{ 
                        fontSize: '0.68rem',
                        fontWeight: 800,
                        padding: '0.1rem 0.4rem',
                        borderRadius: '4px',
                        color: getDecisionStyles(agent.decision).color,
                        background: getDecisionStyles(agent.decision).bg
                      }}>{agent.decision}</span>
                    </div>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Score: <strong>{agent.score}%</strong> (Conf: {Math.round(agent.confidence * 100)}%)</span>
                    <p style={{ margin: '0.3rem 0 0', fontSize: '0.74rem', color: 'var(--text-secondary)', lineHeight: 1.35 }}>{agent.reasoning}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Gantt Timelines */}
          <div>
            <h4 style={{ margin: '0 0 0.8rem', fontSize: '0.92rem', fontWeight: 700 }}>Execution Step Trace</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', background: 'var(--card-bg)', padding: '1rem', borderRadius: '10px', border: '1px solid var(--border-soft)' }}>
              {timeline.map((step, idx) => (
                <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.76rem' }}>
                  <div style={{ display: 'flex', gap: '0.5rem', width: '220px' }}>
                    <strong style={{ color: 'var(--text-secondary)' }}>{step.agent}</strong>
                    <span>{step.stage}</span>
                  </div>
                  <div style={{ flex: 1, height: '8px', background: 'rgba(148, 163, 184, 0.1)', borderRadius: '4px', margin: '0 1rem', position: 'relative' }}>
                    <div style={{ 
                      position: 'absolute',
                      left: `${Math.min(100, step.start_time * 50)}%`,
                      width: `${Math.max(2, ((step.end_time || step.start_time) - step.start_time) * 50)}%`,
                      height: '100%',
                      background: '#3b82f6',
                      borderRadius: '4px'
                    }}></div>
                  </div>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>
                    +{Math.round(step.start_time * 1000)}ms
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Inter-Agent Bus Messages */}
          <div>
            <h4 style={{ margin: '0 0 0.8rem', fontSize: '0.92rem', fontWeight: 700 }}>EventBus Messages Exchanged</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', maxHeight: '180px', overflowY: 'auto', background: 'var(--card-bg)', padding: '1rem', borderRadius: '10px', border: '1px solid var(--border-soft)', fontFamily: 'monospace', fontSize: '0.72rem' }}>
              {messages.map((msg, idx) => (
                <div key={idx} style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.1)', paddingBottom: '0.35rem', display: 'flex', gap: '0.5rem' }}>
                  <span style={{ color: '#3b82f6' }}>[{msg.sender} → {msg.receiver}]</span>
                  <span style={{ color: '#60a5fa' }}>{msg.msg_type}</span>
                  <span style={{ color: 'var(--text-secondary)', flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{JSON.stringify(msg.payload)}</span>
                </div>
              ))}
            </div>
          </div>

        </div>
      )}

      {/* Audit History Log */}
      <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.5rem' }}>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1.05rem', fontWeight: 800 }}>SQLite Compliance Decision Audits</h3>
        
        {loadingAudits ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>Loading logs...</div>
        ) : audits.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>No recent decisions found. Run a simulation to start!</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-soft)', textAlign: 'left' }}>
                  <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-secondary)' }}>Account</th>
                  <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-secondary)' }}>Amount</th>
                  <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-secondary)' }}>Decision</th>
                  <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-secondary)' }}>Risk Score</th>
                  <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-secondary)' }}>Reasoning Rationale</th>
                  <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-secondary)' }}>Audited Date</th>
                </tr>
              </thead>
              <tbody>
                {audits.map((audit) => (
                  <tr key={audit.id} style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.1)', transition: 'background 0.2s' }} className="hover:bg-slate-800">
                    <td style={{ padding: '0.75rem 0.8rem', fontWeight: 700 }}>{audit.account_id}</td>
                    <td style={{ padding: '0.75rem 0.8rem', fontWeight: 700 }}>${audit.amount.toLocaleString()}</td>
                    <td style={{ padding: '0.75rem 0.8rem' }}>
                      <span style={{ 
                        fontSize: '0.7rem',
                        fontWeight: 800,
                        padding: '0.15rem 0.5rem',
                        borderRadius: '6px',
                        color: getDecisionStyles(audit.final_decision).color,
                        background: getDecisionStyles(audit.final_decision).bg
                      }}>{audit.final_decision}</span>
                    </td>
                    <td style={{ padding: '0.75rem 0.8rem', fontWeight: 700 }}>{audit.final_score}%</td>
                    <td style={{ padding: '0.75rem 0.8rem', maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--text-secondary)' }}>
                      {audit.reasoning}
                    </td>
                    <td style={{ padding: '0.75rem 0.8rem', color: 'var(--text-secondary)' }}>
                      {new Date(audit.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
