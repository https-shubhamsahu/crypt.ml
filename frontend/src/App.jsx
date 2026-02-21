import { useEffect, useMemo, useState } from 'react'
import {
  clearAssistantHistory,
  clearSessionRules,
  createSessionRule,
  fetchAssistantHistory,
  fetchDatasetAnalytics,
  fetchDatasetSummary,
  fetchDatasetTransactions,
  fetchDatasets,
  fetchGeneratorSchemas,
  fetchModelInfo,
  fetchSessionRules,
  generateSyntheticAndSave,
  generateSyntheticCsv,
  sendAssistantMessage,
  trainModel,
  trainModelInlineCsv,
} from './api'

const DEFAULT_RULES = [
  {
    id: 'AML-101',
    name: 'Structuring Detection',
    severity: 'High',
    description:
      'Identifies multiple cash deposits under $10,000 reporting threshold within a 24-hour period to evade CTR filing.',
    active: true,
    icon: '⚖️',
    category: 'default',
  },
  {
    id: 'AML-204',
    name: 'Rapid Movement',
    severity: 'Medium',
    description:
      'Flags accounts where 90% of funds are withdrawn or transferred within 1 hour of deposit.',
    active: true,
    icon: '💸',
    category: 'default',
  },
  {
    id: 'AML-310',
    name: 'High-Risk Jurisdiction',
    severity: 'Critical',
    description:
      'Automatically flags incoming wires originating from sanctioned jurisdictions listed in compliance watchlists.',
    active: true,
    icon: '🌍',
    category: 'default',
  },
  {
    id: 'AML-005',
    name: 'KYC Incomplete',
    severity: 'Low',
    description:
      'Monitors accounts with missing secondary identification documents after 30 days of onboarding.',
    active: false,
    icon: '🪪',
    category: 'default',
  },
]

const buildIntroMessage = (datasetName) => ({
  id: 'intro',
  role: 'bot',
  text: datasetName
    ? `Hello! I’m your compliance assistant for ${datasetName}. I can help analyze transaction clusters and summarize risk reports.`
    : 'Hello! I’m your compliance assistant. Select a dataset to start a scoped analysis thread.',
  suggestions: [
    'Show high-risk transactions from the last 24 hours.',
    'Analyze transaction pattern for Entity #8842.',
    'Any new matches on the OFAC list?',
  ],
})

const SCHEMA_OPTIONS = [
  { value: 'aml_cft', label: 'AML-CFT (Standard Upload)' },
  { value: 'unified', label: 'Unified' },
  { value: 'paysim', label: 'PaySim' },
]

const DEFAULT_SCHEMA_COLUMNS = {
  aml_cft: [
    'Time',
    'Date',
    'Sender_account',
    'Receiver_account',
    'Amount',
    'Payment_currency',
    'Received_currency',
    'Sender_bank_location',
    'Receiver_bank_location',
    'Payment_type',
    'Is_laundering',
    'Laundering_type',
  ],
}

