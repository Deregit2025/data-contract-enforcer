import { useState } from 'react'
import './index.css'
import PlatformOverview  from './components/PlatformOverview'
import HealthDashboard   from './components/HealthDashboard'
import ValidationResults from './components/ValidationResults'
import ViolationDeepDive from './components/ViolationDeepDive'
import SchemaEvolution   from './components/SchemaEvolution'
import AiExtensions      from './components/AiExtensions'
import InterfaceRisk     from './components/InterfaceRisk'
import { Database, Activity, CheckSquare, AlertOctagon, GitMerge, Brain, Wifi } from 'lucide-react'

const TABS = [
  { id: 'overview',    label: 'Platform Overview',    icon: Activity },
  { id: 'health',      label: 'Contract Health',      icon: Database },
  { id: 'validation',  label: 'Validation Results',   icon: CheckSquare },
  { id: 'violations',  label: 'Violation Deep-Dive',  icon: AlertOctagon },
  { id: 'schema',      label: 'Schema Evolution',     icon: GitMerge },
  { id: 'ai',          label: 'AI Extensions',        icon: Brain },
  { id: 'interfaces',  label: 'Interface Risk',       icon: Wifi },
]

export default function App() {
  const [active, setActive] = useState('overview')

  const ActiveComponent = {
    overview:   PlatformOverview,
    health:     HealthDashboard,
    validation: ValidationResults,
    violations: ViolationDeepDive,
    schema:     SchemaEvolution,
    ai:         AiExtensions,
    interfaces: InterfaceRisk,
  }[active]

  return (
    <div className="min-h-screen bg-slate-900 flex">
      {/* Sidebar */}
      <aside className="w-60 bg-slate-950 border-r border-slate-800 flex flex-col shrink-0">
        <div className="p-5 border-b border-slate-800">
          <h1 className="text-white font-black text-base leading-tight">Contract<br/>Enforcer</h1>
          <p className="text-slate-500 text-xs mt-1">Data Quality Dashboard</p>
        </div>
        <nav className="p-3 flex-1 space-y-1">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActive(id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                active === id
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>
        <div className="p-4 border-t border-slate-800">
          <p className="text-slate-600 text-xs">FastAPI · PostgreSQL</p>
          <p className="text-slate-600 text-xs">React · Recharts</p>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto p-8">
          {ActiveComponent && <ActiveComponent />}
        </div>
      </main>
    </div>
  )
}
