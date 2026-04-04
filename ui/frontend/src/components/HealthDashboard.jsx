import { useEffect, useState } from 'react'
import { getContractHealth } from '../services/api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const statusColor = { HEALTHY: '#22c55e', WARNING: '#eab308', CRITICAL: '#ef4444' }
const statusBadge = { HEALTHY: 'bg-green-500/20 text-green-400', WARNING: 'bg-yellow-500/20 text-yellow-400', CRITICAL: 'bg-red-500/20 text-red-400' }

export default function HealthDashboard() {
  const [data, setData] = useState([])

  useEffect(() => {
    getContractHealth().then(setData).catch(() => {})
  }, [])

  const chartData = data.map(d => ({
    name: d.contract_id.replace('contract-', '').replace('-', '\n'),
    pass_rate: d.pass_rate ?? 0,
    status: d.status,
  }))

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Contract Health Dashboard</h2>

      {/* Bar chart */}
      <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
        <p className="text-slate-400 text-sm mb-4">Pass Rate by Contract (%)</p>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} margin={{ top: 0, right: 20, bottom: 60, left: 0 }}>
            <XAxis
              dataKey="name"
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              angle={-35}
              textAnchor="end"
              interval={0}
            />
            <YAxis domain={[0, 100]} tick={{ fill: '#94a3b8', fontSize: 12 }} />
            <Tooltip
              contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
              labelStyle={{ color: '#e2e8f0' }}
              formatter={(v) => [`${v}%`, 'Pass Rate']}
            />
            <Bar dataKey="pass_rate" radius={[4, 4, 0, 0]}>
              {chartData.map((entry, i) => (
                <Cell key={i} fill={statusColor[entry.status] || '#6366f1'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Table */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 bg-slate-900/50">
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Contract</th>
              <th className="text-right px-4 py-3 text-slate-400 font-medium">Checks</th>
              <th className="text-right px-4 py-3 text-slate-400 font-medium">Passed</th>
              <th className="text-right px-4 py-3 text-slate-400 font-medium">Failed</th>
              <th className="text-right px-4 py-3 text-slate-400 font-medium">Pass %</th>
              <th className="text-center px-4 py-3 text-slate-400 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {data.map((d, i) => (
              <tr key={i} className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors">
                <td className="px-4 py-3 text-white font-mono text-xs">{d.contract_id}</td>
                <td className="px-4 py-3 text-right text-slate-300">{d.total_checks}</td>
                <td className="px-4 py-3 text-right text-green-400">{d.passed}</td>
                <td className="px-4 py-3 text-right text-red-400">{d.failed}</td>
                <td className="px-4 py-3 text-right text-white font-bold">{d.pass_rate ?? 'N/A'}%</td>
                <td className="px-4 py-3 text-center">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${statusBadge[d.status]}`}>
                    {d.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
