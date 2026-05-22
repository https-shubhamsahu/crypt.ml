import React, { useState, useEffect } from 'react';
import { 
  fetchModelInfo, 
  trainModelInlineCsv, 
  fetchGeneratorSchemas, 
  generateSyntheticAndSave 
} from '../api/ml';
import { 
  Binary, 
  Activity, 
  Sliders, 
  Upload, 
  Cpu, 
  TrendingUp, 
  RefreshCw, 
  Sparkles, 
  CheckCircle,
  FileText,
  AlertTriangle
} from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from 'recharts';

export default function ModelStudio() {
  // Model Stats State
  const [modelInfo, setModelInfo] = useState(null);
  const [loadingModel, setLoadingModel] = useState(true);
  const [trainingBusy, setTrainingBusy] = useState(false);
  const [targetRecall, setTargetRecall] = useState(0.70);

  // File Upload State
  const [uploadFile, setUploadFile] = useState(null);
  const [csvContent, setCsvContent] = useState('');
  const [uploadProgress, setUploadProgress] = useState('');

  // Synthetic Generator State
  const [generatorSettings, setGeneratorSettings] = useState({
    schema: 'aml_cft',
    numRows: 9500,
    fraudRatioPct: 15,
    seed: 42,
  });
  const [generatorBusy, setGeneratorBusy] = useState(false);
  const [schemas, setSchemas] = useState({});

  useEffect(() => {
    loadModelStudioAssets();
  }, []);

  async function loadModelStudioAssets() {
    setLoadingModel(true);
    try {
      const [info, listSchemas] = await Promise.all([
        fetchModelInfo(),
        fetchGeneratorSchemas()
      ]);
      if (info) setModelInfo(info);
      if (listSchemas) setSchemas(listSchemas);
    } catch (err) {
      console.error('Failed to load Model Studio resources', err);
    } finally {
      setLoadingModel(false);
    }
  }

  // Handle CSV file selection & reading
  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadFile(file);
    setUploadProgress('Reading file...');

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result;
      setCsvContent(text);
      setUploadProgress(`Ready (${Math.round(text.length / 1024)} KB)`);
    };
    reader.onerror = () => {
      setUploadProgress('Failed to read file.');
    };
    reader.readAsText(file);
  };

  // Train model on selected CSV
  const handleTrainModel = async (e) => {
    e.preventDefault();
    if (!csvContent || trainingBusy) return;

    setTrainingBusy(true);
    setUploadProgress('Retraining model... this may take a few seconds');
    try {
      const res = await trainModelInlineCsv(
        csvContent,
        targetRecall,
        uploadFile?.name || 'uploaded_training.csv'
      );
      if (res?.status === 'trained') {
        setModelInfo(res);
        setUploadProgress('Retraining completed successfully!');
        setUploadFile(null);
        setCsvContent('');
      } else {
        setUploadProgress('Training failed. Please verify CSV schema.');
      }
    } catch (err) {
      console.error(err);
      setUploadProgress('Training failed due to server error.');
    } finally {
      setTrainingBusy(false);
    }
  };

  // Generate synthetic CSV and save
  const handleGenerateSynthetic = async (e) => {
    e.preventDefault();
    if (generatorBusy) return;

    setGeneratorBusy(true);
    try {
      const payload = {
        schema: generatorSettings.schema,
        num_rows: parseInt(generatorSettings.numRows, 10) || 1000,
        fraud_ratio: (parseFloat(generatorSettings.fraudRatioPct) || 15) / 100,
        seed: parseInt(generatorSettings.seed, 10) || 42,
        num_accounts: 200,
        start_date: '2025-01-01',
        days_span: 90
      };

      const res = await generateSyntheticAndSave(payload);
      if (res) {
        alert(`Successfully generated synthetic batch: ${res.schema} with ${res.rows} rows saved to disk! View it in Overview.`);
        // Reload model info to capture any dataset additions
        const info = await fetchModelInfo();
        if (info) setModelInfo(info);
      }
    } catch (err) {
      console.error(err);
      alert('Failed to generate synthetic data.');
    } finally {
      setGeneratorBusy(false);
    }
  };

  // Prepare SHAP values chart data
  const shapChartData = React.useMemo(() => {
    if (!modelInfo?.shap_top_features || !Array.isArray(modelInfo.shap_top_features)) {
      return [
        { feature: 'velocity_signal', value: 0.32 },
        { feature: 'transaction_amount', value: 0.28 },
        { feature: 'nlp_signal', value: 0.24 },
        { feature: 'account_presence', value: 0.08 },
      ];
    }
    return modelInfo.shap_top_features.slice(0, 8).map(f => ({
      feature: f.feature?.replaceAll('_', ' '),
      value: parseFloat(f.mean_abs_shap || f.importance || 0)
    })).sort((a, b) => b.value - a.value);
  }, [modelInfo]);

  // Color Palette for SHAP chart bars
  const colors = ['#3b82f6', '#8b5cf6', '#a855f7', '#d946ef', '#ec4899', '#f43f5e', '#ef4444', '#f97316'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Binary color="#9333ea" />
            ML Model Developer Studio
          </h2>
          <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Retrain compliance XGBoost classifiers, generate customized synthetic schemas, and inspect SHAP feature attributions.
          </p>
        </div>
        <button 
          onClick={loadModelStudioAssets}
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
          Sync Model
        </button>
      </div>

      {/* Model status bar */}
      <div style={{ 
        border: '1px solid var(--border-soft)', 
        background: 'var(--card-bg-alt)', 
        borderRadius: '14px', 
        padding: '1.25rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        position: 'relative',
        overflow: 'hidden'
      }}>
        <div style={{ position: 'absolute', top: 0, left: 0, bottom: 0, width: '4px', background: modelInfo?.model_available ? '#10b981' : '#f59e0b' }}></div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', paddingLeft: '0.5rem' }}>
          <div style={{ 
            padding: '0.6rem', 
            borderRadius: '10px', 
            background: modelInfo?.model_available ? 'rgba(16, 185, 129, 0.12)' : 'rgba(245, 158, 11, 0.12)', 
            color: modelInfo?.model_available ? '#10b981' : '#f59e0b' 
          }}>
            <Cpu size={24} />
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 800 }}>
              {modelInfo?.model_available ? 'XGBoost Classification Engine Active' : 'Deterministic Scoring Proxy Active'}
            </h3>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
              Artifact Path: <code>{modelInfo?.model_path || 'artifacts/ml_model.joblib'}</code>
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
          {modelInfo?.metadata && (
            <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.8rem' }}>
              <div>
                <span style={{ color: 'var(--text-secondary)', display: 'block', fontSize: '0.7rem' }}>ROC-AUC</span>
                <strong style={{ fontSize: '1.1rem', color: '#10b981' }}>{modelInfo.metadata.roc_auc ? parseFloat(modelInfo.metadata.roc_auc).toFixed(4) : 'N/A'}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-secondary)', display: 'block', fontSize: '0.7rem' }}>Decision Threshold</span>
                <strong style={{ fontSize: '1.1rem' }}>{modelInfo.metadata.threshold ? parseFloat(modelInfo.metadata.threshold).toFixed(2) : 'N/A'}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-secondary)', display: 'block', fontSize: '0.7rem' }}>Training Rows</span>
                <strong style={{ fontSize: '1.1rem' }}>{modelInfo.metadata.rows_used?.toLocaleString() || 'N/A'}</strong>
              </div>
            </div>
          )}
          <span style={{
            fontSize: '0.68rem',
            fontWeight: 800,
            textTransform: 'uppercase',
            padding: '0.25rem 0.6rem',
            borderRadius: '6px',
            background: modelInfo?.model_available ? 'rgba(16, 185, 129, 0.12)' : 'rgba(245, 158, 11, 0.12)',
            color: modelInfo?.model_available ? '#10b981' : '#f59e0b',
            border: '1px solid currentColor'
          }}>
            {modelInfo?.model_available ? 'TRAINED' : 'STANDBY'}
          </span>
        </div>
      </div>

      {/* Main Split Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '2rem' }}>
        
        {/* Left Side: Model Studio Training and Feature Analysis */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* SHAP Chart panel */}
          <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.5rem' }}>
            <h3 style={{ margin: '0 0 0.5rem', fontSize: '1.05rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <TrendingUp size={16} color="#3b82f6" />
              SHAP Explainer: Top Predictive Risk Features
            </h3>
            <p style={{ margin: '0 0 1.5rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Mean absolute SHAP value impact. Higher scores dictate larger agent escalation decisions.
            </p>

            <div style={{ height: '240px', width: '100%' }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={shapChartData} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                  <XAxis type="number" stroke="var(--text-secondary)" fontSize={10} tickLine={false} />
                  <YAxis type="category" dataKey="feature" stroke="var(--text-secondary)" fontSize={10} tickLine={false} />
                  <Tooltip contentStyle={{ background: 'var(--bg-main)', borderColor: 'var(--border-soft)' }} />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={16}>
                    {shapChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Model retraining form */}
          <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.5rem' }}>
            <h3 style={{ margin: '0 0 0.5rem', fontSize: '1.05rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Upload size={16} color="#10b981" />
              Retrain Classification Classifier (XGBoost)
            </h3>
            <p style={{ margin: '0 0 1.25rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Provide a local transaction CSV training file to retrain the underlying ML intelligence matrices.
            </p>

            <form onSubmit={handleTrainModel} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              
              <div style={{ 
                border: '1px dashed var(--border-soft)', 
                background: 'var(--card-bg)', 
                borderRadius: '10px', 
                padding: '1.5rem',
                textAlign: 'center',
                cursor: 'pointer',
                position: 'relative'
              }} className="hover-card">
                <input 
                  type="file" 
                  accept=".csv" 
                  onChange={handleFileChange}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    opacity: 0,
                    cursor: 'pointer'
                  }}
                />
                <Upload size={24} color="var(--text-secondary)" style={{ margin: '0 auto 0.5rem' }} />
                <span style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700 }}>
                  {uploadFile ? uploadFile.name : 'Select or Drop CSV Data File'}
                </span>
                <span style={{ display: 'block', fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                  Supported fields: Amount, Sender_account, Receiver_account, Payment_type...
                </span>
              </div>

              {uploadProgress && (
                <div style={{ 
                  fontSize: '0.76rem', 
                  color: uploadProgress.includes('successfully') ? '#10b981' : (uploadProgress.includes('failed') ? '#ef4444' : 'var(--text-secondary)'),
                  background: 'rgba(255,255,255,0.01)',
                  padding: '0.5rem 0.8rem',
                  borderRadius: '6px',
                  border: '1px solid var(--border-soft)',
                  fontWeight: 600
                }}>
                  {uploadProgress}
                </div>
              )}

              <div className="inline-row" style={{ display: 'flex', gap: '1rem' }}>
                <div className="form-group" style={{ flex: 1 }}>
                  <label>Target Decision Recall Threshold</label>
                  <input 
                    type="number" 
                    step="0.01" 
                    min="0.5" 
                    max="0.99"
                    value={targetRecall} 
                    onChange={(e) => setTargetRecall(parseFloat(e.target.value))} 
                    required 
                  />
                </div>
                <div style={{ display: 'flex', alignItems: 'flex-end', flex: 1 }}>
                  <button 
                    type="submit"
                    disabled={!csvContent || trainingBusy}
                    style={{
                      width: '100%',
                      background: (!csvContent || trainingBusy) ? 'rgba(16, 185, 129, 0.4)' : '#10b981',
                      border: 'none',
                      borderRadius: '10px',
                      color: 'white',
                      padding: '0.75rem',
                      fontWeight: 700,
                      cursor: (!csvContent || trainingBusy) ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.4rem',
                      height: '2.5rem'
                    }}
                  >
                    <Binary size={14} />
                    {trainingBusy ? 'Rebuilding Model Matrix...' : 'Execute Model Training'}
                  </button>
                </div>
              </div>

            </form>
          </div>

        </div>

        {/* Right Side: Synthetic Generator */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.5rem' }}>
            <h3 style={{ margin: '0 0 0.5rem', fontSize: '1.05rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Sliders size={16} color="#9333ea" />
              Synthetic Scenario Generator
            </h3>
            <p style={{ margin: '0 0 1.25rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Synthesize money laundering exposures and normal traffic profiles directly compiled to SQLite.
            </p>

            <form onSubmit={handleGenerateSynthetic} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              
              <div className="form-group">
                <label>Schema Core Type</label>
                <select 
                  value={generatorSettings.schema}
                  onChange={(e) => setGeneratorSettings(prev => ({ ...prev, schema: e.target.value }))}
                >
                  <option value="aml_cft">AML-CFT (Standard Format)</option>
                  <option value="paysim">PaySim Scenario (Mobile Money)</option>
                  <option value="unified">Unified Banking format</option>
                </select>
              </div>

              <div className="form-group">
                <label>Total Transactions Volume</label>
                <input 
                  type="number" 
                  min="100" 
                  max="100000"
                  value={generatorSettings.numRows}
                  onChange={(e) => setGeneratorSettings(prev => ({ ...prev, numRows: parseInt(e.target.value, 10) }))}
                  required 
                />
              </div>

              <div className="inline-row">
                <div className="form-group">
                  <label>Suspicious Fraud Ratio (%)</label>
                  <input 
                    type="number" 
                    step="0.1"
                    min="0.1"
                    max="95"
                    value={generatorSettings.fraudRatioPct}
                    onChange={(e) => setGeneratorSettings(prev => ({ ...prev, fraudRatioPct: parseFloat(e.target.value) }))}
                    required 
                  />
                </div>
                <div className="form-group">
                  <label>Random Generator Seed</label>
                  <input 
                    type="number" 
                    value={generatorSettings.seed}
                    onChange={(e) => setGeneratorSettings(prev => ({ ...prev, seed: parseInt(e.target.value, 10) }))}
                    required 
                  />
                </div>
              </div>

              <button 
                type="submit" 
                disabled={generatorBusy}
                style={{
                  background: generatorBusy ? 'rgba(147, 51, 234, 0.4)' : 'linear-gradient(90deg, #9333ea, #3b82f6)',
                  border: 'none',
                  borderRadius: '10px',
                  color: 'white',
                  padding: '0.75rem',
                  fontWeight: 700,
                  cursor: generatorBusy ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.4rem',
                  marginTop: '0.5rem'
                }}
              >
                <Sparkles size={14} />
                {generatorBusy ? 'Synthesizing transaction nodes...' : 'Compile & Save Synthetic Batch'}
              </button>

            </form>
          </div>

          {/* Model JSON Metadata */}
          {modelInfo?.metadata && (
            <div style={{ border: '1px solid var(--border-soft)', background: 'var(--card-bg-alt)', borderRadius: '14px', padding: '1.25rem' }}>
              <h3 style={{ margin: '0 0 0.8rem', fontSize: '0.92rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <FileText size={14} color="var(--text-secondary)" />
                Raw Artifact Metadata
              </h3>
              <pre style={{
                margin: 0,
                background: 'var(--card-bg)',
                border: '1px solid var(--border-soft)',
                padding: '0.75rem',
                borderRadius: '8px',
                fontSize: '0.68rem',
                fontFamily: 'monospace',
                overflowX: 'auto',
                maxHeight: '140px',
                color: 'var(--text-secondary)',
                lineHeight: 1.35
              }}>
                {JSON.stringify(modelInfo.metadata, null, 2)}
              </pre>
            </div>
          )}

        </div>

      </div>
    </div>
  );
}
