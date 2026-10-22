import { useState } from 'react'
import Schedule from './Schedule.jsx'
import TransferLookup from './TransferLookup.jsx'
import PrereqCheck from './PrereqCheck.jsx'
import CatalogImport from './CatalogImport.jsx'

const TABS = [
  { id: 'schedule', label: 'Schedule & Conflicts', Component: Schedule },
  { id: 'transfer', label: 'Transfer Course Lookup', Component: TransferLookup },
  { id: 'prereqs', label: 'Prerequisites', Component: PrereqCheck },
  { id: 'import', label: 'Import Catalog', Component: CatalogImport },
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
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">V</span>
          <span className="brand-text">
            <strong>Visor</strong>
            <span className="brand-sub">Lipscomb Registrar</span>
          </span>
        </div>

        <nav className="tabs">
          {TABS.map((t) => (
            <button
              type="button"
              key={t.id}
              className={t.id === activeId ? 'active' : ''}
              aria-pressed={t.id === activeId}
              onClick={() => setActiveId(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main>
        <Active />
      </main>
    </div>
  )
}
