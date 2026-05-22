import React, { useState, useEffect } from 'react';
import { fetchSessionRules, createSessionRule, clearSessionRules } from '../api/assistant';
import { Plus, Trash2, Shield, Eye, ShieldAlert, CheckCircle2 } from 'lucide-react';

export default function RuleEngine() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newRuleText, setNewRuleText] = useState('');
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    loadRules();
  }, []);

  async function loadRules() {
    setLoading(true);
    try {
      const list = await fetchSessionRules();
      setRules(list);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  const handleAddRule = async (e) => {
    e.preventDefault();
    const txt = newRuleText.trim();
    if (!txt || adding) return;

    setAdding(true);
    try {
      await createSessionRule(txt);
      setNewRuleText('');
      await loadRules();
    } catch (err) {
      console.error(err);
    } finally {
      setAdding(false);
    }
  };

  const handleClearRules = async () => {
    if (!window.confirm('Wipe all session compliance rules?')) return;
    try {
      await clearSessionRules();
      await loadRules();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2>Session Compliance Rules</h2>
          <p>Add custom heuristic checks or agent guidance tokens dynamically injected into compliance prompts.</p>
        </div>
        <button 
          onClick={handleClearRules}
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
        >
          <Trash2 size={14} />
          Clear All Rules
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.6fr', gap: '2rem' }}>
        
        {/* Left Side: Create Rule */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.5rem' }}>
            <h3 style={{ margin: '0 0 1rem', fontSize: '1.05rem', fontWeight: 800 }}>Define Custom Heuristic</h3>
            
            <form onSubmit={handleAddRule} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="form-group">
                <label>Rule Condition / Instruction</label>
                <textarea 
                  rows="4" 
                  value={newRuleText} 
                  onChange={(e) => setNewRuleText(e.target.value)} 
                  placeholder="e.g. Flag transactions exceeding INR 50000 with the note 'urgent' as critical bypass risk..."
                  required
                ></textarea>
              </div>

              <button 
                type="submit" 
                disabled={adding}
                style={{ 
                  background: adding ? 'rgba(59, 130, 246, 0.4)' : '#3b82f6', 
                  border: 'none', 
                  borderRadius: '10px', 
                  color: 'white', 
                  fontWeight: 700, 
                  padding: '0.7rem', 
                  cursor: adding ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                  marginTop: '0.5rem'
                }}
              >
                <Plus size={16} />
                {adding ? 'Injecting Heuristic...' : 'Commit Rule to Session'}
              </button>
            </form>
          </div>
        </div>

        {/* Right Side: Active Rules List */}
        <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.5rem' }}>
          <h3 style={{ margin: '0 0 1.25rem', fontSize: '1.05rem', fontWeight: 800 }}>Commited Session Heuristics</h3>

          {loading ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>Loading heuristics...</div>
          ) : rules.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
              <Shield size={32} style={{ opacity: 0.5 }} />
              <span>No custom heuristics injected. Standard RAW compliance rules are active.</span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {rules.map((rule, idx) => (
                <div 
                  key={idx} 
                  style={{ 
                    border: '1px solid var(--border-soft)', 
                    background: 'var(--card-bg)', 
                    borderRadius: '10px', 
                    padding: '1rem',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '0.75rem'
                  }}
                >
                  <div style={{ marginTop: '0.15rem', color: '#10b981' }}>
                    <CheckCircle2 size={16} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
                      <span style={{ fontSize: '0.66rem', fontWeight: 800, color: '#10b981', textTransform: 'uppercase' }}>
                        ACTIVE HEURISTIC #{idx + 1}
                      </span>
                      {rule.rule_type && (
                        <span style={{ fontSize: '0.6rem', background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', padding: '0.05rem 0.35rem', borderRadius: '4px', fontWeight: 700 }}>
                          {rule.rule_type}
                        </span>
                      )}
                    </div>
                    <p style={{ margin: 0, fontSize: '0.8rem', lineHeight: 1.45, color: 'var(--text-primary)' }}>
                      {rule.description || rule.text || (typeof rule === 'object' ? JSON.stringify(rule) : String(rule))}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
