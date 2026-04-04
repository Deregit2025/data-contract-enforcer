import { useEffect, useState } from 'react'
import { getContracts, getContractResults } from '../services/api'

const statusStyle = {
  PASS:    'bg-green-500/20 text-green-400 border border-green-500/30',
  FAIL:    'bg-red-500/20 text-red-400 border border-red-500/30',
  WARN:    'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
  ERROR:   'bg-orange-500/20 text-orange-400 border border-orange-500/30',
  UNKNOWN: 'bg-slate-500/20 text-slate-400 border border-slate-500/30',
}

const sevStyle = {
  CRITICAL: 'text-red-400',
  HIGH:     'text-orange-400',
  MEDIUM:   'text-yellow-400',
  LOW:      'text-blue-400',
}

export default function ValidationResults() {
  const [contracts, setContracts] = useState([])
  const [selected, setSelected] = useState('')
  const [results, setResults]   = useState([])
  const [loading, setLoading]   = useState(false)

  useEffect(() => {
    getContracts().then(cs => {
      setContracts(cs)
      if (cs.length) setSelected(cs[0].contract_id)
    })
  }, [])

  useEffect(() => {
    if (!selected) return
    setLoading(true)
    getContractResults(selected)
      .then(setResults)
      .finally(() => setLoading(false))
  }, [selected])

  const pass = results.filter(r => r.status === 'PASS').length
  const fail = results.filter(r => r.status === 'FAIL').length
  const warn = results.filter(r => r.status === 'WARN').length

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Validation Run Results</h2>

      {/* Contract selector */}
      <div className="flex items-center gap-4">
        <label className="text-slate-400 text-sm">Contract:</label>
        <select
          value={selected}
          onChange={e => setSelected(e.target.value)}
          className="bg-slate-800 border border-slate-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
        >
          {contracts.map(c => (
            <option key={c.contract_id} value={c.contract_id}>{c.contract_id}</option>
          ))}
        </select>

        {/* Summary pills */}
        {results.length > 0 && (
          <div className="flex gap-2 ml-4">
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-green-500/20 text-green-400">{pass} PASS</span>
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-red-500/20 text-red-400">{fail} FAIL</span>
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-yellow-500/20 text-yellow-400">{warn} WARN</span>
          </div>
        )}
      </div>

      {/* Results table */}
      {loading ? (
        <p className="text-slate-400">Loading…</p>
      ) : (
        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 bg-slate-900/50">
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Check ID</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Column</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Type</th>
                <th className="text-center px-4 py-3 text-slate-400 font-medium">Status</th>
                <th className="text-center px-4 py-3 text-slate-400 font-medium">Severity</th>
                <th className="text-right px-4 py-3 text-slate-400 font-medium">Failing</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Message</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={i} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                  <td className="px-4 py-3 font-mono text-xs text-slate-300">{r.check_id}</td>
                  <td className="px-4 py-3 text-slate-300">{r.column_name || '—'}</td>
                  <td className="px-4 py-3 text-slate-400 text-xs">{r.check_type || '—'}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusStyle[r.status] || statusStyle.UNKNOWN}`}>
                      {r.status}
                    </span>
                  </td>
                  <td className={`px-4 py-3 text-center text-xs font-bold ${sevStyle[r.severity] || 'text-slate-400'}`}>
                    {r.severity || '—'}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-300">{r.records_failing || 0}</td>
                  <td className="px-4 py-3 text-slate-400 text-xs max-w-xs truncate" title={r.message}>{r.message || '—'}</td>
                </tr>
              ))}
              {results.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-slate-500">No results for this contract</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
