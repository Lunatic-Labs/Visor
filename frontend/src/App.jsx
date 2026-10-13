import { useState } from 'react'
import Schedule from './Schedule.jsx'
import TransferLookup from './TransferLookup.jsx'
import PrereqCheck from './PrereqCheck.jsx'

const TABS = [
  { id: 'schedule', label: 'Schedule & Conflicts', Component: Schedule },
  { id: 'transfer', label: 'Transfer Course Lookup', Component: TransferLookup },
  { id: 'prereqs', label: 'Prerequisites', Component: PrereqCheck },
  { id: 'degree', label: 'Degree Progress', Component: ComingSoon },
]

// Placeholder: no backend yet for program/requirement tracking. Scope TBD after we meet
// with the registrar about what she actually needs here.
function ComingSoon() {
  return <p className="hint">Coming soon — scope still being worked out with the registrar.</p>
}

export default function App() {
  const [activeId, setActiveId] = useState(TABS[0].id)
  const Active = TABS.find((t) => t.id === activeId).Component

  return (
    <main>
      <header>
        <h1>Visor</h1>
      </header>

      <nav className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={t.id === activeId ? 'active' : ''}
            onClick={() => setActiveId(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <Active />
    </main>
  )
}
