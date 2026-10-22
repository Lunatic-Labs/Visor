import { useEffect, useState } from 'react'
import { SIS_DECIDER, api } from './api.js'
import { PageHead, StatusBadge, lipscombLabel } from './ui.jsx'

export default function Dashboard({ navigate }) {
  const [s, setS] = useState(null)
  const [recent, setRecent] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    api('/api/equivalencies/summary').then(setS).catch((e) => setError(e.message))
    api('/api/equivalencies')
      .then((rows) => setRecent(rows
        .filter((q) => q.decided_by && q.decided_by !== SIS_DECIDER && q.status !== 'proposed')
        .sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''))
        .slice(0, 5)))
      .catch(() => {})
  }, [])

  const maxTop = s?.top_schools?.[0]?.confirmed || 1

  return (
    <>
      <PageHead title="Dashboard">
        Transfer course equivalencies at a glance.
      </PageHead>

      {error && <p className="error">Couldn't load the dashboard: {error}</p>}

      <div className="stats">
        <div className="stat">
          <span className="stat-label">Approved equivalencies</span>
          <span className="stat-value">{s ? s.confirmed.toLocaleString() : '—'}</span>
          <span className="stat-sub">{s ? `${s.electives} count as elective credit` : ''}</span>
        </div>
        <button type="button" className="stat stat-link" onClick={() => navigate('review')}>
          <span className="stat-label">Need your review</span>
          <span className="stat-value stat-amber">{s ? s.proposed.toLocaleString() : '—'}</span>
          <span className="stat-sub">Open the review queue →</span>
        </button>
        <div className="stat">
          <span className="stat-label">Schools on file</span>
          <span className="stat-value">{s ? s.schools.toLocaleString() : '—'}</span>
          <span className="stat-sub">institutions students transfer from</span>
        </div>
        <div className="stat">
          <span className="stat-label">Flagged for a professor</span>
          <span className="stat-value">{s ? s.pending_reviews.toLocaleString() : '—'}</span>
          <span className="stat-sub">waiting on a faculty opinion</span>
        </div>
      </div>

      <div className="grid-2">
        <section className="card">
          <h2>What would you like to do?</h2>
          <div className="quick-actions">
            <button type="button" className="quick" onClick={() => navigate('lookup')}>
              <strong>Look up a transfer course</strong>
              <span>See what a course from another school counts as here.</span>
            </button>
            <button type="button" className="quick" onClick={() => navigate('review')}>
              <strong>Review ambiguous matches</strong>
              <span>Courses approved more than one way, or suggested but not yet approved.</span>
            </button>
            <button type="button" className="quick" onClick={() => navigate('library')}>
              <strong>Browse every equivalency</strong>
              <span>Search, filter by school, and download to a spreadsheet.</span>
            </button>
          </div>
        </section>

        <section className="card">
          <h2>Top transfer schools</h2>
          <p className="muted small">By number of approved equivalencies on file.</p>
          {s?.top_schools?.map((t) => (
            <div className="bar-row" key={t.name}>
              <span className="bar-name">{t.name}</span>
              <span className="bar-track"><span className="bar-fill" style={{ width: `${(t.confirmed / maxTop) * 100}%` }} /></span>
              <span className="bar-num">{t.confirmed}</span>
            </div>
          ))}
        </section>
      </div>

      <div className="grid-2">
        <section className="card">
          <h2>Recent decisions</h2>
          {recent.length === 0
            ? <p className="muted">No decisions made in Visor yet. Approve or reject something from Look Up or the Review Queue and it will show up here.</p>
            : recent.map((q) => (
              <div className="recent-row" key={q.id}>
                <div>
                  <span className="code">{q.external_course.subject} {q.external_course.number}</span>
                  {' → '}{lipscombLabel(q)}
                  <div className="muted small">{q.external_course.school} · {q.decided_by}{q.decided_at ? ` · ${q.decided_at}` : ''}</div>
                </div>
                <StatusBadge status={q.status} kind={q.kind} />
              </div>
            ))}
        </section>

        <section className="card">
          <h2>How to read a result</h2>
          <div className="legend-row"><StatusBadge status="confirmed" kind="direct" /><span>A person has approved what this course counts as.</span></div>
          <div className="legend-row"><StatusBadge status="confirmed" kind="elective" /><span>Transfers as elective hours, but doesn't satisfy a specific course.</span></div>
          <div className="legend-row"><StatusBadge status="proposed" /><span>There's a likely match, but someone needs to approve it.</span></div>
          <div className="legend-row"><StatusBadge status="unknown" /><span>Nothing on file yet. Record a decision, or flag it for a professor.</span></div>
          <p className="muted small">Visor never approves anything on its own. Every decision is saved with the name of the person who made it.</p>
        </section>
      </div>
    </>
  )
}
