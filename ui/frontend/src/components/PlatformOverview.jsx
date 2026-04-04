import { useEffect, useState } from 'react'
import { getHealth, getViolationSummary } from '../services/api'
import { RadialBarChart, RadialBar, PolarAngleAxis, ResponsiveContainer } from 'recharts'
import { Shield, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className="bg-slate-800 rounded-xl p-5 flex items-center gap-4 border border-slate-700">
      <div className={`p-3 rounded-lg ${color}`}>
        <Icon size={22} className="text-white" />
      </div>
      <div>
        <p className="text-slate-400 text-sm">{label}</p>
        <p className="text-2xl font-bold text-white">{value}</p>
      </div>
    </div>
  )
}

export default function PlatformOverview() {
  const [health, setHealth] = useState(null)
  const [summary, setSummary] = useState({})

  useEffect(() => {
    getHealth().then(setHealth).catch(() => {})
    getViolationSummary().then(setSummary).catch(() => {})
  }, [])

  if (!health) return <p className="text-slate-400 p-8">Loading platform health…</p>

  const score = health.health_score
  const scoreColor = score >= 90 ? '#22c55e' : score >= 70 ? '#eab308' : '#ef4444'
  const gaugeData = [{ value: score, fill: scoreColor }]

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white mb-1">Platform Overview</h2>
        <p className="text-slate-400 text-sm">{health.health_narrative}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Gauge */}
        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 flex flex-col items-center">
          <p className="text-slate-400 text-sm mb-2">Platform Health Score</p>
          <div className="w-48 h-48">
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart
                cx="50%" cy="50%" innerRadius="70%" outerRadius="100%"
                data={gaugeData} startAngle={90} endAngle={-270}
              >
                <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                <RadialBar dataKey="value" background={{ fill: '#1e293b' }} cornerRadius={10} />
              </RadialBarChart>
            </ResponsiveContainer>
          </div>
          <p className="text-5xl font-black mt-[-60px]" style={{ color: scoreColor }}>{score}</p>
          <p className="text-slate-400 text-xs mt-1">out of 100</p>
        </div>

        {/* Violation breakdown */}
        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
          <p className="text-slate-400 text-sm mb-4">Active Violations by Severity</p>
          <div className="space-y-3">
            {[
              { sev: 'CRITICAL', color: 'bg-red-500' },
              { sev: 'HIGH',     color: 'bg-orange-500' },
              { sev: 'MEDIUM',   color: 'bg-yellow-500' },
              { sev: 'LOW',      color: 'bg-blue-500' },
            ].map(({ sev, color }) => {
              const cnt = summary[sev] || 0
              const max = Math.max(...Object.values(summary), 1)
              return (
                <div key={sev} className="flex items-center gap-3">
                  <span className="text-slate-300 text-sm w-20">{sev}</span>
                  <div className="flex-1 bg-slate-700 rounded-full h-3">
                    <div
                      className={`${color} h-3 rounded-full transition-all`}
                      style={{ width: `${(cnt / max) * 100}%` }}
                    />
                  </div>
                  <span className="text-white font-bold w-8 text-right">{cnt}</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={Shield}        label="Contracts"    value={health.contract_count}  color="bg-indigo-600" />
        <StatCard icon={CheckCircle}   label="Checks Passed" value={health.total_passed}   color="bg-green-600" />
        <StatCard icon={XCircle}       label="Checks Failed" value={health.total_failed}   color="bg-red-600" />
        <StatCard icon={AlertTriangle} label="Warned"        value={health.total_warned}   color="bg-yellow-600" />
      </div>
    </div>
  )
}
