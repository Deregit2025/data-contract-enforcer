export default function ProjectOverview() {
  return (
    <div className="space-y-8 max-w-4xl">

      {/* Title */}
      <div>
        <h2 className="text-3xl font-black text-white">Data Contract Enforcer</h2>
        <p className="text-indigo-300 mt-1">Automated data quality enforcement across multi-week AI pipelines</p>
      </div>

      {/* Why */}
      <Section title="The Problem" color="red">
        <p className="text-slate-300 text-sm leading-relaxed">
          Modern data pipelines are fragile. When an upstream team changes a schema — renames a field,
          removes a column, narrows a value range — downstream consumers break silently.
          There is no contract, no warning, no audit trail. Data quality issues surface in production,
          often days later, with no clear owner.
        </p>
        <div className="grid grid-cols-3 gap-4 mt-4">
          <Problem text="Schema changes break downstream consumers with no warning" />
          <Problem text="No way to know who introduced a bad change or when" />
          <Problem text="Teams don't know which pipelines are affected by a violation" />
        </div>
      </Section>

      {/* Solution */}
      <Section title="The Solution" color="green">
        <p className="text-slate-300 text-sm leading-relaxed">
          A contract-first enforcement layer. Each data interface is described in a YAML contract
          (Bitol format) that defines schema, quality rules, SLA, and consumers.
          Every week the validator runs all checks, logs violations, traces blame via git history,
          and computes the blast radius — which teams are at risk.
        </p>
        <div className="grid grid-cols-2 gap-3 mt-4">
          <Feature icon="📄" title="YAML Contracts" desc="Schema, nullability, ranges, freshness — all declared in one file per dataset." />
          <Feature icon="✅" title="Automated Validation" desc="Custom Python runner reads each contract and executes all checks — nullability, ranges, freshness, uniqueness — against the raw data." />
          <Feature icon="🔍" title="Violation Attribution" desc="Git blame identifies the exact commit and author that introduced each violation." />
          <Feature icon="💥" title="Blast Radius" desc="Registry subscriptions map which consumers are exposed to each violation." />
          <Feature icon="📈" title="Schema Evolution" desc="Snapshot comparison detects breaking vs safe changes between weeks." />
          <Feature icon="🤖" title="AI Extensions" desc="Embedding drift, prompt input validation, and LLM output schema enforcement." />
        </div>
      </Section>

      {/* Architecture diagram */}
      <Section title="Architecture" color="indigo">
        <p className="text-slate-400 text-sm mb-5">End-to-end data flow from raw data to enforced contracts:</p>
        <div className="flex flex-col gap-2">

          {/* Row 1 */}
          <div className="flex items-center gap-2">
            <Box label="Week 1–5 Data" sub="raw datasets" color="slate" />
            <Arrow />
            <Box label="YAML Contracts" sub="Bitol format" color="indigo" />
            <Arrow />
            <Box label="Validation Engine" sub="runner.py (custom)" color="indigo" />
            <Arrow />
            <Box label="Validation Reports" sub="JSON per week" color="slate" />
          </div>

          {/* Down arrow from Validation Engine */}
          <div className="flex items-center gap-2">
            <Spacer /><Spacer /><Spacer />
            <DownArrow />
            <Spacer />
          </div>

          {/* Row 2 */}
          <div className="flex items-center gap-2">
            <Box label="Schema Analyzer" sub="breaking vs safe" color="purple" />
            <Arrow />
            <Box label="Violation Attributor" sub="git blame + score" color="purple" />
            <Arrow />
            <Box label="Blast Radius" sub="registry lookup" color="purple" />
            <Arrow />
            <Box label="Report Generator" sub="actions + PDF" color="purple" />
          </div>

          {/* Down arrow to DB */}
          <div className="flex items-center gap-2">
            <Spacer /><Spacer />
            <DownArrow />
            <Spacer /><Spacer />
          </div>

          {/* Row 3 */}
          <div className="flex items-center gap-2">
            <Box label="PostgreSQL" sub="contracts, violations, reports" color="orange" />
            <Arrow />
            <Box label="FastAPI" sub="10 REST endpoints" color="orange" />
            <Arrow />
            <Box label="React Dashboard" sub="this UI" color="green" />
          </div>

        </div>
      </Section>

      {/* Key Design Decisions */}
      <Section title="Key Design Decisions" color="yellow">
        <div className="space-y-3">
          <Decision
            decision="One YAML contract file per dataset"
            reason="Each dataset (e.g. week3_document_refinery_extractions.yaml) owns its own contract. A companion _dbt.yml is also generated for schema declarations. Ownership is explicit and git-trackable."
          />
          <Decision
            decision="Blame score = max(0.05,  1.0 - (days_since_commit × 0.1) - (hop_count × 0.2))"
            reason="Recency and proximity both matter. A commit from today on a direct upstream file scores ~1.0. A commit from 7 days ago two hops away scores ~0.17. Floor of 0.05 prevents zeroing out known contributors."
          />
          <Decision
            decision="Blast radius: registry lookup (primary) + lineage graph traversal (enrichment)"
            reason="Registry subscriptions.yaml is queried first to find declared consumers of the failing field. The NetworkX lineage graph then finds undeclared downstream nodes and pipelines. Both are stored in the violation log."
          />
          <Decision
            decision="Semantic narrowing is CRITICAL when new_span / old_span >= 50, or field name contains 'confidence'"
            reason="A range change from 0–100 to 0–1 is a 100x scale collapse — not a safe schema change. Any field named 'confidence' is also flagged CRITICAL by name, since scale errors on confidence scores corrupt all downstream ML models silently."
          />
          <Decision
            decision="Recommended actions are derived from check_id, not hardcoded"
            reason="check_id format is {contract_id}.{field}.{check_type}. report_generator.py parses this to name the exact contract file path and clause, so every action points directly to the file and rule that needs fixing."
          />
        </div>
      </Section>

      {/* Tech stack */}
      <Section title="Technology Stack" color="slate">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Tech layer="Contracts" items={["Bitol YAML (v3.0.0)", "dbt schema.yml (generated)", "Custom runner.py"]} />
          <Tech layer="Backend" items={["Python 3.11", "FastAPI", "SQLAlchemy", "PostgreSQL"]} />
          <Tech layer="Analysis" items={["GitPython (blame)", "PyYAML", "Pandas + NumPy", "OpenAI embeddings"]} />
          <Tech layer="Frontend" items={["React + Vite", "Tailwind CSS", "Recharts", "Lucide Icons"]} />
        </div>
      </Section>

    </div>
  )
}

