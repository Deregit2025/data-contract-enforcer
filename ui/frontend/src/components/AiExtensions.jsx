import { useEffect, useState } from 'react'
import { getAiMetrics } from '../services/api'
import { Brain, CheckCircle2, XCircle } from 'lucide-react'

function MetricCard({ title, status, children }) {
  const isOk = status === 'PASS' || status === 'OK' || status === 'STABLE'
  return (
    <div className={`bg-slate-800 rounded-xl p-5 border ${isOk ? 'border-green-500/30' : 'border-red-500/30'}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-semibold text-sm">{title}</h3>
        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold ${
          isOk ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
        }`}>
          {isOk ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
          {status}
        </div>
      </div>
      {children}
    </div>
  )
}

function Stat({ label, value, highlight }) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-slate-700/50 last:border-0">
      <span className="text-slate-400 text-sm">{label}</span>
      <span className={`font-bold text-sm ${highlight ? 'text-red-400' : 'text-white'}`}>{value}</span>
    </div>
  )
}

export default function AiExtensions() {
  const [m, setM] = useState(null)

  useEffect(() => {
    getAiMetrics().then(setM).catch(() => {})
  }, [])

  if (!m) return <p className="text-slate-400 p-8">Loading AI metrics…</p>

  const driftFail = m.embedding_drift_status !== 'PASS' && m.embedding_drift_status !== 'OK'
  const promptOk  = m.prompt_status === 'PASS' || m.prompt_status === 'OK'
  const llmOk     = m.llm_status === 'PASS' || m.llm_status === 'OK'

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Brain size={24} className="text-purple-400" />
        <h2 className="text-2xl font-bold text-white">AI Contract Extensions</h2>
        <span className="text-slate-400 text-sm ml-2">Run date: {m.run_date}</span>
      </div>

      <div className="grid md:grid-cols-3 gap-5">
        {/* Extension 1 — Embedding Drift */}
        <MetricCard title="Extension 1 — Embedding Drift Monitor" status={m.embedding_drift_status || 'UNKNOWN'}>
          <Stat label="Drift Score" value={m.embedding_drift_score?.toFixed(4) ?? '—'} highlight={driftFail} />
          <Stat label="Sample Size" value={m.embedding_sample_size ?? '—'} />
          <div className="mt-3 p-3 rounded-lg bg-slate-900/60">
            <p className="text-xs text-slate-400">
              Cosine similarity measured on {m.embedding_sample_size} sampled vectors.
              {driftFail
                ? ' Drift EXCEEDS 0.15 threshold — concept drift detected.'
                : ' Within threshold — embeddings stable.'}
            </p>
          </div>
        </MetricCard>

        {/* Extension 2 — Prompt Validation */}
        <MetricCard title="Extension 2 — Prompt Input Validation" status={m.prompt_status || 'UNKNOWN'}>
          <Stat label="Total Prompts" value={m.prompt_total ?? '—'} />
          <Stat label="Valid" value={m.prompt_valid ?? '—'} />
          <Stat label="Rejected" value={m.prompt_rejected ?? '—'} highlight={(m.prompt_rejected ?? 0) > 0} />
          <div className="mt-3 p-3 rounded-lg bg-slate-900/60">
            <p className="text-xs text-slate-400">
              JSON Schema validation on all prompt inputs.
              {promptOk ? ' 100% pass — no schema violations.' : ' Some prompts rejected.'}
            </p>
          </div>
        </MetricCard>

        {/* Extension 3 — LLM Output Schema */}
        <MetricCard title="Extension 3 — LLM Output Schema" status={m.llm_status || 'UNKNOWN'}>
          <Stat label="Total Outputs" value={m.llm_total_outputs ?? '—'} />
          <Stat label="Violations" value={m.llm_violations ?? '—'} highlight={(m.llm_violations ?? 0) > 0} />
          <Stat label="Violation Rate" value={m.llm_violation_rate !== null ? `${(m.llm_violation_rate * 100).toFixed(1)}%` : '—'} highlight={(m.llm_violation_rate ?? 0) > 0} />
          <Stat label="Trend" value={m.llm_trend ?? '—'} />
          <div className="mt-3 p-3 rounded-lg bg-slate-900/60">
            <p className="text-xs text-slate-400">
              Enforcing structural contract on all LLM JSON responses.
              {llmOk ? ' Zero schema violations.' : ' Contract violations detected.'}
            </p>
          </div>
        </MetricCard>
      </div>

      {/* Summary banner */}
      <div className={`rounded-xl p-4 border ${driftFail ? 'bg-red-500/10 border-red-500/30' : 'bg-green-500/10 border-green-500/30'}`}>
        <p className={`text-sm font-medium ${driftFail ? 'text-red-300' : 'text-green-300'}`}>
          {driftFail
            ? 'Action required: Embedding drift detected — retrain or recalibrate the embedding model.'
            : 'All AI contract checks nominal — prompt inputs clean, LLM outputs conform, drift within bounds.'}
        </p>
      </div>
    </div>
  )
}