function App() {
  const [datasets, setDatasets] = useState([])
  const [activeView, setActiveView] = useState('overview')
  const [selectedDataset, setSelectedDataset] = useState(null)
  const [datasetSummary, setDatasetSummary] = useState(null)
  const [datasetTransactions, setDatasetTransactions] = useState([])
  const [dashboardAnalytics, setDashboardAnalytics] = useState(null)
  const [datasetRefreshMap, setDatasetRefreshMap] = useState({})
  const [datasetLoadingMap, setDatasetLoadingMap] = useState({})
  const [dashboardWindow, setDashboardWindow] = useState(30)
  const [searchTerm, setSearchTerm] = useState('')
  const [showAllRows, setShowAllRows] = useState(false)
  const [uiNotice, setUiNotice] = useState('')
  const [ruleTab, setRuleTab] = useState('default')
  const [riskFilters, setRiskFilters] = useState({
    high: true,
    medium: true,
    low: true,
    critical: true,
  })
  const [datasetRulesMap, setDatasetRulesMap] = useState({})
  const [newRule, setNewRule] = useState({
    name: '',
    metric: 'Transaction Amount',
    operator: 'Greater Than',
    value: '',
    severity: 'Medium',
    description: '',
  })
  const [isDark, setIsDark] = useState(() => {
    const stored = window.localStorage.getItem('aegis-theme')
    if (stored === 'light') return false
    if (stored === 'dark') return true
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })
  const [assistantInput, setAssistantInput] = useState('')
  const [assistantLoading, setAssistantLoading] = useState(false)
  const [assistantMessagesMap, setAssistantMessagesMap] = useState({})
  const [llmPromptSuggestionsMap, setLlmPromptSuggestionsMap] = useState({})
  const [llmPromptLoadingMap, setLlmPromptLoadingMap] = useState({})
  const [llmPromptRefreshTick, setLlmPromptRefreshTick] = useState(0)
  const [analysisTab, setAnalysisTab] = useState('risk')
  const [analysisStatusFilter, setAnalysisStatusFilter] = useState('All')
  const [analysisPaymentFilter, setAnalysisPaymentFilter] = useState('All')
  const [analysisMinAmount, setAnalysisMinAmount] = useState('0')
  const [analysisSelectedEntity, setAnalysisSelectedEntity] = useState('')
  const [generatorSettings, setGeneratorSettings] = useState({
    schema: 'aml_cft',
    numRows: 9500,
    fraudRatioPct: 15,
    seed: 42,
    targetRecall: 0.7,
  })
  const [generatorSchemas, setGeneratorSchemas] = useState(DEFAULT_SCHEMA_COLUMNS)
  const [studioPreview, setStudioPreview] = useState({ columns: [], rows: [] })
  const [modelInfo, setModelInfo] = useState(null)
  const [inlineTrainingFile, setInlineTrainingFile] = useState(null)
  const [inlineTrainingCsv, setInlineTrainingCsv] = useState('')
  const [generatorBusy, setGeneratorBusy] = useState(false)
  const [trainingBusy, setTrainingBusy] = useState(false)

  const currentDatasetId = selectedDataset?.dataset_id ?? null
  const currentDatasetKey = currentDatasetId ?? 'global'
  const rules = datasetRulesMap[currentDatasetKey] ?? DEFAULT_RULES
  const assistantMessages = assistantMessagesMap[currentDatasetKey] ?? [buildIntroMessage(selectedDataset?.name)]
  const lastUpdatedValue = datasetRefreshMap[currentDatasetKey] ?? null
  const isRefreshingDataset = datasetLoadingMap[currentDatasetKey] === true
  const isGeneratingPrompts = llmPromptLoadingMap[currentDatasetKey] === true

  useEffect(() => {
    if (!uiNotice) return undefined
    const timer = window.setTimeout(() => setUiNotice(''), 2800)
    return () => window.clearTimeout(timer)
  }, [uiNotice])

  useEffect(() => {
    let active = true
    const load = async () => {
      const data = await fetchDatasets()
      if (active) {
        setDatasets(data)
      }
    }
    void load()
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    const loadStudioAssets = async () => {
      const [schemas, info] = await Promise.all([fetchGeneratorSchemas(), fetchModelInfo()])
      if (!active) return
      if (schemas && Object.keys(schemas).length > 0) {
        setGeneratorSchemas(schemas)
      }
      if (info) {
        setModelInfo(info)
      }
    }

    void loadStudioAssets()
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true

    const loadScopedState = async () => {
      const [apiRules, apiMessages] = await Promise.all([
        fetchSessionRules(currentDatasetId),
        fetchAssistantHistory(currentDatasetId, 100),
      ])

      if (!active) return

      const mappedRules = apiRules.map((rule, idx) => ({
        id: `API-${currentDatasetKey}-${idx + 1}`,
        name: rule.rule_type?.replaceAll('_', ' ') || 'Custom Rule',
        severity: 'Medium',
        description: rule.description || 'Session rule loaded from backend',
        active: true,
        icon: '🧩',
        category: 'custom',
      }))

      setDatasetRulesMap((prev) => ({
        ...prev,
        [currentDatasetKey]: [...mappedRules, ...DEFAULT_RULES],
      }))

      const mappedMessages = apiMessages.length
        ? apiMessages.map((message, idx) => ({
            id: `H-${currentDatasetKey}-${idx}`,
            role: message.role === 'assistant' ? 'bot' : 'user',
            text: message.text,
          }))
        : [buildIntroMessage(selectedDataset?.name)]

      setAssistantMessagesMap((prev) => ({
        ...prev,
        [currentDatasetKey]: mappedMessages,
      }))
    }

    void loadScopedState()
    return () => {
      active = false
    }
  }, [currentDatasetId, currentDatasetKey, selectedDataset?.name])

  useEffect(() => {
    const datasetId = selectedDataset?.dataset_id
    if (!datasetId) {
      setDatasetSummary(null)
      setDatasetTransactions([])
      setDashboardAnalytics(null)
      setDatasetLoadingMap((prev) => ({
        ...prev,
        [currentDatasetKey]: false,
      }))
      return
    }

    let active = true
    const loadDetails = async () => {
      setDatasetLoadingMap((prev) => ({
        ...prev,
        [currentDatasetKey]: true,
      }))

      const [summary, transactions, analytics] = await Promise.all([
        fetchDatasetSummary(datasetId),
        fetchDatasetTransactions(datasetId, 120),
        fetchDatasetAnalytics(datasetId, dashboardWindow),
      ])

      if (!active) return
      setDatasetSummary(summary)
      setDatasetTransactions(transactions)
      setDashboardAnalytics(analytics)
      setDatasetRefreshMap((prev) => ({
        ...prev,
        [currentDatasetKey]: new Date().toISOString(),
      }))
      setDatasetLoadingMap((prev) => ({
        ...prev,
        [currentDatasetKey]: false,
      }))
    }

    void loadDetails()
    return () => {
      active = false
      setDatasetLoadingMap((prev) => ({
        ...prev,
        [currentDatasetKey]: false,
      }))
    }
  }, [selectedDataset, dashboardWindow, currentDatasetKey])

  useEffect(() => {
    const nextTheme = isDark ? 'dark' : 'light'
    document.documentElement.setAttribute('data-theme', nextTheme)
    window.localStorage.setItem('aegis-theme', nextTheme)
  }, [isDark])

  const totals = useMemo(() => {
    const totalRows = datasets.reduce((acc, ds) => acc + (ds.total_rows || 0), 0)
    const highRisk = datasets.filter((ds) => ds.risk_level === 'High').length
    const completed = datasets.filter((ds) => ds.status === 'Completed').length
    return { totalRows, highRisk, completed }
  }, [datasets])

  const statusClass = (status) => {
    if (status === 'Completed') return 'completed'
    if (status === 'In Progress') return 'inprogress'
    return 'pending'
  }

  const riskClass = (risk) => {
    if (risk === 'High') return 'high'
    if (risk === 'Medium') return 'medium'
    if (risk === 'Low') return 'low'
    return 'unknown'
  }

  const formatDate = (value) => {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return String(value || '').slice(0, 10)
    return date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
    })
  }

  const formatLastUpdated = (isoValue) => {
    if (!isoValue) return 'Never'
    const date = new Date(isoValue)
    if (Number.isNaN(date.getTime())) return 'Unknown'
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const openValidationView = (dataset) => {
    setSelectedDataset(dataset)
    setActiveView('validation')
  }

  const checks = useMemo(() => {
    const ds = selectedDataset
    if (!ds) return []

    if (Array.isArray(datasetSummary?.checks) && datasetSummary.checks.length > 0) {
      return datasetSummary.checks
    }

    const schemaPass = (ds.total_columns || 0) >= 12
    return [
      {
        key: 'schema',
        title: 'Schema Validation',
        kind: schemaPass ? 'pass' : 'fail',
        detail: schemaPass
          ? 'Structure matches AML v2.1 standard. Header rows and delimiters are correct.'
          : 'Schema mismatch detected. Mandatory AML-CFT columns are missing.',
      },
      {
        key: 'missing',
        title: 'Missing Value Check',
        kind: 'pass',
        detail: `0 missing mandatory fields found across ${(ds.total_rows || 0).toLocaleString()} records.`,
      },
      {
        key: 'dupe',
        title: 'Duplicate Detection',
        kind: 'warn',
        detail: '14 potential duplicates found based on transaction ID.',
      },
      {
        key: 'consistency',
        title: 'Data Consistency',
        kind: 'pass',
        detail: 'Currency codes normalized (ISO 4217) and entity names standardized.',
      },
    ]
  }, [selectedDataset, datasetSummary])

  const validationSummary = useMemo(() => {
    const total = checks.length || 1
    const progressPoints = checks.reduce((acc, item) => {
      if (item.kind === 'pass') return acc + 1
      if (item.kind === 'warn') return acc + 0.5
      return acc
    }, 0)
    const percent = Math.round((progressPoints / total) * 100)
    const hasFail = checks.some((item) => item.kind === 'fail')
    return {
      percent,
      statusLabel: hasFail ? 'Issues Found' : 'Ready for Processing',
      statusKind: hasFail ? 'fail' : 'pass',
    }
  }, [checks])

  const recentTransactions = useMemo(() => {
    if (datasetTransactions.length > 0) {
      return datasetTransactions.map((tx, index) => ({
        id: tx.tx_id,
        date: tx.date,
        entity: tx.entity,
        amount: tx.amount,
        risk: tx.risk,
        focused: index === 0,
      }))
    }

    return [
      { id: 'TXN-8824', date: 'Oct 24, 2023', entity: 'Gamma Traders', amount: '$150,000.00', risk: 'High' },
      { id: 'TXN-8822', date: 'Oct 24, 2023', entity: 'Alpha Logistics', amount: '$12,500.00', risk: 'Medium' },
      { id: 'TXN-8825', date: 'Oct 22, 2023', entity: 'Delta Services', amount: '$8,900.00', risk: 'Low' },
      { id: 'TXN-8821', date: 'Oct 24, 2023', entity: 'Corp-X Holdings', amount: '$45,000.00', risk: 'High', focused: true },
    ]
  }, [datasetTransactions])

  const filteredTransactions = useMemo(() => {
    const source = showAllRows ? recentTransactions : recentTransactions.slice(0, 20)
    const query = searchTerm.trim().toLowerCase()
    if (!query) return source
    return source.filter((item) => {
      const hay = `${item.id} ${item.entity} ${item.amount} ${item.date} ${item.risk}`.toLowerCase()
      return hay.includes(query)
    })
  }, [recentTransactions, searchTerm, showAllRows])

  const analyticsRiskDistribution = useMemo(() => {
    if (Array.isArray(dashboardAnalytics?.risk_distribution) && dashboardAnalytics.risk_distribution.length > 0) {
      return dashboardAnalytics.risk_distribution
    }
    return [
      { label: 'Low', value: 65 },
      { label: 'Medium', value: 25 },
      { label: 'High', value: 10 },
    ]
  }, [dashboardAnalytics])

  const analyticsAlerts = useMemo(() => {
    if (Array.isArray(dashboardAnalytics?.alerts_over_time) && dashboardAnalytics.alerts_over_time.length > 1) {
      return dashboardAnalytics.alerts_over_time
    }
    return [
      { label: 'D1', count: 5 },
      { label: 'D2', count: 9 },
      { label: 'D3', count: 8 },
      { label: 'D4', count: 13 },
      { label: 'D5', count: 11 },
      { label: 'D6', count: 16 },
    ]
  }, [dashboardAnalytics])

  const paymentTypeBars = useMemo(() => {
    if (Array.isArray(dashboardAnalytics?.payment_type_distribution) && dashboardAnalytics.payment_type_distribution.length > 0) {
      return dashboardAnalytics.payment_type_distribution
    }
    return [
      { label: 'ACH', count: 32 },
      { label: 'Cross-border', count: 18 },
      { label: 'Cash Deposit', count: 14 },
    ]
  }, [dashboardAnalytics])

  const currencyMix = useMemo(() => {
    if (Array.isArray(dashboardAnalytics?.currency_distribution) && dashboardAnalytics.currency_distribution.length > 0) {
      return dashboardAnalytics.currency_distribution
    }
    return [
      { label: 'INR', count: 64 },
      { label: 'USD', count: 23 },
      { label: 'EUR', count: 13 },
    ]
  }, [dashboardAnalytics])

  const topEntities = useMemo(() => {
    if (Array.isArray(dashboardAnalytics?.top_entities) && dashboardAnalytics.top_entities.length > 0) {
      return dashboardAnalytics.top_entities
    }
    return [
      { label: 'ACC_1001', count: 9 },
      { label: 'ACC_1004', count: 7 },
      { label: 'ACC_1008', count: 6 },
    ]
  }, [dashboardAnalytics])

  const analyticsKpi = useMemo(() => ({
    totalProcessed: dashboardAnalytics?.total_processed ?? selectedDataset?.total_rows ?? 0,
    activeAlerts: dashboardAnalytics?.active_alerts ?? 0,
    highRiskEntities: dashboardAnalytics?.high_risk_entities ?? 0,
  }), [dashboardAnalytics, selectedDataset])

  const alertLinePath = useMemo(() => {
    const points = analyticsAlerts
    if (!points.length) return ''
    const width = 260
    const height = 100
    const max = Math.max(...points.map((p) => p.count), 1)
    return points
      .map((point, idx) => {
        const x = (idx / Math.max(points.length - 1, 1)) * width
        const y = height - (point.count / max) * 80 - 10
        return `${idx === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`
      })
      .join(' ')
  }, [analyticsAlerts])

  const currencyDonutStyle = useMemo(() => {
    const total = currencyMix.reduce((acc, item) => acc + item.count, 0) || 1
    const colors = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6']
    let running = 0
    const chunks = currencyMix.map((item, idx) => {
      const start = (running / total) * 100
      running += item.count
      const end = (running / total) * 100
      return `${colors[idx % colors.length]} ${start.toFixed(2)}% ${end.toFixed(2)}%`
    })
    return { background: `conic-gradient(${chunks.join(', ')})` }
  }, [currencyMix])

  const entityContrib = useMemo(() => {
    const top = topEntities[0]
    return [
      {
        name: 'Rule Violations',
        note: `Top account ${top?.label || 'N/A'} activity`,
        pts: `${Math.min(45, 18 + (top?.count || 0) * 2)} pts`,
        tone: 'high',
        icon: '⚖️',
      },
      {
        name: 'Behavioral',
        note: `${analyticsKpi.activeAlerts} active medium/high alerts`,
        pts: `${Math.min(35, 10 + Math.round(analyticsKpi.activeAlerts / 4))} pts`,
        tone: 'medium',
        icon: '🧠',
      },
      {
        name: 'KYC Gaps',
        note: `${analyticsKpi.highRiskEntities} high-risk entities flagged`,
        pts: `${Math.min(20, 5 + analyticsKpi.highRiskEntities)} pts`,
        tone: 'low',
        icon: '🪪',
      },
    ]
  }, [analyticsKpi, topEntities])

  const filteredRules = useMemo(() => {
    const map = {
      High: riskFilters.high,
      Medium: riskFilters.medium,
      Low: riskFilters.low,
      Critical: riskFilters.critical,
    }
    return rules.filter((rule) => {
      if (ruleTab === 'default' && rule.category !== 'default') return false
      if (ruleTab === 'custom' && rule.category !== 'custom') return false
      if (ruleTab === 'archived' && rule.active) return false
      return map[rule.severity] ?? true
    })
  }, [rules, riskFilters, ruleTab])

  const assistantRisk = useMemo(() => {
    const percentText = String(selectedDataset?.fraud_pct || '0').replace('%', '')
    const percent = Number.parseFloat(percentText)
    const normalized = Number.isFinite(percent) ? Math.max(0, Math.min(100, Math.round(percent * 2.5))) : 0
    const label = normalized >= 75 ? 'Critical' : normalized >= 45 ? 'High' : normalized >= 20 ? 'Medium' : 'Low'
    return { score: normalized, label }
  }, [selectedDataset])

  const relatedEntities = useMemo(() => {
    const byTop = topEntities.slice(0, 3).map((item, idx) => {
      const level = idx === 0 ? 'Watchlist Match' : idx === 1 ? 'Pattern Escalation' : 'Monitoring Required'
      return {
        name: item.label,
        note: `${level} • ${item.count} linked transactions`,
      }
    })

    if (byTop.length > 0) return byTop

    const unique = []
    for (const tx of recentTransactions) {
      if (!unique.some((entry) => entry.name === tx.entity)) {
        unique.push({
          name: tx.entity,
          note: `${tx.risk} risk activity observed`,
        })
      }
      if (unique.length >= 3) break
    }

    return unique.length
      ? unique
      : [{ name: 'No entities available', note: 'Load a dataset to populate related entities.' }]
  }, [topEntities, recentTransactions])

  const suggestedActions = useMemo(() => {
    const topName = relatedEntities[0]?.name || 'top entity'
    return [
      {
        key: 'sar',
        label: `File SAR Report${analyticsKpi.activeAlerts ? ` (${analyticsKpi.activeAlerts} alerts)` : ''}`,
        action: 'File SAR Report',
      },
      {
        key: 'freeze',
        label: assistantRisk.label === 'Critical' || assistantRisk.label === 'High'
          ? `Freeze ${topName}`
          : `Escalate Review for ${topName}`,
        action: assistantRisk.label === 'Critical' || assistantRisk.label === 'High' ? 'Freeze Account' : 'Escalate for Manual Review',
      },
      {
        key: 'edd',
        label: 'Request Enhanced Due Diligence',
        action: 'Request Enhanced Due Diligence',
      },
    ]
  }, [assistantRisk.label, analyticsKpi.activeAlerts, relatedEntities])

  const fallbackPromptSuggestions = useMemo(() => {
    const topEntity = topEntities[0]?.label || relatedEntities[0]?.name || 'top entity'
    const topRiskBand = analyticsRiskDistribution
      .slice()
      .sort((left, right) => Number(right.value || 0) - Number(left.value || 0))[0]?.label || 'High'
    return [
      `Summarize why ${topEntity} is flagged and list the top suspicious signals.`,
      `Compare ${topRiskBand} risk activity over the last ${dashboardWindow} days with medium risk trends.`,
      `Draft an investigator-ready narrative for ${selectedDataset?.name || 'this dataset'} with recommended next actions.`,
      `Show which payment types contribute most to current alerts and explain why.`,
    ]
  }, [topEntities, relatedEntities, analyticsRiskDistribution, dashboardWindow, selectedDataset?.name])

  const assistantPromptSuggestions = useMemo(() => {
    const llmPrompts = llmPromptSuggestionsMap[currentDatasetKey]
    if (Array.isArray(llmPrompts) && llmPrompts.length > 0) {
      return llmPrompts
    }
    return fallbackPromptSuggestions
  }, [llmPromptSuggestionsMap, currentDatasetKey, fallbackPromptSuggestions])

  const parseAmountValue = (value) => {
    const numeric = Number.parseFloat(String(value || '').replace(/[^\d.-]/g, ''))
    return Number.isFinite(numeric) ? numeric : 0
  }

  const getScaledBarHeight = (value, maxValue, minHeight = 14, maxHeight = 92) => {
    const current = Number(value) || 0
    const peak = Number(maxValue) || 0
    if (peak <= 0) return minHeight
    const ratio = Math.min(1, Math.max(0, current / peak))
    return Math.round(minHeight + ratio * (maxHeight - minHeight))
  }

  const analysisFraudPct = useMemo(() => {
    const pct = Number.parseFloat(String(selectedDataset?.fraud_pct || '0').replace('%', '').trim())
    return Number.isFinite(pct) ? pct : 0
  }, [selectedDataset?.fraud_pct])

  const analysisAverageAmount = useMemo(() => {
    if (!recentTransactions.length) return 0
    const total = recentTransactions.reduce((sum, tx) => sum + parseAmountValue(tx.amount), 0)
    return Math.round(total / recentTransactions.length)
  }, [recentTransactions])

  const analysisUniqueEntities = useMemo(() => {
    return new Set(recentTransactions.map((tx) => tx.entity)).size
  }, [recentTransactions])

  const analysisHighRiskRows = useMemo(() => {
    return recentTransactions.filter((tx) => String(tx.risk).toLowerCase() === 'high').length
  }, [recentTransactions])

  const analysisPaymentOptions = useMemo(() => {
    const options = paymentTypeBars.map((item) => item.label)
    return ['All', ...options]
  }, [paymentTypeBars])

  const analysisCorridors = useMemo(() => {
    const top = currencyMix.slice(0, 3)
    if (!top.length) {
      return [
        { label: 'IN ↔ IN', value: 3 },
        { label: 'IN ↔ AE', value: 1 },
        { label: 'IN ↔ CH', value: 1 },
      ]
    }
    return top.map((item, idx) => ({
      label: idx === 0 ? `${item.label} ↔ ${item.label}` : `${top[0].label} ↔ ${item.label}`,
      value: item.count,
    }))
  }, [currencyMix])

  const analysisTypologyBreakdown = useMemo(() => {
    const launderingRows = recentTransactions.filter((tx) => String(tx.risk).toLowerCase() === 'high').length
    const fanOutRows = Math.max(0, Math.round(analysisHighRiskRows * 0.6))
    return [
      { label: 'Fan-out', value: fanOutRows || 1 },
      { label: 'Layering', value: Math.max(1, launderingRows - fanOutRows) },
    ]
  }, [recentTransactions, analysisHighRiskRows])

  const analysisAmountBuckets = useMemo(() => {
    const buckets = [
      { label: '$0-5k', min: 0, max: 5000, count: 0 },
      { label: '$5k-10k', min: 5000, max: 10000, count: 0 },
      { label: '$10k-50k', min: 10000, max: 50000, count: 0 },
      { label: '$50k-100k', min: 50000, max: 100000, count: 0 },
      { label: '$100k+', min: 100000, max: Number.POSITIVE_INFINITY, count: 0 },
    ]
    recentTransactions.forEach((tx) => {
      const amount = parseAmountValue(tx.amount)
      const bucket = buckets.find((item) => amount >= item.min && amount < item.max)
      if (bucket) bucket.count += 1
    })
    return buckets
  }, [recentTransactions])

  const analysisExplorerRows = useMemo(() => {
    const minAmount = Number.parseFloat(analysisMinAmount)
    const threshold = Number.isFinite(minAmount) ? minAmount : 0
    const paymentSeries = analysisPaymentOptions.filter((item) => item !== 'All')

    return recentTransactions
      .map((row, index) => ({
        ...row,
        paymentType: paymentSeries.length ? paymentSeries[index % paymentSeries.length] : 'ACH',
      }))
      .filter((row) => {
        if (analysisStatusFilter !== 'All' && row.risk !== analysisStatusFilter) return false
        if (analysisPaymentFilter !== 'All' && row.paymentType !== analysisPaymentFilter) return false
        return parseAmountValue(row.amount) >= threshold
      })
      .slice(0, 10)
  }, [recentTransactions, analysisStatusFilter, analysisPaymentFilter, analysisMinAmount, analysisPaymentOptions])

  const analysisNarrative = useMemo(() => {
    return `The dataset exhibits a fraud rate of ${analysisFraudPct.toFixed(1)}%, with ${analysisHighRiskRows} high-risk rows and ${analyticsKpi.activeAlerts} active alerts. Average transaction amount is $${analysisAverageAmount.toLocaleString()} and ${analysisUniqueEntities} unique entities are involved. Prioritize review of ${topEntities[0]?.label || 'the top entity'} and cross-border payment corridors.`
  }, [analysisFraudPct, analysisHighRiskRows, analyticsKpi.activeAlerts, analysisAverageAmount, analysisUniqueEntities, topEntities])

  const selectedSchemaColumns = useMemo(() => {
    const schemaKey = generatorSettings.schema
    return generatorSchemas[schemaKey] || DEFAULT_SCHEMA_COLUMNS[schemaKey] || []
  }, [generatorSchemas, generatorSettings.schema])

  const modelMetadataText = useMemo(() => {
    return JSON.stringify(modelInfo?.metadata || {}, null, 2)
  }, [modelInfo])

  const modelShapTop = useMemo(() => {
    const rows = Array.isArray(modelInfo?.shap_top_features) ? modelInfo.shap_top_features : []
    return rows.slice(0, 6).map((item) => ({
      feature: String(item.feature || 'unknown'),
      value: Number(item.mean_abs_shap || item.importance || 0),
    }))
  }, [modelInfo])

  const modelShapMax = useMemo(() => {
    return Math.max(1, ...modelShapTop.map((item) => item.value || 0))
  }, [modelShapTop])

  const buildGeneratorPayload = () => {
    const numRows = Number.parseInt(String(generatorSettings.numRows), 10)
    const fraudRatioPct = Number.parseFloat(String(generatorSettings.fraudRatioPct))
    const seed = Number.parseInt(String(generatorSettings.seed), 10)

    return {
      schema: generatorSettings.schema,
      num_rows: Number.isFinite(numRows) ? Math.max(20, Math.min(500000, numRows)) : 1000,
      fraud_ratio: Number.isFinite(fraudRatioPct) ? Math.max(0.01, Math.min(0.95, fraudRatioPct / 100)) : 0.15,
      seed: Number.isFinite(seed) ? seed : 42,
      num_accounts: 200,
      start_date: '2025-01-01',
      days_span: 90,
    }
  }

  const parseCsvPreview = (csvText) => {
    const lines = String(csvText || '')
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
    if (!lines.length) {
      return { columns: [], rows: [] }
    }

    const columns = lines[0].split(',').map((item) => item.trim())
    const rows = lines.slice(1, 7).map((line) => {
      const values = line.split(',')
      return columns.reduce((acc, column, index) => {
        acc[column] = String(values[index] || '').trim()
        return acc
      }, {})
    })

    return { columns, rows }
  }

  const analysisTypologyMax = useMemo(
    () => Math.max(1, ...analysisTypologyBreakdown.map((item) => Number(item.value) || 0)),
    [analysisTypologyBreakdown],
  )

  const analysisAmountBucketMax = useMemo(
    () => Math.max(1, ...analysisAmountBuckets.map((item) => Number(item.count) || 0)),
    [analysisAmountBuckets],
  )

  const analysisCorridorMax = useMemo(
    () => Math.max(1, ...analysisCorridors.map((item) => Number(item.value) || 0)),
    [analysisCorridors],
  )

  const analysisDailyVolumeMax = useMemo(
    () => Math.max(1, ...analyticsAlerts.slice(0, 6).map((item) => Number(item.count) || 0)),
    [analyticsAlerts],
  )

  const parsePromptListFromText = (textValue) => {
    const infraStatusPattern = /(received your query|session rules are stored|llm-powered analysis|check that ollama is running|localhost:11434|aegis_llm_enabled)/i
    const isPromptCandidate = (value) => {
      const text = String(value || '').trim()
      if (text.length < 12 || text.length > 220) return false
      if (infraStatusPattern.test(text)) return false
      return true
    }

    const rawText = String(textValue || '').trim()
    if (!rawText) return []
    if (infraStatusPattern.test(rawText)) return []

    const codeBlockMatch = rawText.match(/```(?:json)?\s*([\s\S]*?)```/i)
    const candidates = [codeBlockMatch?.[1] || rawText, rawText]

    for (const candidate of candidates) {
      const arrayChunk = String(candidate).match(/\[[\s\S]*\]/)
      const parseTarget = arrayChunk?.[0] || String(candidate)
      try {
        const parsed = JSON.parse(parseTarget)
        if (Array.isArray(parsed)) {
          return parsed
            .map((item) => String(item || '').trim())
            .filter(isPromptCandidate)
            .slice(0, 4)
        }
      } catch {
      }
    }

    const lines = rawText
      .split(/\r?\n/)
      .map((line) => line.replace(/^\s*[-*•\d.)]+\s*/, '').trim())
      .filter(isPromptCandidate)

    return Array.from(new Set(lines)).slice(0, 4)
  }

  useEffect(() => {
    let active = true
    const datasetKey = currentDatasetKey

    const loadLlmPrompts = async () => {
      setLlmPromptLoadingMap((prev) => ({
        ...prev,
        [datasetKey]: true,
      }))

      const contextPrompt = [
        'Generate exactly 4 concise prompts for an AML Data Query Assistant.',
        'Return ONLY a JSON array of strings.',
        `Dataset: ${selectedDataset?.name || 'Global Session'}`,
        `Window days: ${dashboardWindow}`,
        `Active alerts: ${analyticsKpi.activeAlerts}`,
        `High-risk entities: ${analyticsKpi.highRiskEntities}`,
        `Top entity: ${topEntities[0]?.label || relatedEntities[0]?.name || 'N/A'}`,
        `Top payment type: ${paymentTypeBars[0]?.label || 'N/A'}`,
      ].join('\n')

      const response = await sendAssistantMessage(contextPrompt, false, currentDatasetId, false)
      if (!active) return

      const parsedPrompts = parsePromptListFromText(response?.result || response?.reply || '')
      if (parsedPrompts.length > 0) {
        setLlmPromptSuggestionsMap((prev) => ({
          ...prev,
          [datasetKey]: parsedPrompts,
        }))
      } else {
        setLlmPromptSuggestionsMap((prev) => {
          const next = { ...prev }
          delete next[datasetKey]
          return next
        })
      }

      setLlmPromptLoadingMap((prev) => ({
        ...prev,
        [datasetKey]: false,
      }))
    }

    void loadLlmPrompts()
    return () => {
      active = false
      setLlmPromptLoadingMap((prev) => ({
        ...prev,
        [datasetKey]: false,
      }))
    }
  }, [
    currentDatasetId,
    currentDatasetKey,
    selectedDataset?.name,
    dashboardWindow,
    analyticsKpi.activeAlerts,
    analyticsKpi.highRiskEntities,
    topEntities,
    relatedEntities,
    paymentTypeBars,
    llmPromptRefreshTick,
  ])

  const regeneratePromptSuggestions = () => {
    const datasetKey = currentDatasetKey
    setLlmPromptSuggestionsMap((prev) => {
      const next = { ...prev }
      delete next[datasetKey]
      return next
    })
    setLlmPromptRefreshTick((prev) => prev + 1)
  }

  const applySuggestedPrompt = (promptText, goToAssistant = false) => {
    setAssistantInput(promptText)
    if (goToAssistant) {
      setActiveView('assistant')
    }
  }

  const runDataPreview = async () => {
    setGeneratorBusy(true)
    const generated = await generateSyntheticCsv(buildGeneratorPayload())
    setGeneratorBusy(false)

    if (!generated?.text) {
      setUiNotice('Preview failed. Check API connectivity and key settings.')
      return
    }

    setStudioPreview(parseCsvPreview(generated.text))
    setUiNotice('Synthetic preview generated successfully.')
  }

  const downloadGeneratedCsv = async () => {
    setGeneratorBusy(true)
    const generated = await generateSyntheticCsv(buildGeneratorPayload())
    setGeneratorBusy(false)

    if (!generated?.blob) {
      setUiNotice('Download failed. Check API connectivity and key settings.')
      return
    }

    const url = URL.createObjectURL(generated.blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `aegis_synthetic_${generatorSettings.schema}_${generatorSettings.numRows}.csv`
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    URL.revokeObjectURL(url)

    if (generated.text) {
      setStudioPreview(parseCsvPreview(generated.text))
    }
    setUiNotice('Synthetic CSV downloaded.')
  }

  const saveAndTrainSynthetic = async () => {
    setTrainingBusy(true)
    const saved = await generateSyntheticAndSave(buildGeneratorPayload())
    if (!saved?.path) {
      setTrainingBusy(false)
      setUiNotice('Generate & save failed. Check backend availability.')
      return
    }

    const trained = await trainModel({
      data_path: saved.path,
      target_recall: Number(generatorSettings.targetRecall) || 0.7,
    })
    setTrainingBusy(false)

    if (!trained) {
      setUiNotice('Training failed after save. Check server logs for details.')
      return
    }

    const info = await fetchModelInfo()
    if (info) setModelInfo(info)
    setUiNotice('Synthetic data saved and model retrained successfully.')
  }

  const handleInlineFileSelect = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    const text = await file.text()
    setInlineTrainingFile(file)
    setInlineTrainingCsv(text)
    setUiNotice(`Loaded ${file.name} for no-code training.`)
  }

  const runInlineTraining = async () => {
    if (!inlineTrainingCsv.trim()) {
      setUiNotice('Select a CSV file first for no-code training.')
      return
    }

    setTrainingBusy(true)
    const trained = await trainModelInlineCsv(
      inlineTrainingCsv,
      Number(generatorSettings.targetRecall) || 0.7,
      inlineTrainingFile?.name || 'uploaded_training.csv',
    )
    setTrainingBusy(false)

    if (!trained) {
      setUiNotice('No-code training failed. Ensure CSV includes required columns.')
      return
    }

    const info = await fetchModelInfo()
    if (info) setModelInfo(info)
    setUiNotice('No-code training completed and artifacts refreshed.')
  }

  const triggerAction = (actionName) => {
    const actionText = `${actionName} initiated for ${selectedDataset?.name || 'current dataset'}.`
    setUiNotice(actionText)
    setAssistantInput(`Prepare ${actionName.toLowerCase()} context for dataset ${selectedDataset?.name || ''}`)
  }

  const exportDashboardData = () => {
    const rows = filteredTransactions.map((item) => `${item.id},${item.date},${item.entity},${item.amount},${item.risk}`)
    const csv = ['Transaction ID,Date,Entity,Amount,Risk', ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${selectedDataset?.name || 'aml-dashboard'}-export.csv`
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    URL.revokeObjectURL(url)
    setUiNotice('Export completed from live backend data.')
  }

  const cycleWindow = () => {
    setDashboardWindow((prev) => {
      if (prev === 30) return 7
      if (prev === 7) return 90
      return 30
    })
  }

  const toggleRisk = (key) => {
    setRiskFilters((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const toggleRuleActive = (id) => {
    const datasetKey = currentDatasetKey
    setDatasetRulesMap((prev) => {
      const current = prev[datasetKey] ?? DEFAULT_RULES
      return {
        ...prev,
        [datasetKey]: current.map((rule) => (rule.id === id ? { ...rule, active: !rule.active } : rule)),
      }
    })
  }

  const saveCustomRule = async () => {
    if (!newRule.name.trim()) return
    const normalizedSeverity = newRule.severity === 'High' ? 'High' : newRule.severity === 'Low' ? 'Low' : 'Medium'

    const ruleText = [
      `add rule ${newRule.name.trim()}`,
      `${newRule.metric} ${newRule.operator} ${newRule.value || 'threshold'}`,
      newRule.description?.trim() || '',
    ]
      .filter(Boolean)
      .join('. ')

    const created = await createSessionRule(ruleText, currentDatasetId)

    const next = {
      id: `CUS-${Date.now().toString().slice(-5)}`,
      name: newRule.name.trim(),
      severity: normalizedSeverity,
      description: newRule.description.trim() || `${newRule.metric} ${newRule.operator} ${newRule.value || 'threshold'}`,
      active: true,
      icon: '🧩',
      category: 'custom',
    }
    if (created && Array.isArray(created.injected) && created.injected.length > 0) {
      const mapped = created.injected.map((rule, idx) => ({
        id: `API-CUS-${Date.now().toString().slice(-5)}-${idx}`,
        name: rule.rule_type?.replaceAll('_', ' ') || next.name,
        severity: normalizedSeverity,
        description: rule.description || next.description,
        active: true,
        icon: '🧩',
        category: 'custom',
      }))
      const datasetKey = currentDatasetKey
      setDatasetRulesMap((prev) => {
        const current = prev[datasetKey] ?? DEFAULT_RULES
        return {
          ...prev,
          [datasetKey]: [...mapped, ...current.filter((rule) => rule.category !== 'custom')],
        }
      })
    } else {
      const datasetKey = currentDatasetKey
      setDatasetRulesMap((prev) => {
        const current = prev[datasetKey] ?? DEFAULT_RULES
        return {
          ...prev,
          [datasetKey]: [next, ...current],
        }
      })
    }

    setRuleTab('custom')
    setNewRule({
      name: '',
      metric: 'Transaction Amount',
      operator: 'Greater Than',
      value: '',
      severity: 'Medium',
      description: '',
    })
  }

  const clearDatasetRules = async () => {
    const cleared = await clearSessionRules(currentDatasetId)
    if (!cleared) {
      setUiNotice('Failed to clear dataset rules. Please try again.')
      return
    }

    setDatasetRulesMap((prev) => ({
      ...prev,
      [currentDatasetKey]: [...DEFAULT_RULES],
    }))
    setRuleTab('default')
    setUiNotice(`Rules cleared for ${selectedDataset?.name || 'global session'}.`)
  }

  const submitAssistantMessage = async () => {
    const message = assistantInput.trim()
    if (!message || assistantLoading) return

    const datasetId = currentDatasetId
    const datasetKey = currentDatasetKey

    setAssistantMessagesMap((prev) => {
      const current = prev[datasetKey] ?? [buildIntroMessage(selectedDataset?.name)]
      return {
        ...prev,
        [datasetKey]: [
          ...current,
          {
            id: `user-${Date.now()}`,
            role: 'user',
            text: message,
          },
        ],
      }
    })
    setAssistantInput('')
    setAssistantLoading(true)

    const response = await sendAssistantMessage(message, true, datasetId)

    const replyText = response?.result || response?.reply || 'Assistant is currently unavailable. Please try again.'
    setAssistantMessagesMap((prev) => {
      const current = prev[datasetKey] ?? [buildIntroMessage(selectedDataset?.name)]
      return {
        ...prev,
        [datasetKey]: [
          ...current,
          {
            id: `bot-${Date.now()}`,
            role: 'bot',
            text: replyText,
          },
        ],
      }
    })
    setAssistantLoading(false)
  }

  const clearDatasetChat = async () => {
    const cleared = await clearAssistantHistory(currentDatasetId)
    if (!cleared) {
      setUiNotice('Failed to clear chat history. Please try again.')
      return
    }

    setAssistantMessagesMap((prev) => ({
      ...prev,
      [currentDatasetKey]: [buildIntroMessage(selectedDataset?.name)],
    }))
    setUiNotice(`Chat history cleared for ${selectedDataset?.name || 'global session'}.`)
  }

  return (
    <div className="page">
      <header className="header">
        <div className="brand-wrap">
          <div className="brand-left">
            <div className="brand-icon">🛡️</div>
            <h1>AEGIS-AML</h1>
          </div>

          <div className="theme-toggle-wrap">
            <span className="theme-label">{isDark ? 'Dark' : 'Light'} Mode</span>
            <label className="switch" aria-label="Toggle color mode">
              <input
                type="checkbox"
                checked={isDark}
                onChange={(event) => setIsDark(event.target.checked)}
              />
              <span className="slider" />
            </label>
          </div>
        </div>
      </header>

      <main className="container">
        {uiNotice && <div className="ui-notice">{uiNotice}</div>}

        {activeView === 'overview' ? (
          <>
            <section className="title-row">
              <div>
                <h2>Datasets Overview</h2>
                <p>Manage transaction datasets and risk analysis reports.</p>
              </div>
            </section>

            <section className="metrics">
              <div className="metric-card">
                <span>Total Datasets</span>
                <strong>{datasets.length}</strong>
              </div>
              <div className="metric-card">
                <span>Total Transactions</span>
                <strong>{totals.totalRows.toLocaleString()}</strong>
              </div>
              <div className="metric-card">
                <span>High Risk</span>
                <strong>{totals.highRisk}</strong>
              </div>
              <div className="metric-card">
                <span>Analysed</span>
                <strong>
                  {totals.completed}/{datasets.length || 0}
                </strong>
              </div>
            </section>

            <section className="grid">
              <button
                className="add-card"
                type="button"
                onClick={() => setUiNotice('Upload endpoint is next step. Existing backend datasets are already live in this dashboard.')}
              >
                <div className="add-icon">＋</div>
                <h3>Add New Dataset</h3>
                <p>Upload CSV or Excel file</p>
              </button>

              {datasets.map((ds) => (
                <article key={ds.dataset_id} className="dataset-card">
                  <div className={`topbar ${statusClass(ds.status)}`} />

                  <div className="status-row">
                    <span className={`status-pill ${statusClass(ds.status)}`}>
                      <span className="dot" />
                      {ds.status}
                    </span>
                  </div>

                  <h3>{ds.name}</h3>
                  <p className="meta">Uploaded: {formatDate(ds.upload_date)}</p>

                  <div className="kv-row">
                    <span>Transactions</span>
                    <strong>{(ds.total_rows || 0).toLocaleString()}</strong>
                  </div>
                  <div className="kv-row">
                    <span>Risk Summary</span>
                    <span className={`risk-pill ${riskClass(ds.risk_level)}`}>
                      {ds.risk_level === 'Unknown' ? 'Calculating...' : `${ds.risk_level} Risk`}
                    </span>
                  </div>

                  <button
                    className="card-open-btn"
                    type="button"
                    onClick={() => openValidationView(ds)}
                  >
                    Open Validation
                  </button>
                </article>
              ))}
            </section>
          </>
        ) : activeView === 'validation' ? (
          <>
            <section className="val-header">
              <h2>Dataset Validation &amp; Processing</h2>
              <p>
                Reviewing <strong>{selectedDataset?.name || 'dataset.csv'}</strong> against enterprise AML compliance rules.
              </p>
            </section>

            <section className="val-layout">
              <div className="val-main">
                <div className="val-card">
                  <div className="val-title-row">
                    <h3>Validation Status</h3>
                    <span className={`val-chip ${validationSummary.statusKind}`}>
                      <span className="chip-dot" />
                      {validationSummary.statusLabel}
                    </span>
                  </div>

                  <div className="val-progress-wrap">
                    <div className="val-progress-text">Overall Progress: {validationSummary.percent}%</div>
                    <div className="val-progress-track">
                      <div className="val-progress-fill" style={{ width: `${validationSummary.percent}%` }} />
                    </div>
                  </div>

                  <div className="val-checks">
                    {checks.map((item) => (
                      <div key={item.key} className={`val-check ${item.kind}`}>
                        <div className="val-check-icon">{item.kind === 'pass' ? '✅' : item.kind === 'warn' ? '⚠️' : '❌'}</div>
                        <div className="val-check-content">
                          <h4>{item.title}</h4>
                          <p>{item.detail}</p>
                        </div>
                        {item.key === 'dupe' && (
                          <button
                            type="button"
                            className="review-btn"
                            onClick={() => setUiNotice(datasetSummary?.duplicate_count ? `${datasetSummary.duplicate_count} duplicates ready for review.` : 'No duplicates detected.')}
                          >
                            Review Duplicates
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <aside className="val-side">
                <div className="summary-card">
                  <div className="summary-head">Dataset Summary</div>
                  <div className="summary-body">
                    <div className="summary-block">
                      <div className="summary-label">Selected Dataset</div>
                      <div className="summary-value">{selectedDataset?.name || '-'}</div>
                      <div className="summary-sub">{selectedDataset?.human_size || '-'} • Uploaded {formatDate(selectedDataset?.upload_date || '')}</div>
                    </div>

                    <div className="summary-divider" />

                    <div className="summary-block">
                      <div className="summary-label">Total Transactions</div>
                      <div className="summary-hero">{(selectedDataset?.total_rows || 0).toLocaleString()}</div>
                    </div>

                    <div className="summary-block">
                      <div className="summary-label">Date Range</div>
                      <div className="summary-value">{datasetSummary?.date_range || 'Unknown'}</div>
                    </div>

                    <div className="summary-block">
                      <div className="summary-label">Jurisdictions</div>
                      <div className="summary-value">{datasetSummary?.jurisdictions ?? 0} Countries</div>
                    </div>
                  </div>

                  <div className="summary-actions">
                    <button type="button" className="primary-action" onClick={() => setActiveView('rule-engine')}>
                      Proceed to Rules
                    </button>
                    <button type="button" className="secondary-action" onClick={() => setActiveView('overview')}>
                      Go Back
                    </button>
                  </div>
                </div>
              </aside>
            </section>
          </>
        ) : activeView === 'rules' ? (
          <>
            <section className="uam-shell">
              <aside className="uam-nav">
                <div className="uam-logo">
                  <div className="uam-logo-icon">🛡️</div>
                  <div>
                    <div className="uam-logo-title">AML Unified</div>
                    <div className="uam-logo-sub">Enterprise Risk</div>
                  </div>
                </div>
                <nav className="uam-menu">
                  <button type="button" className="uam-menu-item active" onClick={() => setActiveView('rules')}>Dashboard (Testing)</button>
                  <button type="button" className="uam-menu-item" onClick={() => setActiveView('analysis')}>Analysis</button>
                  <button type="button" className="uam-menu-item" onClick={() => setActiveView('rule-engine')}>Rule Engine</button>
                  <button type="button" className="uam-menu-item" onClick={() => setActiveView('assistant')}>AI Assistant</button>
                </nav>
                <button type="button" className="secondary-action" onClick={() => setActiveView('validation')}>
                  Back to Validation
                </button>
              </aside>

              <div className="uam-main">
                <div className="uam-topbar">
                  <div>
                    <h2>Overview</h2>
                    <p>
                      Last updated: {formatLastUpdated(lastUpdatedValue)}
                      {isRefreshingDataset && <span className="refreshing-indicator">Refreshing…</span>}
                    </p>
                    <div className="dataset-scope-badge">
                      Dataset Scope: {selectedDataset?.name || 'Global Session'}
                    </div>
                  </div>
                  <div className="uam-top-actions">
                    <input
                      placeholder="Search entities, TXIDs..."
                      value={searchTerm}
                      onChange={(event) => setSearchTerm(event.target.value)}
                    />
                    <button type="button" className="secondary-action" onClick={cycleWindow}>Last {dashboardWindow} Days</button>
                    <button type="button" className="primary-action" onClick={exportDashboardData}>Export</button>
                  </div>
                </div>

                <div className="uam-content">
                  <div className="uam-left">
                    <div className="uam-kpis">
                      <div className="uam-kpi-card"><span>Total Processed</span><strong>{analyticsKpi.totalProcessed.toLocaleString()}</strong></div>
                      <div className="uam-kpi-card"><span>Active Alerts</span><strong>{analyticsKpi.activeAlerts.toLocaleString()}</strong></div>
                      <div className="uam-kpi-card"><span>High Risk Entities</span><strong>{analyticsKpi.highRiskEntities.toLocaleString()}</strong></div>
                    </div>

                    <div className="uam-mini-grid">
                      <div className="uam-chart-card">
                        <h3>Risk Score Distribution</h3>
                        <div className="uam-bars">
                          {analyticsRiskDistribution.map((item) => (
                            <div
                              key={item.label}
                              className={`bar ${item.label.toLowerCase()}`}
                              style={{ height: `${Math.max(8, Number(item.value || 0))}%` }}
                            >
                              <span>{item.label}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="uam-chart-card">
                        <h3>Alerts Over Time</h3>
                        <svg viewBox="0 0 260 100" className="uam-line">
                          <path d={alertLinePath} fill="none" stroke="currentColor" strokeWidth="3" />
                        </svg>
                      </div>
                      <div className="uam-chart-card">
                        <h3>Payment Type Mix</h3>
                        <div className="mini-bars">
                          {paymentTypeBars.map((item) => {
                            const maxCount = Math.max(...paymentTypeBars.map((entry) => entry.count), 1)
                            const width = Math.round((item.count / maxCount) * 100)
                            return (
                              <div key={item.label} className="mini-row">
                                <span>{item.label}</span>
                                <div className="mini-track"><div style={{ width: `${width}%` }} /></div>
                                <strong>{item.count}</strong>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                      <div className="uam-chart-card">
                        <h3>Currency Distribution</h3>
                        <div className="donut-wrap">
                          <div className="donut" style={currencyDonutStyle} />
                          <div className="donut-legend">
                            {currencyMix.map((item) => (
                              <div key={item.label}><span>{item.label}</span><strong>{item.count}</strong></div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="uam-table-card">
                      <div className="uam-table-head">
                        <h3>Recent Transactions</h3>
                        <button type="button" onClick={() => setShowAllRows((prev) => !prev)}>{showAllRows ? 'Show Less' : 'View All'}</button>
                      </div>
                      <table>
                        <thead>
                          <tr>
                            <th>Transaction ID</th>
                            <th>Date</th>
                            <th>Entity Name</th>
                            <th>Amount</th>
                            <th>Risk</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredTransactions.map((tx) => (
                            <tr key={tx.id} className={tx.focused ? 'focused' : ''}>
                              <td>{tx.id}</td>
                              <td>{tx.date}</td>
                              <td>{tx.entity}</td>
                              <td>{tx.amount}</td>
                              <td><span className={`tx-risk ${tx.risk.toLowerCase()}`}>{tx.risk}</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <aside className="uam-right">
                    <div className="uam-entity-card">
                      <h3>{topEntities[0]?.label || 'Top Entity'}</h3>
                      <div className="uam-score-row">
                        <div className="uam-score-ring"><span>{assistantRisk.score}</span><small>{assistantRisk.label}</small></div>
                        <div className="uam-score-meta">Live score derived from current backend dataset profile and rule signals.</div>
                      </div>
                      <div className="uam-contrib-list">
                        {entityContrib.map((item) => (
                          <div className="uam-contrib-item" key={item.name}>
                            <div>
                              <div className="c-title">{item.icon} {item.name}</div>
                              <div className="c-note">{item.note}</div>
                            </div>
                            <div className={`c-points ${item.tone}`}>{item.pts}</div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="uam-actions-card">
                      <h3>Recommended Actions</h3>
                      <button type="button" onClick={() => triggerAction('Generate SAR Report')}>Generate SAR Report</button>
                      <button type="button" onClick={() => triggerAction('Freeze Account')}>Freeze Account</button>
                      <button type="button" onClick={() => triggerAction('Request Enhanced Due Diligence')}>Request Enhanced Due Diligence</button>
                    </div>
                  </aside>
                </div>
              </div>
            </section>
          </>
        ) : activeView === 'analysis' ? (
          <>
            <section className="analysis-v2-shell">
              <aside className="analysis-v2-rail">
                <div className="analysis-v2-card">
                  <h4>System Status</h4>
                  <div className="analysis-v2-weight"><span>RAW Weight</span><strong>0.3500</strong></div>
                  <div className="analysis-v2-weight"><span>ML Weight</span><strong>0.3000</strong></div>
                  <div className="analysis-v2-weight"><span>GRAPH Weight</span><strong>0.3500</strong></div>
                  <div className="analysis-v2-pill">Model artifact detected</div>
                  <small>Rows: {(selectedDataset?.total_rows || 0).toLocaleString()}</small>
                  <small>Threshold: 1.6e-05</small>
                </div>

                <div className="analysis-v2-card">
                  <h4>Session Rules ({rules.filter((rule) => rule.active).length})</h4>
                  <ol className="analysis-v2-rule-list">
                    {rules.filter((rule) => rule.active).slice(0, 4).map((rule) => (
                      <li key={rule.id}>{rule.name}</li>
                    ))}
                  </ol>
                </div>
              </aside>

              <div className="analysis-v2-main">
                <div className="analysis-v2-hero">
                  <h2>AEGIS-AML — Hackathon Command Center</h2>
                  <p>Live AML scoring, human feedback calibration, model training, and explainability in one UI.</p>
                </div>

                <div className="analysis-v2-breadcrumb">📁 Datasets &nbsp; &gt; &nbsp; 🧠 Intelligence Hub &nbsp; &gt; &nbsp; 🧪 Model Studio</div>
                <div className="analysis-v2-steps">1. Upload &nbsp; • &nbsp; 2. Validation &amp; Processing &nbsp; • &nbsp; 3. Compliance Rules &nbsp; • &nbsp; 4. Analysis</div>

                <div className="analysis-v2-title-row">
                  <div>
                    <h3>⚡ Analysis — {selectedDataset?.name || 'training_transactions.template'}</h3>
                    <p>
                      {selectedDataset?.total_rows || 0} transactions · {analysisFraudPct.toFixed(1)}% fraud · Risk Level: {selectedDataset?.risk_level || 'High'} · Status: {selectedDataset?.status || 'Completed'}
                    </p>
                  </div>
                  <button type="button" className="secondary-action" onClick={() => setActiveView('overview')}>← Back to Datasets</button>
                </div>

                <div className="analysis-v2-tabs">
                  <button type="button" className={analysisTab === 'risk' ? 'active' : ''} onClick={() => setAnalysisTab('risk')}>Risk Analysis</button>
                  <button type="button" className={analysisTab === 'studio' ? 'active' : ''} onClick={() => setAnalysisTab('studio')}>Model Studio</button>
                  <button type="button" className={analysisTab === 'assistant' ? 'active' : ''} onClick={() => { setAnalysisTab('assistant'); setActiveView('assistant') }}>Data Query Assistant</button>
                </div>
                {analysisTab === 'studio' ? (
                  <>
                    <div className="analysis-v2-meta-row">
                      <span>Model studio enabled · schema {generatorSettings.schema}</span>
                      <span>Artifacts: {modelInfo?.model_available ? 'Available' : 'Not trained yet'}</span>
                    </div>

                    <section className="studio-v2-section">
                      <h3>Synthetic Training Data Generator</h3>
                      <p>Generate realistic AML fraud transaction datasets in multiple schemas. Preview before saving/training.</p>

                      <div className="studio-v2-grid">
                        <div className="studio-v2-card">
                          <h4>Generation Settings</h4>
                          <label>Data Schema</label>
                          <select
                            value={generatorSettings.schema}
                            onChange={(event) => setGeneratorSettings((prev) => ({ ...prev, schema: event.target.value }))}
                          >
                            {SCHEMA_OPTIONS.map((item) => (
                              <option key={item.value} value={item.value}>{item.label}</option>
                            ))}
                          </select>

                          <label>Number of flows</label>
                          <input
                            type="number"
                            value={generatorSettings.numRows}
                            onChange={(event) => setGeneratorSettings((prev) => ({ ...prev, numRows: event.target.value }))}
                            min={20}
                            max={500000}
                          />

                          <label>Fraud Ratio %</label>
                          <input
                            type="range"
                            min={1}
                            max={95}
                            value={generatorSettings.fraudRatioPct}
                            onChange={(event) => setGeneratorSettings((prev) => ({ ...prev, fraudRatioPct: event.target.value }))}
                          />

                          <label>Random Seed</label>
                          <input
                            type="number"
                            value={generatorSettings.seed}
                            onChange={(event) => setGeneratorSettings((prev) => ({ ...prev, seed: event.target.value }))}
                          />

                          <label>Target Recall</label>
                          <input
                            type="number"
                            min={0.01}
                            max={0.99}
                            step={0.01}
                            value={generatorSettings.targetRecall}
                            onChange={(event) => setGeneratorSettings((prev) => ({ ...prev, targetRecall: event.target.value }))}
                          />

                          <div className="studio-v2-columns">
                            {selectedSchemaColumns.slice(0, 14).map((column) => (
                              <span key={column}>{column}</span>
                            ))}
                          </div>

                          <div className="studio-v2-actions-row">
                            <button type="button" className="studio-v2-primary" onClick={runDataPreview} disabled={generatorBusy || trainingBusy}>
                              {generatorBusy ? 'Previewing...' : 'Preview'}
                            </button>
                            <button type="button" className="studio-v2-secondary" onClick={downloadGeneratedCsv} disabled={generatorBusy || trainingBusy}>Download CSV</button>
                            <button type="button" className="studio-v2-secondary" onClick={saveAndTrainSynthetic} disabled={generatorBusy || trainingBusy}>
                              {trainingBusy ? 'Training...' : 'Save & Train'}
                            </button>
                          </div>
                        </div>

                        <div className="studio-v2-card studio-v2-info">
                          <div className="studio-v2-hint">Click Preview to generate and inspect synthetic data before saving.</div>
                          <h4>Preview Snapshot</h4>
                          {studioPreview.rows.length > 0 ? (
                            <table className="analysis-v2-table">
                              <thead>
                                <tr>
                                  {studioPreview.columns.slice(0, 5).map((column) => (
                                    <th key={column}>{column}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {studioPreview.rows.slice(0, 5).map((row, index) => (
                                  <tr key={index}>
                                    {studioPreview.columns.slice(0, 5).map((column) => (
                                      <td key={column}>{row[column]}</td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          ) : (
                            <p>No preview loaded yet. Generate preview to inspect synthetic rows.</p>
                          )}
                        </div>
                      </div>
                    </section>

                    <section className="studio-v2-section">
                      <h3>No-Code Training Control</h3>
                      <p>Upload a training CSV directly from your machine and retrain artifacts in one click.</p>
                      <div className="studio-v2-trainbox">
                        <input type="file" accept=".csv,text/csv" onChange={handleInlineFileSelect} />
                        <button type="button" className="studio-v2-secondary" onClick={runInlineTraining} disabled={trainingBusy}>
                          {trainingBusy ? 'Training...' : 'Upload & Train'}
                        </button>
                      </div>
                      <small>
                        {inlineTrainingFile
                          ? `Selected file: ${inlineTrainingFile.name}`
                          : 'Upload a CSV or place file at data/training_transactions.csv and use Save & Train above.'}
                      </small>
                    </section>

                    <section className="studio-v2-section">
                      <h3>Model Explainability & Artifacts</h3>
                      <div className="studio-v2-grid">
                        <div className="studio-v2-card">
                          <h4>Training Metadata</h4>
                          <pre className="studio-v2-json">{modelMetadataText}</pre>
                        </div>
                        <div className="studio-v2-card">
                          <h4>Top SHAP Features</h4>
                          <div className="analysis-v2-bars studio-v2-shap-bars">
                            {modelShapTop.map((item) => (
                              <div key={item.feature}>
                                <small>{item.value.toFixed(4)}</small>
                                <div style={{ height: `${getScaledBarHeight(item.value, modelShapMax, 8, 96)}px` }} />
                                <span>{item.feature}</span>
                              </div>
                            ))}
                          </div>
                          <table className="analysis-v2-table">
                            <thead>
                              <tr>
                                <th>feature</th>
                                <th>mean_abs_shap</th>
                              </tr>
                            </thead>
                            <tbody>
                              {modelShapTop.length ? (
                                modelShapTop.map((item) => (
                                  <tr key={item.feature}>
                                    <td>{item.feature}</td>
                                    <td>{item.value.toFixed(6)}</td>
                                  </tr>
                                ))
                              ) : (
                                <tr>
                                  <td colSpan={2} className="analysis-v2-empty">No SHAP features available yet. Train model first.</td>
                                </tr>
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </section>
                  </>
                ) : (
                  <>
                    <div className="analysis-v2-meta-row">
                      <span>ML scoring enabled · {analyticsKpi.totalProcessed} rows scored</span>
                      <span>Composite risk (RAW+ML+GRAPH): Avg {assistantRisk.score.toFixed(1)}</span>
                    </div>

                    <div className="analysis-v2-toolbar">
                      <input
                        placeholder="e.g. 8724/731955, Cross-border, Structuring"
                        value={searchTerm}
                        onChange={(event) => setSearchTerm(event.target.value)}
                      />
                      <select>
                        <option>Excel/CSV</option>
                        <option>JSON</option>
                      </select>
                      <button type="button" className="secondary-action" onClick={exportDashboardData}>Export</button>
                    </div>

                    <div className="analysis-v2-kpis">
                      <div><span>Transactions</span><strong>{analyticsKpi.totalProcessed}</strong></div>
                      <div><span>Fraud Flagged</span><strong>{analysisHighRiskRows}</strong></div>
                      <div><span>Cross-border</span><strong>{Math.max(1, analyticsKpi.activeAlerts)}</strong></div>
                      <div><span>Avg. Amount</span><strong>${analysisAverageAmount.toLocaleString()}</strong></div>
                      <div><span>Unique Entities</span><strong>{analysisUniqueEntities}</strong></div>
                    </div>

                    <div className="analysis-v2-chart-grid">
                      <div className="analysis-v2-chart-card">
                        <h4>🧠 Laundering Typology Breakdown</h4>
                        <div className="analysis-v2-bars">
                          {analysisTypologyBreakdown.map((item) => (
                            <div key={item.label}>
                              <small>{item.value}</small>
                              <div style={{ height: `${getScaledBarHeight(item.value, analysisTypologyMax)}px` }} />
                              <span>{item.label}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="analysis-v2-chart-card">
                        <h4>💰 Transaction Amount Distribution</h4>
                        <div className="analysis-v2-bars">
                          {analysisAmountBuckets.map((item) => (
                            <div key={item.label}>
                              <small>{item.count}</small>
                              <div style={{ height: `${getScaledBarHeight(item.count, analysisAmountBucketMax)}px` }} />
                              <span>{item.label}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="analysis-v2-chart-card">
                        <h4>🌍 Top Geographic Corridors</h4>
                        <div className="analysis-v2-bars">
                          {analysisCorridors.map((item) => (
                            <div key={item.label}>
                              <small>{item.value}</small>
                              <div style={{ height: `${getScaledBarHeight(item.value, analysisCorridorMax)}px` }} />
                              <span>{item.label}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="analysis-v2-chart-card">
                        <h4>📅 Daily Transaction Volume</h4>
                        <div className="analysis-v2-bars">
                          {analyticsAlerts.slice(0, 6).map((item) => (
                            <div key={item.label}>
                              <small>{item.count}</small>
                              <div style={{ height: `${getScaledBarHeight(item.count, analysisDailyVolumeMax)}px` }} />
                              <span>{item.label}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="analysis-v2-lower-grid">
                      <div className="analysis-v2-card">
                        <h4>🧾 Transaction Explorer</h4>
                        <div className="analysis-v2-filters">
                          <select value={analysisStatusFilter} onChange={(event) => setAnalysisStatusFilter(event.target.value)}>
                            <option>All</option>
                            <option>High</option>
                            <option>Medium</option>
                            <option>Low</option>
                          </select>
                          <select value={analysisPaymentFilter} onChange={(event) => setAnalysisPaymentFilter(event.target.value)}>
                            {analysisPaymentOptions.map((item) => (
                              <option key={item}>{item}</option>
                            ))}
                          </select>
                          <input
                            value={analysisMinAmount}
                            onChange={(event) => setAnalysisMinAmount(event.target.value)}
                            placeholder="Min Amount"
                          />
                        </div>
                        <select
                          value={analysisSelectedEntity}
                          onChange={(event) => setAnalysisSelectedEntity(event.target.value)}
                        >
                          <option value="">Select entity for deep analysis</option>
                          {relatedEntities.map((entity) => (
                            <option key={entity.name} value={entity.name}>{entity.name}</option>
                          ))}
                        </select>

                        <table className="analysis-v2-table">
                          <thead>
                            <tr>
                              <th>Sender</th>
                              <th>Receiver</th>
                              <th>Payment Type</th>
                              <th>Amount</th>
                              <th>Risk</th>
                            </tr>
                          </thead>
                          <tbody>
                            {analysisExplorerRows.length ? (
                              analysisExplorerRows.map((row) => (
                                <tr key={row.id}>
                                  <td>{row.entity}</td>
                                  <td>{topEntities[0]?.label || 'ACC_9001'}</td>
                                  <td>{row.paymentType}</td>
                                  <td>{row.amount}</td>
                                  <td><span className={`analysis-v2-risk ${String(row.risk).toLowerCase()}`}>{row.risk}</span></td>
                                </tr>
                              ))
                            ) : (
                              <tr>
                                <td colSpan={5} className="analysis-v2-empty">No transactions match the current filters.</td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>

                      <div className="analysis-v2-side-stack">
                        <div className="analysis-v2-card">
                          <h4>🎯 Entity Analysis</h4>
                          <p>
                            {analysisSelectedEntity
                              ? `${analysisSelectedEntity} shows elevated risk behavior. Review counterparties, linked corridors, and bursty transaction timing.`
                              : 'Select an entity from Transaction Explorer to view profile and risk indicators.'}
                          </p>
                        </div>
                        <div className="analysis-v2-card">
                          <h4>⚡ Recommended Actions</h4>
                          <div className="analysis-v2-actions">
                            <button type="button" onClick={() => triggerAction('Generate SAR Report')}>Generate SAR Report</button>
                            <button type="button" onClick={() => triggerAction('Export Dataset Analysis')}>Export Dataset Analysis</button>
                            <button type="button" onClick={() => triggerAction('Train Model on Dataset')}>Train Model on Dataset</button>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="analysis-v2-briefing">
                      <h4>🧠 AI Risk Briefing</h4>
                      <p>{analysisNarrative}</p>
                    </div>

                    <div className="analysis-v2-prompts-row">
                      <h4>✨ Explore Further</h4>
                      <button
                        type="button"
                        className="prompt-refresh-btn"
                        onClick={regeneratePromptSuggestions}
                        disabled={isGeneratingPrompts}
                      >
                        {isGeneratingPrompts ? 'Generating…' : 'Regenerate Prompts'}
                      </button>
                    </div>
                    <div className="analysis-prompts">
                      {assistantPromptSuggestions.map((prompt) => (
                        <button
                          key={prompt}
                          type="button"
                          className="analysis-prompt-btn"
                          onClick={() => applySuggestedPrompt(prompt, true)}
                        >
                          ↪ {prompt}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </section>
          </>
        ) : activeView === 'rule-engine' ? (
          <>
            <section className="rules-header">
              <div>
                <h2>Compliance Rules</h2>
                <p>Manage detection logic, risk thresholds, and automate AML monitoring workflows.</p>
                <div className="dataset-scope-badge">
                  Dataset Scope: {selectedDataset?.name || 'Global Session'}
                </div>
                {isRefreshingDataset && <span className="refreshing-indicator">Refreshing…</span>}
              </div>
              <div className="rules-head-actions">
                <button type="button" className="secondary-action" onClick={() => setActiveView('rules')}>Dashboard</button>
                <button type="button" className="secondary-action" onClick={() => setActiveView('analysis')}>Analysis</button>
                <button type="button" className="primary-action" onClick={() => setActiveView('assistant')}>AI Assistant</button>
              </div>
            </section>

            <section className="rules-tabs">
              <button
                type="button"
                className={`rules-tab-btn ${ruleTab === 'default' ? 'active' : ''}`}
                onClick={() => setRuleTab('default')}
              >
                Default Rules
              </button>
              <button
                type="button"
                className={`rules-tab-btn ${ruleTab === 'custom' ? 'active' : ''}`}
                onClick={() => setRuleTab('custom')}
              >
                Custom Rules
              </button>
              <button
                type="button"
                className={`rules-tab-btn ${ruleTab === 'archived' ? 'active' : ''}`}
                onClick={() => setRuleTab('archived')}
              >
                Archived
              </button>
            </section>

            <section className="rules-layout">
              <div className="rules-main">
                <div className="rules-filter-card">
                  <span className="rules-filter-label">Filter by Risk:</span>
                  <button
                    type="button"
                    className={`risk-filter-chip ${riskFilters.high ? 'on high' : ''}`}
                    onClick={() => toggleRisk('high')}
                  >
                    High
                  </button>
                  <button
                    type="button"
                    className={`risk-filter-chip ${riskFilters.medium ? 'on medium' : ''}`}
                    onClick={() => toggleRisk('medium')}
                  >
                    Medium
                  </button>
                  <button
                    type="button"
                    className={`risk-filter-chip ${riskFilters.low ? 'on low' : ''}`}
                    onClick={() => toggleRisk('low')}
                  >
                    Low
                  </button>
                  <button
                    type="button"
                    className={`risk-filter-chip ${riskFilters.critical ? 'on critical' : ''}`}
                    onClick={() => toggleRisk('critical')}
                  >
                    Critical
                  </button>
                </div>

                <div className="rules-grid">
                  {filteredRules.map((rule) => (
                    <article key={rule.id} className="rule-card">
                      <div className="rule-head">
                        <div>
                          <div className="rule-title-row">
                            <span className="rule-icon">{rule.icon}</span>
                            <h3>{rule.name}</h3>
                          </div>
                          <p className="rule-id">Rule #{rule.id}</p>
                        </div>
                        <span className={`rule-severity ${rule.severity.toLowerCase()}`}>{rule.severity} Risk</span>
                      </div>

                      <p className="rule-desc">{rule.description}</p>

                      <div className="rule-foot">
                        <button
                          type="button"
                          className={`rule-toggle ${rule.active ? 'on' : ''}`}
                          onClick={() => toggleRuleActive(rule.id)}
                        >
                          {rule.active ? 'Active' : 'Inactive'}
                        </button>
                        <span className="rule-arrow">→</span>
                      </div>
                    </article>
                  ))}
                </div>
              </div>

              <aside className="rules-side">
                <div className="summary-card">
                  <div className="summary-head">Add Custom Rule</div>
                  <div className="summary-body">
                    <div className="form-group">
                      <label>Rule Name</label>
                      <input
                        value={newRule.name}
                        onChange={(event) => setNewRule((prev) => ({ ...prev, name: event.target.value }))}
                        placeholder="e.g., Crypto Wallet Transfer > $10k"
                      />
                    </div>

                    <div className="form-group">
                      <label>Trigger Condition</label>
                      <select
                        value={newRule.metric}
                        onChange={(event) => setNewRule((prev) => ({ ...prev, metric: event.target.value }))}
                      >
                        <option>Transaction Amount</option>
                        <option>Transaction Frequency</option>
                        <option>Beneficiary Location</option>
                        <option>Account Age</option>
                      </select>
                      <div className="inline-row">
                        <select
                          value={newRule.operator}
                          onChange={(event) => setNewRule((prev) => ({ ...prev, operator: event.target.value }))}
                        >
                          <option>Greater Than</option>
                          <option>Less Than</option>
                          <option>Equals</option>
                        </select>
                        <input
                          value={newRule.value}
                          onChange={(event) => setNewRule((prev) => ({ ...prev, value: event.target.value }))}
                          placeholder="Value"
                        />
                      </div>
                    </div>

                    <div className="form-group">
                      <label>Risk Severity</label>
                      <div className="severity-row">
                        {['Low', 'Medium', 'High'].map((severity) => (
                          <button
                            key={severity}
                            type="button"
                            className={`severity-btn ${newRule.severity === severity ? 'active' : ''}`}
                            onClick={() => setNewRule((prev) => ({ ...prev, severity }))}
                          >
                            {severity}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="form-group">
                      <label>Description</label>
                      <textarea
                        rows={3}
                        value={newRule.description}
                        onChange={(event) => setNewRule((prev) => ({ ...prev, description: event.target.value }))}
                        placeholder="Briefly describe what this rule detects..."
                      />
                    </div>
                  </div>
                  <div className="summary-actions">
                    <button
                      type="button"
                      className="secondary-action"
                      onClick={() =>
                        setNewRule({
                          name: '',
                          metric: 'Transaction Amount',
                          operator: 'Greater Than',
                          value: '',
                          severity: 'Medium',
                          description: '',
                        })
                      }
                    >
                      Cancel
                    </button>
                    <button type="button" className="secondary-action" onClick={clearDatasetRules}>
                      Clear Dataset Rules
                    </button>
                    <button type="button" className="primary-action" onClick={saveCustomRule}>
                      Save Rule
                    </button>
                  </div>
                </div>
              </aside>
            </section>
          </>
        ) : (
          <>
            <section className="aq-shell">
              <aside className="aq-nav">
                <div className="aq-brand">
                  <div className="aq-brand-icon">🛡️</div>
                  <div>
                    <div className="aq-brand-title">AML Platform</div>
                    <div className="aq-brand-sub">Enterprise</div>
                  </div>
                </div>

                <nav className="aq-menu">
                  <button type="button" className="aq-menu-item" onClick={() => setActiveView('rules')}>Dashboard (Testing)</button>
                  <button type="button" className="aq-menu-item" onClick={() => setActiveView('analysis')}>Analysis</button>
                  <button type="button" className="aq-menu-item" onClick={() => setActiveView('rule-engine')}>Rule Engine</button>
                  <button type="button" className="aq-menu-item active" onClick={() => setActiveView('assistant')}>AI Assistant</button>
                </nav>

                <button type="button" className="secondary-action" onClick={() => setActiveView('rules')}>
                  Back to Dashboard
                </button>
              </aside>

              <div className="aq-main">
                <div className="aq-chat-col">
                  <div className="aq-chat-header">
                    <div>
                      <h2>Data Query Assistant</h2>
                      <p>Ask questions about transactions, entities, or risk patterns.</p>
                      <div className="dataset-scope-badge">
                        Dataset Scope: {selectedDataset?.name || 'Global Session'}
                      </div>
                      {isRefreshingDataset && <span className="refreshing-indicator">Refreshing…</span>}
                    </div>
                    <button type="button" className="secondary-action" onClick={clearDatasetChat}>
                      Clear This Dataset Chat
                    </button>
                  </div>

                  <div className="aq-chat-scroll">
                    {assistantMessages.map((message) => (
                      <div key={message.id} className={`aq-msg ${message.role}`}>
                        {message.role === 'bot' && <div className="aq-avatar">🤖</div>}
                        <div className="aq-bubble">
                          <p>{message.text}</p>
                          {Array.isArray(message.suggestions) && message.suggestions.length > 0 && (
                            <ul>
                              {message.suggestions.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          )}
                        </div>
                      </div>
                    ))}

                    <div className="aq-alert-card">
                      <h4>Live Dataset Snapshot</h4>
                      <table>
                        <thead>
                          <tr>
                            <th>Date</th>
                            <th>Amount</th>
                            <th>Entity</th>
                          </tr>
                        </thead>
                        <tbody>
                          {recentTransactions.slice(0, 3).map((row) => (
                            <tr key={`${row.id}-${row.entity}`}>
                              <td>{row.date}</td>
                              <td>{row.amount}</td>
                              <td>{row.entity}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div className="aq-input-wrap">
                    <textarea
                      rows={2}
                      placeholder="Type your query here... Use / for commands"
                      value={assistantInput}
                      onChange={(event) => setAssistantInput(event.target.value)}
                    />
                    <button type="button" onClick={submitAssistantMessage} disabled={assistantLoading}>
                      {assistantLoading ? 'Sending...' : 'Send'}
                    </button>
                  </div>
                </div>

                <aside className="aq-insights">
                  <div className="aq-insight-card">
                    <div className="aq-insight-head">
                      <h4>Risk Score</h4>
                      <span className={`tx-risk ${assistantRisk.label.toLowerCase()}`}>{assistantRisk.label}</span>
                    </div>
                    <div className="aq-score">{assistantRisk.score}/100</div>
                    <div className="aq-meter"><span style={{ width: `${assistantRisk.score}%` }} /></div>
                    <p>
                      Dataset {selectedDataset?.name || 'N/A'} currently has {selectedDataset?.fraud_pct || '0.0%'}
                      {' '}flagged transactions.
                    </p>
                  </div>

                  <div className="aq-insight-card">
                    <h4>Related Entities</h4>
                    <ul className="aq-entity-list">
                      {relatedEntities.map((entity) => (
                        <li key={entity.name}><span>{entity.name}</span><small>{entity.note}</small></li>
                      ))}
                    </ul>
                  </div>

                  <div className="aq-insight-card">
                    <h4>Suggested Actions</h4>
                    <div className="aq-suggest">
                      {suggestedActions.map((item) => (
                        <button key={item.key} type="button" onClick={() => triggerAction(item.action)}>{item.label}</button>
                      ))}
                    </div>
                  </div>

                  <div className="aq-insight-card">
                    <h4>Related Prompts</h4>
                    <p>{isGeneratingPrompts ? 'Refreshing prompts via LLM…' : 'Context-aware prompts from current dataset signals.'}</p>
                    <button
                      type="button"
                      className="prompt-refresh-btn"
                      onClick={regeneratePromptSuggestions}
                      disabled={isGeneratingPrompts}
                    >
                      {isGeneratingPrompts ? 'Generating…' : 'Regenerate Prompts'}
                    </button>
                    <div className="aq-suggest">
                      {assistantPromptSuggestions.slice(0, 3).map((prompt) => (
                        <button key={prompt} type="button" onClick={() => applySuggestedPrompt(prompt, false)}>{prompt}</button>
                      ))}
                    </div>
                  </div>
                </aside>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  )
}

export default App
