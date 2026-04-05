import { useEffect, useState } from 'react'
import { getAllFailures, getSubscriptions } from '../services/api'
import { GitCommit, Zap, ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react'

// ── Four top-level classifications from the challenge document ──────────
// Data contracts have three dimensions: structural, statistical, temporal
// + AI-specific extensions (embedding drift, prompt validation, LLM output)

const CLASSIFY = (checkType) => {
  const t = (checkType || '').toLowerCase()
  if (['not_null', 'unique', 'row_count', 'referential_integrity', 'cross_system_referential'].includes(t))
    return { label: 'Structural',   color: 'bg-red-500/20 text-red-300 border-red-500/30',        dot: 'bg-red-400' }
  if (['range', 'max_range', 'drift', 'statistical_drift'].includes(t))
    return { label: 'Statistical',  color: 'bg-orange-500/20 text-orange-300 border-orange-500/30', dot: 'bg-orange-400' }
  if (['timestamp_order', 'sequence_integrity', 'freshness'].includes(t))
    return { label: 'Temporal',     color: 'bg-green-500/20 text-green-300 border-green-500/30',   dot: 'bg-green-400' }
  if (['embedding_drift', 'prompt_validation', 'llm_output'].includes(t))
    return { label: 'AI',           color: 'bg-pink-500/20 text-pink-300 border-pink-500/30',      dot: 'bg-pink-400' }
  return   { label: 'Structural',   color: 'bg-red-500/20 text-red-300 border-red-500/30',        dot: 'bg-red-400' }
}

const SEV_STYLE = {
  CRITICAL: 'bg-red-500/20 text-red-400 border-red-500/30',
  HIGH:     'bg-orange-500/20 text-orange-400 border-orange-500/30',
  MEDIUM:   'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  LOW:      'bg-blue-500/20 text-blue-400 border-blue-500/30',
}

const SEV_DOT = { CRITICAL: 'bg-red-500', HIGH: 'bg-orange-500', MEDIUM: 'bg-yellow-500', LOW: 'bg-blue-500' }

const MODE_COLOR = {
  ENFORCE: 'text-red-400 bg-red-500/10 border-red-500/30',
  WARN:    'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  AUDIT:   'text-blue-400 bg-blue-500/10 border-blue-500/30',
}

function BlameChain({ chain }) {
  if (!chain?.length)
    return <p className="text-slate-500 text-xs italic">No git blame data — attributor did not run on this check</p>
  return (
    <div className="space-y-2">
      {chain.map((entry, i) => (
        <div key={i} className="bg-slate-900/60 rounded-lg p-3 border border-slate-700/40">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-slate-500 text-xs font-bold">#{entry.rank}</span>
            <GitCommit size={11} className="text-indigo-400" />
            <span className="font-mono text-xs text-indigo-300">{entry.commit_hash?.slice(0, 7)}</span>
            <span className="ml-auto text-xs font-bold" style={{
              color: entry.confidence_score >= 0.7 ? '#22c55e' : entry.confidence_score >= 0.4 ? '#eab308' : '#94a3b8'
            }}>
              score {entry.confidence_score}
            </span>
          </div>
          <p className="text-slate-200 text-xs font-medium leading-snug">{entry.commit_message}</p>
          <div className="mt-1.5 flex flex-wrap gap-2 text-xs text-slate-500">
            <span className="text-slate-400">{entry.author_name}</span>
            <span>·</span>
            <span className="font-mono">{entry.file_path}</span>
            <span>·</span>
            <span>{entry.commit_timestamp?.slice(0, 10)}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

function BlastRadius({ contractId, allSubscriptions, blastRadius }) {
  const subs = allSubscriptions.filter(s => s.contract_id === contractId)

  // lineage enrichment from the attributor's blast_radius field
  const affectedNodes    = blastRadius?.affected_nodes || []
  const affectedPipelines = blastRadius?.affected_pipelines || []
  const estimatedRecords = blastRadius?.estimated_records
  const depth            = blastRadius?.contamination_depth

  const hasRegistry = subs.length > 0
  const hasLineage  = affectedNodes.length > 0 || affectedPipelines.length > 0

  if (!hasRegistry && !hasLineage)
    return <p className="text-slate-500 text-xs italic">No blast radius data — registry has no subscribers and lineage found no downstream nodes</p>

  return (
    <div className="space-y-4">

      {/* PRIMARY — Registry subscribers */}
      <div>
        <p className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-2">
          Primary — Registry Subscribers
        </p>
        {hasRegistry ? (
          <div className="space-y-2">
            {subs.map((sub, i) => (
              <div key={i} className="bg-slate-900/60 rounded-lg p-3 border border-slate-700/40">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle size={11} className="text-orange-400 shrink-0" />
                  <span className="text-white text-xs font-semibold">{sub.subscriber_id}</span>
                  <span className={`ml-auto px-2 py-0.5 rounded text-xs font-bold border ${MODE_COLOR[sub.validation_mode] || MODE_COLOR.AUDIT}`}>
                    {sub.validation_mode}
                  </span>
                </div>
                {(sub.breaking_fields || []).map((bf, j) => (
                  <div key={j} className="mt-1.5 text-xs">
                    <span className="text-orange-300 font-mono">{bf.field}</span>
                    <p className="text-slate-400 mt-0.5 leading-snug">{bf.reason}</p>
                  </div>
                ))}
                {sub.contact && <p className="text-slate-600 text-xs mt-2">{sub.contact}</p>}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-slate-500 text-xs italic">No subscriptions registered for this contract</p>
        )}
      </div>

      {/* ENRICHMENT — Lineage graph traversal */}
      <div>
        <p className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-2">
          Enrichment — Lineage Graph Traversal
        </p>
        {hasLineage ? (
          <div className="bg-slate-900/60 rounded-lg p-3 border border-slate-700/40 space-y-2">
            {estimatedRecords !== undefined && (
              <div className="flex gap-4 text-xs">
                <span className="text-slate-400">Estimated records affected:
                  <span className="text-red-400 font-bold ml-1">{estimatedRecords}</span>
                </span>
                {depth !== undefined && (
                  <span className="text-slate-400">Contamination depth:
                    <span className="text-orange-400 font-bold ml-1">{depth} hops</span>
                  </span>
                )}
              </div>
            )}
            {affectedNodes.length > 0 && (
              <div>
                <p className="text-slate-500 text-xs mb-1">Downstream nodes (BFS traversal):</p>
                <div className="flex flex-wrap gap-1.5">
                  {affectedNodes.map((n, i) => (
                    <span key={i} className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/20 text-xs font-mono">
                      {n}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {affectedPipelines.length > 0 && (
              <div>
                <p className="text-slate-500 text-xs mb-1">Affected pipelines:</p>
                <div className="flex flex-wrap gap-1.5">
                  {affectedPipelines.map((p, i) => (
                    <span key={i} className="px-2 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/20 text-xs font-mono">
                      {p}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-slate-500 text-xs italic">No lineage data — attributor did not run on this check</p>
        )}
      </div>

    </div>
  )
}

// ── Classification summary bar ──────────────────────────────────────────
function ClassBar({ failures }) {
  const counts = { Structural: 0, Statistical: 0, Temporal: 0, AI: 0 }
  failures.forEach(f => { counts[CLASSIFY(f.check_type).label]++ })
  const colors = {
    Structural: 'bg-red-500',
    Statistical: 'bg-orange-500',
    Temporal: 'bg-green-500',
    AI: 'bg-pink-500',
  }
  const textColors = {
    Structural: 'text-red-300',
    Statistical: 'text-orange-300',
    Temporal: 'text-green-300',
    AI: 'text-pink-300',
  }
  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
      <p className="text-slate-400 text-xs mb-3 uppercase tracking-widest font-bold">Violation Classification (from challenge doc)</p>
      <div className="grid grid-cols-4 gap-3">
        {Object.entries(counts).map(([label, count]) => (
          <div key={label} className="text-center">
            <div className={`text-3xl font-black ${textColors[label]}`}>{count}</div>
            <div className={`text-xs font-bold mt-1 ${textColors[label]}`}>{label}</div>
            <div className="text-slate-500 text-xs">
              {label === 'Structural' && 'type, nullability, uniqueness'}
              {label === 'Statistical' && 'range, drift'}
              {label === 'Temporal' && 'freshness, sequence'}
              {label === 'AI' && 'embeddings, LLM'}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 flex h-2 rounded-full overflow-hidden gap-0.5">
        {Object.entries(counts).map(([label, count]) =>
          count > 0 ? (
            <div
              key={label}
              className={`${colors[label]} h-full`}
              style={{ width: `${(count / failures.length) * 100}%` }}
              title={`${label}: ${count}`}
            />
          ) : null
        )}
      </div>
    </div>
  )
}

// ── Main ────────────────────────────────────────────────────────────────
export default function ViolationDeepDive() {
  const [failures, setFailures]           = useState([])
  const [subscriptions, setSubscriptions] = useState([])
  const [expanded, setExpanded]           = useState(0)
  const [filterClass, setFilterClass]     = useState('All')

  useEffect(() => {
    getAllFailures().then(data => {
      const sorted = [...data].sort((a, b) => {
        const sevOrder = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }
        return (sevOrder[a.severity] ?? 9) - (sevOrder[b.severity] ?? 9)
      })
      setFailures(sorted)
    }).catch(() => {})
    getSubscriptions().then(setSubscriptions).catch(() => {})
  }, [])

  const classes = ['All', 'Structural', 'Statistical', 'Temporal', 'AI']
  const visible = filterClass === 'All'
    ? failures
    : failures.filter(f => CLASSIFY(f.check_type).label === filterClass)

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-white">Violation Deep-Dive</h2>
        <p className="text-slate-400 text-sm mt-1">
          {failures.length} distinct failures across all contracts
        </p>
      </div>

      {/* Classification summary */}
      {failures.length > 0 && <ClassBar failures={failures} />}

      {/* Filter tabs */}
      <div className="flex gap-2">
        {classes.map(c => (
          <button
            key={c}
            onClick={() => { setFilterClass(c); setExpanded(null) }}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filterClass === c ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            {c}
            {c !== 'All' && (
              <span className="ml-1.5 text-xs opacity-70">
                {failures.filter(f => CLASSIFY(f.check_type).label === c).length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Failure list */}
      <div className="space-y-2">
        {visible.map((f, i) => {
          const cls    = CLASSIFY(f.check_type)
          const isOpen = expanded === i
          const subCount = subscriptions.filter(s => s.contract_id === f.contract_id).length

          return (
            <div key={f.check_id} className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
              <button
                className="w-full text-left px-5 py-4 flex items-center gap-3 hover:bg-slate-700/40 transition-colors"
                onClick={() => setExpanded(isOpen ? null : i)}
              >
                <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${SEV_DOT[f.severity] || 'bg-slate-500'}`} />
                <span className={`px-2 py-0.5 rounded text-xs font-bold border shrink-0 ${SEV_STYLE[f.severity] || SEV_STYLE.LOW}`}>
                  {f.severity}
                </span>
                <span className={`px-2 py-0.5 rounded text-xs font-bold border shrink-0 ${cls.color}`}>
                  {cls.label}
                </span>
                <span className="text-slate-200 text-sm flex-1 text-left truncate">{f.message}</span>
                <div className="flex items-center gap-3 shrink-0 text-xs text-slate-500">
                  <span className="font-mono hidden md:block">{f.check_type}</span>
                  {f.blame_chain?.length > 0 && (
                    <span className="text-indigo-400 flex items-center gap-1">
                      <GitCommit size={11} /> {f.blame_chain.length}
                    </span>
                  )}
                  {subCount > 0 && (
                    <span className="text-orange-400 flex items-center gap-1">
                      <Zap size={11} /> {subCount}
                    </span>
                  )}
                  {isOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                </div>
              </button>

              {isOpen && (
                <div className="border-t border-slate-700/50 px-5 pb-5 pt-4">
                  <div className="text-xs text-slate-500 font-mono mb-4 flex flex-wrap gap-4">
                    <span>check: <span className="text-slate-400">{f.check_id}</span></span>
                    <span>contract: <span className="text-slate-400">{f.contract_id}</span></span>
                    {f.records_failing > 0 && <span>records failing: <span className="text-red-400 font-bold">{f.records_failing}</span></span>}
                  </div>
                  <div className="grid md:grid-cols-2 gap-6">
                    <div>
                      <p className="text-slate-300 text-sm font-semibold mb-3 flex items-center gap-2">
                        <GitCommit size={14} className="text-indigo-400" />
                        Blame Chain
                        <span className="text-slate-500 text-xs font-normal">who introduced this</span>
                      </p>
                      <BlameChain chain={f.blame_chain} />
                    </div>
                    <div>
                      <p className="text-slate-300 text-sm font-semibold mb-3 flex items-center gap-2">
                        <Zap size={14} className="text-orange-400" />
                        Blast Radius
                        <span className="text-slate-500 text-xs font-normal">registered consumers at risk</span>
                      </p>
                      <BlastRadius contractId={f.contract_id} allSubscriptions={subscriptions} blastRadius={f.blast_radius} />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )
        })}

        {visible.length === 0 && (
          <div className="bg-slate-800 rounded-xl border border-slate-700 p-8 text-center text-slate-500">
            No {filterClass === 'All' ? '' : filterClass + ' '}violations found
          </div>
        )}
      </div>
    </div>
  )
}
