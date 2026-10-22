import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import { PageHead } from './ui.jsx'
import Dashboard from './Dashboard.jsx'
import TransferLookup from './TransferLookup.jsx'
import ReviewQueue from './ReviewQueue.jsx'
import Library from './Library.jsx'
import CatalogImport from './CatalogImport.jsx'
import Schedule from './Schedule.jsx'
import PrereqCheck from './PrereqCheck.jsx'

function DegreeAudit() {
  return (
    <>
      <PageHead title="Degree audit">
        Coming after transfer equivalencies: see how a student's Lipscomb and transfer credit count toward their major.
      </PageHead>
      <section className="card empty">
        <h2>Not built yet</h2>
        <p className="muted">Next on the roadmap once equivalencies are settled.</p>
      </section>
    </>
  )
}

const TABS = [
  { id: 'dashboard', label: 'Dashboard', Component: Dashboard },
  { id: 'lookup', label: 'Look Up', Component: TransferLookup },
  { id: 'review', label: 'Review Queue', Component: ReviewQueue, showCount: true },
  { id: 'library', label: 'Library', Component: Library },
  { id: 'import', label: 'Import Catalog', Component: CatalogImport },
  { id: 'schedule', label: 'Schedule', Component: Schedule },
  { id: 'prereqs', label: 'Prerequisites', Component: PrereqCheck },
  { id: 'degree', label: 'Degree Audit', Component: DegreeAudit, soon: true },
]

const NAME_KEY = 'visor.name'
function savedName() {
  try { return localStorage.getItem(NAME_KEY) || '' } catch { return '' }
}

export default function App() {
  const [activeId, setActiveId] = useState('dashboard')
  const [actor, setActorState] = useState(savedName)
  const [reviewCount, setReviewCount] = useState(null)
  const Active = TABS.find((t) => t.id === activeId).Component

  function setActor(name) {
    setActorState(name)
    try { localStorage.setItem(NAME_KEY, name) } catch { /* private window: name just won't persist */ }
  }

  const refreshCount = useCallback(() => {
    api('/api/equivalencies/summary').then((s) => setReviewCount(s.proposed)).catch(() => {})
  }, [])
  useEffect(() => { refreshCount() }, [refreshCount, activeId])

  return (
    <div className="app-shell">
      <header className="topbar">
        <button type="button" className="brand" onClick={() => setActiveId('dashboard')}>
          <span className="brand-mark">V</span>
          <span className="brand-text">
            <strong>VISOR</strong>
            <span className="brand-sub">Lipscomb Registrar</span>
          </span>
        </button>

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
              {t.showCount && reviewCount > 0 && <span className="tab-count">{reviewCount}</span>}
              {t.soon && <span className="tab-soon">Soon</span>}
            </button>
          ))}
        </nav>

        <label className="whoami">
          <span>Your name</span>
          <input value={actor} onChange={(e) => setActor(e.target.value)} placeholder="Needed to approve" />
        </label>
      </header>

      <main>
        <Active actor={actor} navigate={setActiveId} onChange={refreshCount} />
      </main>
    </div>
  )
}
