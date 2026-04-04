import { useEffect, useState } from 'react'
import { getInterfaces } from '../services/api'
import { ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer, ZAxis } from 'recharts'
import { AlertTriangle } from 'lucide-react'

function RiskBadge({ score }) {
  if (score >= 15) return <span className="px-2 py-0.5 rounded text-xs font-bold bg-red-500/20 text-red-400 border border-red-500/30">CRITICAL</span>
  if (score >= 10) return <span className="px-2 py-0.5 rounded text-xs font-bold bg-orange-500/20 text-orange-400 border border-orange-500/30">HIGH</span>
  if (score >= 6)  return <span className="px-2 py-0.5 rounded text-xs font-bold bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">MEDIUM</span>
  return <span className="px-2 py-0.5 rounded text-xs font-bold bg-green-500/20 text-green-400 border border-green-500/30">LOW</span>
}

const modeStyle = {
  ENFORCE: 'bg-red-500/20 text-red-300',
  WARN:    'bg-yellow-500/20 text-yellow-300',
  AUDIT:   'bg-blue-500/20 text-blue-300',
  OBSERVE: 'bg-slate-500/20 text-slate-300',
}

export default function InterfaceRisk() {
  const [interfaces, setInterfaces] = useState([])

  useEffect(() => {
    getInterfaces().then(setInterfaces).catch(() => {})
  }, [])

  const top = interfaces[0]
  const scatterData = interfaces.map(d => ({
    x: d.breaking_field_count,
    y: d.active_critical,
    z: d.risk_score,
    name: `${d.contract_id} → ${d.subscriber_id}`,
  }))

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Highest-Risk Interface</h2>

      {/* Top risk highlight */}
      {top && (
        <div className="bg-gradient-to-r from-red-900/40 to-orange-900/20 rounded-xl p-6 border border-red-500/40">
          <div className="flex items-center gap-3 mb-3">
            <AlertTriangle size={20} className="text-red-400" />
            <span className="text-red-400 font-bold text-sm uppercase tracking-wide">Highest Risk Interface</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-slate-400 text-xs">Contract</p>
              <p className="text-white font-mono text-sm">{top.contract_id}</p>
            </div>
            <div>
              <p className="text-slate-400 text-xs">Subscriber</p>
              <p className="text-white font-mono text-sm">{top.subscriber_id}</p>
            </div>
            <div>
              <p className="text-slate-400 text-xs">Risk Score</p>
              <p className="text-5xl font-black text-red-400">{top.risk_score}</p>
            </div>
            <div>
              <p className="text-slate-400 text-xs">Mode</p>
              <span className={`px-3 py-1 rounded-full text-sm font-bold ${modeStyle[top.validation_mode] || modeStyle.AUDIT}`}>
                {top.validation_mode}
              </span>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4 mt-4">
            <div className="bg-slate-900/40 rounded-lg p-3">
              <p className="text-xs text-slate-400">Breaking Fields</p>
              <p className="text-xl font-bold text-orange-400">{top.breaking_field_count}</p>
            </div>
            <div className="bg-slate-900/40 rounded-lg p-3">
              <p className="text-xs text-slate-400">Active Critical Violations</p>
              <p className="text-xl font-bold text-red-400">{top.active_critical}</p>
            </div>
            <div className="bg-slate-900/40 rounded-lg p-3">
              <p className="text-xs text-slate-400">Active High Violations</p>
              <p className="text-xl font-bold text-orange-400">{top.active_high}</p>
            </div>
          </div>
          {top.contact && (
            <p className="text-slate-400 text-xs mt-3">Contact: <span className="text-slate-300">{top.contact}</span></p>
          )}
        </div>
      )}

      {/* Risk scatter */}
      <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
        <p className="text-slate-400 text-sm mb-4">Risk Matrix: Breaking Fields vs Critical Violations (bubble = risk score)</p>
        <ResponsiveContainer width="100%" height={240}>
          <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
            <XAxis dataKey="x" name="Breaking Fields" tick={{ fill: '#94a3b8', fontSize: 12 }} label={{ value: 'Breaking Fields', position: 'insideBottom', fill: '#64748b', fontSize: 12, offset: -10 }} />
            <YAxis dataKey="y" name="Critical Violations" tick={{ fill: '#94a3b8', fontSize: 12 }} label={{ value: 'Critical Violations', angle: -90, position: 'insideLeft', fill: '#64748b', fontSize: 12 }} />
            <ZAxis dataKey="z" range={[60, 400]} />
            <Tooltip
              contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
              cursor={{ strokeDasharray: '3 3' }}
              formatter={(v, name) => [v, name]}
              labelFormatter={(_, payload) => payload?.[0]?.payload?.name || ''}
            />
            <Scatter data={scatterData} fill="#f97316" opacity={0.8} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      {/* Full table */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 bg-slate-900/50">
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Contract</th>
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Subscriber</th>
              <th className="text-center px-4 py-3 text-slate-400 font-medium">Mode</th>
              <th className="text-right px-4 py-3 text-slate-400 font-medium">Breaking Fields</th>
              <th className="text-right px-4 py-3 text-slate-400 font-medium">Critical</th>
              <th className="text-right px-4 py-3 text-slate-400 font-medium">High</th>
              <th className="text-right px-4 py-3 text-slate-400 font-medium">Risk Score</th>
              <th className="text-center px-4 py-3 text-slate-400 font-medium">Level</th>
            </tr>
          </thead>
          <tbody>
            {interfaces.map((d, i) => (
              <tr key={i} className={`border-b border-slate-700/50 hover:bg-slate-700/30 ${i === 0 ? 'bg-red-900/10' : ''}`}>
                <td className="px-4 py-3 font-mono text-xs text-slate-300">{d.contract_id}</td>
                <td className="px-4 py-3 font-mono text-xs text-slate-300">{d.subscriber_id}</td>
                <td className="px-4 py-3 text-center">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${modeStyle[d.validation_mode] || modeStyle.AUDIT}`}>
                    {d.validation_mode}
                  </span>
                </td>
                <td className="px-4 py-3 text-right text-orange-400 font-bold">{d.breaking_field_count}</td>
                <td className="px-4 py-3 text-right text-red-400 font-bold">{d.active_critical}</td>
                <td className="px-4 py-3 text-right text-orange-400">{d.active_high}</td>
                <td className="px-4 py-3 text-right text-white font-black text-base">{d.risk_score}</td>
                <td className="px-4 py-3 text-center"><RiskBadge score={d.risk_score} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
