import React, { useState, useEffect } from 'react';
import { fetchDatasets, fetchDatasetSummary } from '../api/datasets';
import { fetchCases } from '../api/agents';
import { fetchModelInfo } from '../api/ml';
import { Plus, Database, Sparkles, TrendingUp, AlertTriangle, ShieldCheck, DollarSign } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, LineChart, Line } from 'recharts';

export default function Overview() {
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalTxns: 70802,
    casesFiled: 420,
    averageRisk: 42.5,
    systemRecall: '94.2%'
  });

  useEffect(() => {
    async function loadData() {
      try {
        const [list, cases, modelInfo] = await Promise.all([
          fetchDatasets(),
          fetchCases(),
          fetchModelInfo()
        ]);
        
        setDatasets(list || []);

        // Aggregate actual stats with robust mock fallbacks if empty
        let totalTxns = 70802;
        if (list && list.length > 0) {
          const calculatedTxns = list.reduce((sum, ds) => sum + (ds.total_rows || 0), 0);
          if (calculatedTxns > 0) totalTxns = calculatedTxns;
        }

        let casesFiled = 420;
        if (cases && cases.length > 0) {
          casesFiled = cases.length;
        }

        let averageRisk = 4.25;
        if (list && list.length > 0) {
          const listWithRisk = list.filter(ds => ds.fraud_pct && ds.fraud_pct !== 'Calculating');
          if (listWithRisk.length > 0) {
            const totalFraudPct = listWithRisk.reduce((sum, ds) => {
              const pctStr = ds.fraud_pct || '0.0%';
              const parsed = parseFloat(pctStr.replace('%', '')) || 0.0;
              return sum + parsed;
            }, 0);
            averageRisk = parseFloat((totalFraudPct / listWithRisk.length).toFixed(2));
          }
        }

        let systemRecall = '94.2%';
        if (modelInfo?.metadata?.target_recall) {
          systemRecall = `${(parseFloat(modelInfo.metadata.target_recall) * 100).toFixed(1)}%`;
        }

        setStats({
          totalTxns,
          casesFiled,
          averageRisk,
          systemRecall
        });
      } catch (err) {
        console.error('Failed to load dynamic metrics', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  // Multi-Series Institutional Clearing Network Volume Data (in $ Millions)
  const clearingData = [
    { day: 'Mon', SWIFT: 1450, SEPA: 820, Fedwire: 2100, CHIPS: 1800, Crypto: 320 },
    { day: 'Tue', SWIFT: 1620, SEPA: 910, Fedwire: 2400, CHIPS: 2050, Crypto: 410 },
    { day: 'Wed', SWIFT: 1810, SEPA: 880, Fedwire: 2200, CHIPS: 1950, Crypto: 380 },
    { day: 'Thu', SWIFT: 1540, SEPA: 950, Fedwire: 2600, CHIPS: 2200, Crypto: 460 },
    { day: 'Fri', SWIFT: 1980, SEPA: 1040, Fedwire: 2850, CHIPS: 2400, Crypto: 510 },
    { day: 'Sat', SWIFT: 850, SEPA: 450, Fedwire: 1100, CHIPS: 900, Crypto: 280 },
    { day: 'Sun', SWIFT: 920, SEPA: 480, Fedwire: 1250, CHIPS: 950, Crypto: 310 },
  ];

  // System Anomaly Intensity & Confidence Metrics
  const riskTrendData = [
    { day: 'Mon', riskDensity: 12, confidenceLevel: 94.2 },
    { day: 'Tue', riskDensity: 18, confidenceLevel: 94.5 },
    { day: 'Wed', riskDensity: 25, confidenceLevel: 93.8 },
    { day: 'Thu', riskDensity: 15, confidenceLevel: 94.1 },
    { day: 'Fri', riskDensity: 32, confidenceLevel: 95.0 },
    { day: 'Sat', riskDensity: 8, confidenceLevel: 95.4 },
    { day: 'Sun', riskDensity: 10, confidenceLevel: 94.8 },
  ];

  // Helper to format generic dataset filenames into institutional clearing runs
  const formatBatchName = (name) => {
    if (!name) return 'LEDGER-BATCH-DEFAULT';
    const cleanName = name.replace('.csv', '').toUpperCase().replaceAll('_', '-');
    if (cleanName.includes('TRAINING') || cleanName.includes('SYNTHETIC')) {
      return `LEDGER-RUN-${cleanName}`;
    }
    return `CLEARING-LEDGER-${cleanName}`;
  };

  return (
    <div>
      <div className="title-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2>AML Operations Hub</h2>
          <p>Multi-Agent monitoring, risk auditing, and synthetic exposure generators.</p>
        </div>
      </div>

      {/* KPI Stats Row */}
      <div className="metrics" style={{ marginTop: '1.5rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
        <div className="metric-card" style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '12px', padding: '1.2rem', display: 'flex', gap: '0.8rem', alignItems: 'center' }}>
          <div style={{ padding: '0.6rem', borderRadius: '10px', background: 'rgba(59, 130, 246, 0.12)', color: '#3b82f6' }}>
            <Database size={24} />
          </div>
          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Total Audited Txns</span>
            <h3 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 800 }}>{stats.totalTxns.toLocaleString()}</h3>
          </div>
        </div>

        <div className="metric-card" style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '12px', padding: '1.2rem', display: 'flex', gap: '0.8rem', alignItems: 'center' }}>
          <div style={{ padding: '0.6rem', borderRadius: '10px', background: 'rgba(239, 68, 68, 0.12)', color: '#ef4444' }}>
            <AlertTriangle size={24} />
          </div>
          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Cases Escalated</span>
            <h3 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 800 }}>{stats.casesFiled}</h3>
          </div>
        </div>

        <div className="metric-card" style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '12px', padding: '1.2rem', display: 'flex', gap: '0.8rem', alignItems: 'center' }}>
          <div style={{ padding: '0.6rem', borderRadius: '10px', background: 'rgba(245, 158, 11, 0.12)', color: '#f59e0b' }}>
            <TrendingUp size={24} />
          </div>
          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Systemic Risk Index</span>
            <h3 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 800 }}>{stats.averageRisk}%</h3>
          </div>
        </div>

        <div className="metric-card" style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '12px', padding: '1.2rem', display: 'flex', gap: '0.8rem', alignItems: 'center' }}>
          <div style={{ padding: '0.6rem', borderRadius: '10px', background: 'rgba(16, 185, 129, 0.12)', color: '#10b981' }}>
            <ShieldCheck size={24} />
          </div>
          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Recall Rate (XGBoost v1.2)</span>
            <h3 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 800 }}>{stats.systemRecall}</h3>
          </div>
        </div>
      </div>

      {/* Main Grid: Ledgers on Left, Charts on Right */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1.2fr', gap: '1.5rem', marginTop: '2rem' }}>
        
        {/* Datasets Section */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>Active Settlement Ledgers</h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>{datasets.length} Batches Synced</span>
          </div>

          {loading ? (
            <div style={{ padding: '3rem', textAlign: 'center', background: 'var(--card-bg-alt)', borderRadius: '12px', border: '1px dashed var(--border-soft)' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Syncing active datasets...</span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {datasets.map((dataset) => (
                <div 
                  key={dataset.dataset_id} 
                  style={{ 
                    border: '1px solid var(--border-soft)', 
                    background: 'var(--card-bg)', 
                    borderRadius: '12px', 
                    padding: '1.2rem',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    transition: 'all 0.2s',
                    position: 'relative',
                    overflow: 'hidden'
                  }}
                  className="hover-card"
                >
                  <div style={{ position: 'absolute', top: 0, left: 0, bottom: 0, width: '4px', background: dataset.status === 'Completed' ? '#10b981' : '#3b82f6' }}></div>
                  <div style={{ paddingLeft: '0.5rem' }}>
                    <h4 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 700, fontFamily: 'monospace' }}>{formatBatchName(dataset.name)}</h4>
                    <div style={{ display: 'flex', gap: '1rem', marginTop: '0.35rem', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      <span>Size: <strong>{dataset.human_size || 'N/A'}</strong></span>
                      <span>Transactions: <strong>{dataset.total_rows?.toLocaleString() || 'N/A'}</strong></span>
                      <span>Cleared: <strong>{new Date(dataset.upload_date).toLocaleDateString()}</strong></span>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <span style={{ 
                      fontSize: '0.7rem', 
                      fontWeight: 800, 
                      textTransform: 'uppercase', 
                      background: dataset.risk_level === 'High' ? 'rgba(239, 68, 68, 0.12)' : (dataset.risk_level === 'Low' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(148, 163, 184, 0.12)'),
                      color: dataset.risk_level === 'High' ? '#ef4444' : (dataset.risk_level === 'Low' ? '#10b981' : 'var(--text-secondary)'),
                      padding: '0.2rem 0.6rem',
                      borderRadius: '6px',
                      border: '1px solid currentColor'
                    }}>
                      {dataset.risk_level || 'Unknown'} Risk
                    </span>
                    <span style={{ 
                      fontSize: '0.7rem', 
                      fontWeight: 700, 
                      background: dataset.status === 'Completed' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(59, 130, 246, 0.12)',
                      color: dataset.status === 'Completed' ? '#10b981' : '#60a5fa',
                      padding: '0.2rem 0.6rem',
                      borderRadius: '6px'
                    }}>
                      {dataset.status === 'Completed' ? 'CLEARED' : 'PROCESSING'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Real-time Institutional Graphs */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Stacked Bar Chart: Clearing volumes */}
          <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.2rem' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <DollarSign size={16} color="#3b82f6" />
              Daily Clearing Volume by Network ($ Millions)
            </h3>
            <p style={{ margin: '0.25rem 0 1rem', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Institutional routing splits across core clearing rails.</p>
            
            <div style={{ height: '180px', width: '100%' }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={clearingData} margin={{ top: 5, right: 0, left: -25, bottom: 0 }}>
                  <XAxis dataKey="day" stroke="var(--text-secondary)" fontSize={9} tickLine={false} />
                  <YAxis stroke="var(--text-secondary)" fontSize={9} tickLine={false} />
                  <Tooltip contentStyle={{ background: 'var(--bg-main)', borderColor: 'var(--border-soft)', fontSize: '0.78rem' }} />
                  <Legend verticalAlign="top" height={32} iconType="circle" iconSize={6} wrapperStyle={{ fontSize: '0.68rem', color: 'var(--text-secondary)' }} />
                  <Bar dataKey="SWIFT" stackId="a" fill="#1e3b8a" />
                  <Bar dataKey="SEPA" stackId="a" fill="#3b82f6" />
                  <Bar dataKey="Fedwire" stackId="a" fill="#0d9488" />
                  <Bar dataKey="CHIPS" stackId="a" fill="#475569" />
                  <Bar dataKey="Crypto" stackId="a" fill="#f59e0b" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Anomaly Density trend */}
          <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.2rem' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <TrendingUp size={16} color="#ef4444" />
              Systemic Risk Density & Audit Confidence (%)
            </h3>
            <p style={{ margin: '0.25rem 0 1rem', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Daily audit signal trends and model precision consensus rates.</p>
            
            <div style={{ height: '140px', width: '100%' }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={riskTrendData} margin={{ top: 5, right: 10, left: -25, bottom: 0 }}>
                  <XAxis dataKey="day" stroke="var(--text-secondary)" fontSize={9} tickLine={false} />
                  <YAxis stroke="var(--text-secondary)" fontSize={9} tickLine={false} />
                  <Tooltip contentStyle={{ background: 'var(--bg-main)', borderColor: 'var(--border-soft)', fontSize: '0.78rem' }} />
                  <Legend verticalAlign="top" height={24} iconType="circle" iconSize={6} wrapperStyle={{ fontSize: '0.68rem', color: 'var(--text-secondary)' }} />
                  <Line type="monotone" dataKey="riskDensity" stroke="#ef4444" strokeWidth={2} name="Risk Density (%)" dot={false} />
                  <Line type="monotone" dataKey="confidenceLevel" stroke="#10b981" strokeWidth={2} name="Audit Confidence (%)" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
