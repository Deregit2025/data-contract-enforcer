import { useEffect, useState } from 'react'
import { getSchemaChanges } from '../services/api'

const compatStyle = {
  BREAKING:    'bg-red-500/20 text-red-400 border border-red-500/30',
  SAFE:        'bg-green-500/20 text-green-400 border border-green-500/30',
  CRITICAL:    'bg-red-600/30 text-red-300 border border-red-600/40',
  MINOR:       'bg-slate-500/20 text-slate-400 border border-slate-500/30',
  DEPRECATION: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
}

const changeStyle = {
  TYPE_CHANGED:       'text-red-400',
  FIELD_REMOVED:      'text-red-500',
  RANGE_CHANGED:      'text-orange-400',
  FIELD_ADDED:        'text-green-400',
  NULLABLE_CHANGED:   'text-yellow-400',
  CONSTRAINT_CHANGED: 'text-orange-300',
}

export default function SchemaEvolution() {
  const [changes, setChanges] = useState([])

  useEffect(() => {
    getSchemaChanges().then(setChanges).catch(() => {})
  }, [])

  const breaking = changes.filter(c => c.compatibility === 'BREAKING' || c.compatibility === 'CRITICAL')
  const safe     = changes.filter(c => c.compatibility === 'SAFE')

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Schema Evolution</h2>
        <div className="flex gap-3 text-sm">
          <span className="px-3 py-1 rounded-full bg-red-500/20 text-red-400">{breaking.length} Breaking</span>
          <span className="px-3 py-1 rounded-full bg-green-500/20 text-green-400">{safe.length} Safe</span>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-slate-800 rounded-xl p-4 border border-slate-700 text-center">
          <p className="text-3xl font-black text-white">{changes.length}</p>
          <p className="text-slate-400 text-sm mt-1">Total Changes</p>
        </div>
        <div className="bg-slate-800 rounded-xl p-4 border border-red-500/30 text-center">
          <p className="text-3xl font-black text-red-400">{breaking.length}</p>
          <p className="text-slate-400 text-sm mt-1">Breaking Changes</p>
        </div>
        <div className="bg-slate-800 rounded-xl p-4 border border-green-500/30 text-center">
          <p className="text-3xl font-black text-green-400">{safe.length}</p>
          <p className="text-slate-400 text-sm mt-1">Safe Changes</p>
        </div>
      </div>

      {/* Changes table */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 bg-slate-900/50">
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Contract</th>
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Field</th>
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Change Type</th>
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Old Value</th>
              <th className="text-left px-4 py-3 text-slate-400 font-medium">New Value</th>
              <th className="text-center px-4 py-3 text-slate-400 font-medium">Compat</th>
            </tr>
          </thead>
          <tbody>
            {changes.map((c, i) => (
              <tr key={i} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                <td className="px-4 py-3 font-mono text-xs text-slate-300">{c.contract_id}</td>
                <td className="px-4 py-3 text-white font-medium">{c.field}</td>
                <td className={`px-4 py-3 text-xs font-mono ${changeStyle[c.change_type] || 'text-slate-400'}`}>
                  {c.change_type || '—'}
                </td>
                <td className="px-4 py-3 text-xs text-slate-400 font-mono max-w-[120px] truncate" title={c.old_value}>
                  {c.old_value || '—'}
                </td>
                <td className="px-4 py-3 text-xs text-slate-300 font-mono max-w-[120px] truncate" title={c.new_value}>
                  {c.new_value || '—'}
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium border ${compatStyle[c.compatibility] || compatStyle.MINOR}`}>
                    {c.compatibility || '—'}
                  </span>
                </td>
              </tr>
            ))}
            {changes.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">No schema changes detected</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Reason column as expandable info below table */}
      {changes.filter(c => c.reason).length > 0 && (
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
          <p className="text-slate-400 text-sm mb-3">Change Reasons</p>
          <div className="space-y-2">
            {changes.filter(c => c.reason).map((c, i) => (
              <div key={i} className="text-xs text-slate-400 flex gap-2">
                <span className="text-slate-500 font-mono shrink-0">{c.field}:</span>
                <span>{c.reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
