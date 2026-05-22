import React, { useState, useEffect, useRef } from 'react';
import { fetchDatasets } from '../api/datasets';
import { 
  sendAssistantMessage, 
  fetchAssistantHistory, 
  clearAssistantHistory,
  fetchSessionRules 
} from '../api/assistant';
import { 
  MessageSquare, 
  Send, 
  Trash2, 
  Cpu, 
  Sparkles, 
  FileText, 
  ShieldAlert, 
  Activity, 
  ArrowRight,
  RefreshCw,
  Database
} from 'lucide-react';

const buildIntroMessage = (datasetName) => ({
  id: 'intro',
  role: 'assistant',
  text: datasetName
    ? `Hello! I’m your multi-agent compliance assistant for **${datasetName}**. I can help you analyze transaction clusters, explain why specific entities are flagged, and draft SAR reports.`
    : 'Hello! I’m your multi-agent compliance assistant. Select an active dataset to start a scoped analysis thread, or talk to me globally about standard AML patterns.',
  created_at: new Date().toISOString()
});

export default function Assistant() {
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState('');
  const [messages, setMessages] = useState([]);
  const [activeRules, setActiveRules] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [llmStatus, setLlmStatus] = useState({ enabled: true, model: 'phi3.5' });

  const messagesEndRef = useRef(null);

  // Load datasets on mount
  useEffect(() => {
    async function loadDatasets() {
      try {
        const list = await fetchDatasets();
        setDatasets(list);
      } catch (err) {
        console.error('Failed to load datasets', err);
      }
    }
    loadDatasets();
  }, []);

  // Reload history and rules whenever selected dataset changes
  useEffect(() => {
    loadChatState();
  }, [selectedDatasetId]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const selectedDataset = datasets.find(d => d.dataset_id === selectedDatasetId);

  async function loadChatState() {
    setLoadingHistory(true);
    try {
      const [history, rules] = await Promise.all([
        fetchAssistantHistory(selectedDatasetId || null, 80),
        fetchSessionRules(selectedDatasetId || null)
      ]);
      
      setActiveRules(rules);
      
      if (history && history.length > 0) {
        setMessages(history);
      } else {
        setMessages([buildIntroMessage(selectedDataset?.name)]);
      }
    } catch (err) {
      console.error('Failed to load chat history', err);
      setMessages([buildIntroMessage(selectedDataset?.name)]);
    } finally {
      setLoadingHistory(false);
    }
  }

  const handleSend = async (textToSend) => {
    const text = (textToSend || inputMessage).trim();
    if (!text || loading) return;

    setInputMessage('');
    
    // Add user message to local state immediately
    const userMsg = {
      id: `u-${Date.now()}`,
      role: 'user',
      text,
      created_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await sendAssistantMessage(
        text,
        true,
        selectedDatasetId || null,
        true
      );

      if (res) {
        setLlmStatus({ enabled: res.llm_used, model: res.model_name });
        
        // Add assistant reply to local state
        const assistantReply = {
          id: `a-${Date.now()}`,
          role: 'assistant',
          text: res.reply || 'No response received.',
          plan: res.plan,
          result: res.result,
          suggested_next: res.suggested_next,
          created_at: new Date().toISOString()
        };
        
        setMessages(prev => [...prev, assistantReply]);

        // Refresh active rules in case the message injected a rule
        const rules = await fetchSessionRules(selectedDatasetId || null);
        setActiveRules(rules);
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, {
        id: `err-${Date.now()}`,
        role: 'assistant',
        text: 'Sorry, I encountered an issue while communicating with the multi-agent pipeline. Please make sure the backend server is active.',
        created_at: new Date().toISOString()
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleClearChat = async () => {
    if (!window.confirm('Are you sure you want to clear the conversation history for this scope?')) return;
    try {
      await clearAssistantHistory(selectedDatasetId || null);
      await loadChatState();
    } catch (err) {
      console.error(err);
    }
  };

  // Default helper suggestions
  const suggestions = selectedDatasetId ? [
    `List high-risk accounts in ${selectedDataset?.name}`,
    `Explain the biggest money laundering clusters found`,
    `Summarize AML-101 structuring rule triggers in this dataset`,
    `Draft an executive summary of this batch's compliance health`
  ] : [
    'How do structuring compliance rules work?',
    'What are circular money flow patterns in financial graph networks?',
    'Explain the role of SHAP features in evaluating AML risk',
    'How does a multi-agent system cooperate to reduce false positives?'
  ];

  // Helper for computing mock risk level / details
  const getRiskStyles = (level) => {
    switch (level?.toLowerCase()) {
      case 'high': return { color: '#ef4444', bg: 'rgba(239, 68, 68, 0.12)', border: 'rgba(239, 68, 68, 0.3)' };
      case 'medium': return { color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.12)', border: 'rgba(245, 158, 11, 0.3)' };
      case 'low': return { color: '#10b981', bg: 'rgba(16, 185, 129, 0.12)', border: 'rgba(16, 185, 129, 0.3)' };
      default: return { color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.12)', border: 'rgba(148, 163, 184, 0.3)' };
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', height: 'calc(100vh - 7rem)' }}>
      {/* Header Row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minHeight: '3rem' }}>
        <div>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <MessageSquare color="#3b82f6" />
            AI Compliance Copilot
          </h2>
          <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Investigate case histories, query ML top importances, and interact with the agentic reasoning loop.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          {/* Dataset Scope Picker */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--card-bg-alt)', border: '1px solid var(--border-soft)', padding: '0.35rem 0.75rem', borderRadius: '8px' }}>
            <Database size={14} color="var(--text-secondary)" />
            <select 
              value={selectedDatasetId} 
              onChange={(e) => setSelectedDatasetId(e.target.value)}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-primary)',
                fontSize: '0.8rem',
                fontWeight: 600,
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              <option value="">Global Assistant Scope</option>
              {datasets.map(d => (
                <option key={d.dataset_id} value={d.dataset_id}>
                  Scope: {d.name.length > 22 ? d.name.slice(0, 22) + '...' : d.name}
                </option>
              ))}
            </select>
          </div>

          <button 
            onClick={handleClearChat}
            style={{ 
              background: 'rgba(239, 68, 68, 0.08)', 
              border: '1px solid rgba(239, 68, 68, 0.2)', 
              color: '#ef4444', 
              padding: '0.5rem 1rem', 
              borderRadius: '8px', 
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              fontSize: '0.8rem',
              fontWeight: 700
            }}
            title="Clear Chat History"
          >
            <Trash2 size={14} />
            Wipe
          </button>
        </div>
      </div>

      {/* Main Split Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '1.5rem', flex: 1, overflow: 'hidden' }}>
        
        {/* Left Side: Conversational Arena */}
        <div style={{ 
          border: '1px solid var(--border-soft)', 
          background: 'var(--card-bg-alt)', 
          borderRadius: '14px', 
          display: 'flex', 
          flexDirection: 'column', 
          overflow: 'hidden',
          position: 'relative'
        }}>
          {/* Active Model Indicator */}
          <div style={{ 
            background: 'var(--card-bg)', 
            borderBottom: '1px solid var(--border-soft)', 
            padding: '0.5rem 1rem', 
            display: 'flex', 
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '0.75rem',
            color: 'var(--text-secondary)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Cpu size={12} color="#a855f7" />
              <span>Pipeline NLP Layer: <strong>{llmStatus.enabled ? `Ollama (${llmStatus.model})` : 'Enhanced Deterministic Lexicon'}</strong></span>
            </div>
            {llmStatus.enabled && (
              <span style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: '0.2rem', fontWeight: 700 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981' }}></span>
                Real-time Augmentation Active
              </span>
            )}
          </div>

          {/* Messages Stream */}
          <div style={{ 
            flex: 1, 
            padding: '1.5rem', 
            overflowY: 'auto', 
            display: 'flex', 
            flexDirection: 'column', 
            gap: '1rem' 
          }}>
            {loadingHistory ? (
              <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '0.8rem', color: 'var(--text-secondary)' }}>
                <RefreshCw className="animate-spin" size={24} color="#3b82f6" />
                <span>Loading conversation logs...</span>
              </div>
            ) : (
              messages.map((msg, idx) => {
                const isUser = msg.role === 'user';
                return (
                  <div 
                    key={msg.id || idx} 
                    style={{ 
                      display: 'flex', 
                      justifyContent: isUser ? 'flex-end' : 'flex-start',
                      width: '100%' 
                    }}
                  >
                    <div style={{ 
                      maxWidth: '80%',
                      background: isUser ? 'linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(147, 51, 234, 0.15))' : 'var(--card-bg)',
                      border: isUser ? '1px solid rgba(59, 130, 246, 0.25)' : '1px solid var(--border-soft)',
                      padding: '1rem',
                      borderRadius: isUser ? '14px 14px 2px 14px' : '14px 14px 14px 2px',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                      lineHeight: 1.5,
                      fontSize: '0.85rem'
                    }}>
                      {/* Message Text */}
                      <p style={{ margin: 0, whiteSpace: 'pre-wrap', color: 'var(--text-primary)' }}>
                        {msg.text}
                      </p>

                      {/* Display NLP reasoning plan / SAR draft results if included */}
                      {!isUser && msg.plan && (
                        <div style={{ marginTop: '0.75rem', background: 'rgba(255,255,255,0.02)', padding: '0.6rem 0.8rem', borderRadius: '8px', borderLeft: '3px solid #3b82f6', fontSize: '0.78rem' }}>
                          <strong style={{ color: '#60a5fa', display: 'block', marginBottom: '0.2rem' }}>Investigation Plan:</strong>
                          {msg.plan}
                        </div>
                      )}
                      {!isUser && msg.result && (
                        <div style={{ marginTop: '0.75rem', background: 'rgba(255,255,255,0.02)', padding: '0.6rem 0.8rem', borderRadius: '8px', borderLeft: '3px solid #10b981', fontSize: '0.78rem' }}>
                          <strong style={{ color: '#34d399', display: 'block', marginBottom: '0.2rem' }}>Audit Verdict:</strong>
                          {msg.result}
                        </div>
                      )}
                      
                      {/* Suggested actions from response */}
                      {!isUser && msg.suggested_next && (
                        <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                          {msg.suggested_next.split(/,|\n/).map((act, index) => {
                            const cleanAction = act.trim().replace(/^-\s*/, '');
                            if (!cleanAction) return null;
                            return (
                              <button 
                                key={index}
                                onClick={() => handleSend(cleanAction)}
                                style={{
                                  background: 'rgba(168, 85, 247, 0.08)',
                                  border: '1px solid rgba(168, 85, 247, 0.2)',
                                  borderRadius: '6px',
                                  color: '#c084fc',
                                  padding: '0.2rem 0.5rem',
                                  fontSize: '0.72rem',
                                  cursor: 'pointer',
                                  fontWeight: 600
                                }}
                              >
                                {cleanAction} →
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}

            {/* Waiting for response loader */}
            {loading && (
              <div style={{ display: 'flex', justifyContent: 'flex-start', width: '100%' }}>
                <div style={{ 
                  background: 'var(--card-bg)', 
                  border: '1px solid var(--border-soft)',
                  padding: '1rem',
                  borderRadius: '14px 14px 14px 2px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontSize: '0.8rem',
                  color: 'var(--text-secondary)'
                }}>
                  <span className="dot-pulse"></span>
                  <span>Compliance Agents thinking...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Quick suggestions if thread is empty or simple */}
          {messages.length <= 1 && !loading && (
            <div style={{ padding: '0 1.5rem 1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.7rem', fontWeight: 800, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Prompt Suggestions
              </span>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                {suggestions.map((s, idx) => (
                  <button 
                    key={idx} 
                    onClick={() => handleSend(s)}
                    style={{
                      background: 'var(--card-bg)',
                      border: '1px solid var(--border-soft)',
                      borderRadius: '8px',
                      padding: '0.6rem 0.8rem',
                      textAlign: 'left',
                      fontSize: '0.76rem',
                      color: 'var(--text-primary)',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '0.4rem'
                    }}
                    className="hover-card"
                  >
                    <span>{s}</span>
                    <ArrowRight size={12} color="#3b82f6" style={{ flexShrink: 0 }} />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input Panel */}
          <form 
            onSubmit={(e) => { e.preventDefault(); handleSend(); }}
            style={{ 
              background: 'var(--card-bg)', 
              borderTop: '1px solid var(--border-soft)', 
              padding: '1rem',
              display: 'flex',
              gap: '0.75rem' 
            }}
          >
            <input 
              type="text" 
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder={selectedDatasetId ? `Chat scoped to ${selectedDataset?.name}...` : "Talk to Compliance Copilot globally..."}
              disabled={loading}
              style={{
                flex: 1,
                background: 'var(--bg-main)',
                border: '1px solid var(--border-soft)',
                borderRadius: '10px',
                padding: '0.75rem 1rem',
                color: 'var(--text-primary)',
                fontSize: '0.85rem',
                outline: 'none'
              }}
            />
            <button 
              type="submit"
              disabled={loading || !inputMessage.trim()}
              style={{
                background: loading || !inputMessage.trim() ? 'rgba(59, 130, 246, 0.4)' : '#3b82f6',
                border: 'none',
                borderRadius: '10px',
                color: 'white',
                padding: '0.75rem 1.25rem',
                cursor: loading || !inputMessage.trim() ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.4rem',
                fontWeight: 700
              }}
            >
              <Send size={14} />
              Verify
            </button>
          </form>

        </div>

        {/* Right Side: Insights Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', overflowY: 'auto' }}>
          
          {/* Selected Dataset Summary */}
          <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.25rem' }}>
            <h3 style={{ margin: '0 0 0.8rem', fontSize: '0.92rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <ShieldAlert size={14} color="#3b82f6" />
              Target Scope Details
            </h3>

            {selectedDataset ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.78rem' }}>
                <div style={{ borderBottom: '1px solid var(--border-soft)', paddingBottom: '0.5rem' }}>
                  <strong style={{ display: 'block', fontSize: '0.82rem', marginBottom: '0.15rem' }}>{selectedDataset.name}</strong>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>Dataset ID: <code>{selectedDataset.dataset_id}</code></span>
                </div>
                
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Size & Rows:</span>
                  <strong>{selectedDataset.human_size} ({selectedDataset.total_rows?.toLocaleString()})</strong>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Base Fraud Rate:</span>
                  <strong style={{ color: '#ef4444' }}>{selectedDataset.fraud_pct || 'Calculating'}</strong>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Evaluated Risk:</span>
                  <span style={{
                    fontSize: '0.66rem',
                    fontWeight: 800,
                    textTransform: 'uppercase',
                    padding: '0.1rem 0.4rem',
                    borderRadius: '4px',
                    color: getRiskStyles(selectedDataset.risk_level).color,
                    background: getRiskStyles(selectedDataset.risk_level).bg,
                    border: '1px solid currentColor'
                  }}>
                    {selectedDataset.risk_level || 'UNKNOWN'}
                  </span>
                </div>
              </div>
            ) : (
              <p style={{ margin: 0, fontSize: '0.76rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                Select a dataset batch from the top scope picker to load specific risk variables, custom fraud indexes, and context tokens.
              </p>
            )}
          </div>

          {/* Active Rules Count & Inject Links */}
          <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.25rem' }}>
            <h3 style={{ margin: '0 0 0.8rem', fontSize: '0.92rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <FileText size={14} color="#a855f7" />
              Session Rules Injected
            </h3>

            {activeRules.length === 0 ? (
              <p style={{ margin: 0, fontSize: '0.76rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                No active custom session rules. Standard heuristics are running. You can inject custom guidance by saying: 
                <code style={{ display: 'block', marginTop: '0.4rem', color: '#a855f7', background: 'rgba(168, 85, 247, 0.08)', padding: '0.3rem', borderRadius: '4px', fontSize: '0.7rem' }}>
                  "In this session, flag all transactions over INR 100000"
                </code>
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <span style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
                  <strong>{activeRules.length} rules</strong> active in LLM contexts.
                </span>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', maxHeight: '120px', overflowY: 'auto', border: '1px solid var(--border-soft)', background: 'var(--card-bg)', padding: '0.5rem', borderRadius: '8px' }}>
                  {activeRules.map((rule, idx) => (
                    <div key={idx} style={{ fontSize: '0.7rem', borderBottom: '1px solid rgba(148,163,184,0.08)', paddingBottom: '0.2rem', color: 'var(--text-primary)' }}>
                      🔍 {rule.description || rule.rule_type || 'Custom rule'}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Quick Actions */}
          <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <h3 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Activity size={14} color="#10b981" />
              Investigation Quick Actions
            </h3>

            <button 
              onClick={() => handleSend("Draft an investigator-ready compliance narrative for the flagged accounts.")}
              style={{
                background: 'var(--card-bg)',
                border: '1px solid var(--border-soft)',
                borderRadius: '8px',
                padding: '0.5rem',
                textAlign: 'left',
                fontSize: '0.74rem',
                cursor: 'pointer',
                fontWeight: 600,
                color: 'var(--text-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}
              className="hover-card"
            >
              <span>Draft Compliance Narrative</span>
              <Sparkles size={12} color="#a855f7" />
            </button>

            <button 
              onClick={() => handleSend("Show high risk entities and circular money patterns detected in active graph.")}
              style={{
                background: 'var(--card-bg)',
                border: '1px solid var(--border-soft)',
                borderRadius: '8px',
                padding: '0.5rem',
                textAlign: 'left',
                fontSize: '0.74rem',
                cursor: 'pointer',
                fontWeight: 600,
                color: 'var(--text-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}
              className="hover-card"
            >
              <span>Detect Graph money loops</span>
              <Sparkles size={12} color="#3b82f6" />
            </button>
          </div>

        </div>

      </div>
    </div>
  );
}