function Section({ title, color, children }) {
  const border = {
    red: 'border-red-500/30', green: 'border-green-500/30',
    indigo: 'border-indigo-500/30', yellow: 'border-yellow-500/30',
    purple: 'border-purple-500/30', slate: 'border-slate-600/50',
  }[color] || 'border-slate-600/50'
  const heading = {
    red: 'text-red-400', green: 'text-green-400',
    indigo: 'text-indigo-400', yellow: 'text-yellow-400',
    purple: 'text-purple-400', slate: 'text-slate-300',
  }[color] || 'text-slate-300'

  return (
    <div className={`bg-slate-800/60 rounded-xl p-6 border ${border}`}>
      <h3 className={`text-sm font-bold uppercase tracking-widest mb-4 ${heading}`}>{title}</h3>
      {children}
    </div>
  )
}

function Problem({ text }) {
  return (
    <div className="bg-red-900/20 border border-red-500/20 rounded-lg p-3">
      <p className="text-red-300 text-xs leading-relaxed">{text}</p>
    </div>
  )
}

function Feature({ icon, title, desc }) {
  return (
    <div className="flex gap-3 items-start">
      <span className="text-xl shrink-0">{icon}</span>
      <div>
        <p className="text-white text-sm font-semibold">{title}</p>
        <p className="text-slate-400 text-xs mt-0.5">{desc}</p>
      </div>
    </div>
  )
}

function Decision({ decision, reason }) {
  return (
    <div className="flex gap-3 items-start">
      <span className="text-yellow-400 text-xs font-black mt-0.5 shrink-0">DECISION</span>
      <div>
        <p className="text-white text-sm font-medium">{decision}</p>
        <p className="text-slate-400 text-xs mt-0.5">Why: {reason}</p>
      </div>
    </div>
  )
}

function Tech({ layer, items }) {
  return (
    <div className="bg-slate-900/60 rounded-lg p-3">
      <p className="text-slate-400 text-xs font-bold uppercase tracking-wide mb-2">{layer}</p>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className="text-slate-300 text-xs">{item}</li>
        ))}
      </ul>
    </div>
  )
}

function Box({ label, sub, color }) {
  const styles = {
    slate:  'bg-slate-700/60 border-slate-600',
    indigo: 'bg-indigo-900/40 border-indigo-500/40',
    purple: 'bg-purple-900/40 border-purple-500/40',
    orange: 'bg-orange-900/30 border-orange-500/30',
    green:  'bg-green-900/30 border-green-500/30',
  }[color] || 'bg-slate-700/60 border-slate-600'
  return (
    <div className={`flex-1 border rounded-lg px-3 py-2 text-center ${styles}`}>
      <p className="text-white text-xs font-semibold leading-tight">{label}</p>
      <p className="text-slate-400 text-xs mt-0.5">{sub}</p>
    </div>
  )
}

function Arrow() {
  return <span className="text-slate-500 text-sm shrink-0">→</span>
}

function DownArrow() {
  return (
    <div className="flex-1 flex justify-center text-slate-500 text-sm">↓</div>
  )
}

function Spacer() {
  return <div className="flex-1" />
}
