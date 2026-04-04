import { useEffect, useState } from 'react'
import { getViolations } from '../services/api'
import { AlertOctagon, GitBranch, Zap } from 'lucide-react'

const sevStyle = {
  CRITICAL: { badge: 'bg-red-500/20 text-red-400 border border-red-500/30', dot: 'bg-red-500' },
  HIGH:     { badge: 'bg-orange-500/20 text-orange-400 border border-orange-500/30', dot: 'bg-orange-500' },
  MEDIUM:   { badge: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30', dot: 'bg-yellow-500' },
  LOW:      { badge: 'bg-blue-500/20 text-blue-400 border border-blue-500/30', dot: 'bg-blue-500' },
}

function BlameChain({ chain }) {
  if (!chain || !chain.length) return <span className="text-slate-500 text-xs">No blame data</span>
  return (
    <div className="space-y-1 mt-2">
      {chain.slice(0, 3).map((entry, i) => (
        <div key={i} className="flex items-center gap-2 text-xs text-slate-400">
          <GitBranch size={12} className="text-indigo-400 shrink-0" />
          <span className="font-mono">{entry.commit?.slice(0, 7) || '?'}</span>
          <span className="text-slate-500">by</span>
          <span className="text-slate-300">{entry.author || 'unknown'}</span>
          {entry.score !== undefined && (
            <span className="ml-auto text-indigo-400">score: {entry.score.toFixed(2)}</span>
          )}
        </div>
      ))}
    </div>
  )
}

function BlastRadius({ radius }) {
  if (!radius) return <span className="text-slate-500 text-xs">No blast radius</span>
  const consumers = radius.consumers || radius.affected_subscribers || []
  const pipelines = radius.affected_pipelines || []
  return (
    <div className="text-xs space-y-1 mt-2">
      {consumers.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {consumers.slice(0, 4).map((c, i) => (
            <span key={i} className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/20">
              {typeof c === 'string' ? c : c.subscriber_id || JSON.stringify(c)}
            </span>
          ))}
        </div>
      )}
      {pipelines.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {pipelines.slice(0, 3).map((p, i) => (
            <span key={i} className="px-2 py-0.5 rounded bg-slate-600/50 text-slate-300">{p}</span>
          ))}
        </div>
      )}
      {consumers.length === 0 && pipelines.length === 0 && (
        <span className="text-slate-500">No downstream consumers</span>
      )}
    </div>
  )
}

export default function ViolationDeepDive() {
  const [violations, setViolations] = useState([])
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    getViolations({ exclude_injected: true }).then(setViolations).catch(() => {})
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Violation Deep-Dive</h2>
        <span className="text-slate-400 text-sm">{violations.length} active violations</span>
      </div>

      <div className="space-y-3">
        {violations.map((v, i) => {
          const sev = sevStyle[v.severity] || sevStyle.LOW
          const isOpen = expanded === i
          return (
            <div
              key={v.violation_id}
              className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden"
            >
              <button
                className="w-full text-left px-5 py-4 flex items-center gap-3 hover:bg-slate-700/40 transition-colors"
                onClick={() => setExpanded(isOpen ? null : i)}
              >
                <div className={`w-2 h-2 rounded-full shrink-0 ${sev.dot}`} />
                <span className={`px-2 py-0.5 rounded text-xs font-bold border ${sev.badge}`}>
                  {v.severity}
                </span>
                <span className="text-slate-200 text-sm flex-1">{v.message || 'No message'}</span>
                <span className="text-slate-500 text-xs font-mono">{v.check_id}</span>
                <span className="text-slate-500 text-lg">{isOpen ? '▲' : '▼'}</span>
              </button>

              {isOpen && (
                <div className="px-5 pb-5 border-t border-slate-700/50 pt-4 grid md:grid-cols-2 gap-6">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <GitBranch size={14} className="text-indigo-400" />
                      <span className="text-slate-300 text-sm font-medium">Blame Chain</span>
                    </div>
                    <BlameChain chain={v.blame_chain} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <Zap size={14} className="text-purple-400" />
                      <span className="text-slate-300 text-sm font-medium">Blast Radius</span>
                    </div>
                    <BlastRadius radius={v.blast_radius} />
                  </div>
                  <div className="col-span-2 text-xs text-slate-500 font-mono">
                    ID: {v.violation_id} · Detected: {v.detected_at || 'unknown'}
                  </div>
                </div>
              )}
            </div>
          )
        })}

        {violations.length === 0 && (
          <div className="bg-slate-800 rounded-xl border border-slate-700 p-8 text-center text-slate-500">
            No violations found
          </div>
        )}
      </div>
    </div>
  )
}
