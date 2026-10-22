import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import { PageHead, StatusBadge, lipscombLabel } from './ui.jsx'

const PAGE = 15

// Every external course with at least one proposed row, with what it currently counts as.
// Most come from the SIS export: courses approved as more than one Lipscomb course, where the
// most-used one was stored as approved and the rest wait here for the registrar to settle.
export default function ReviewQueue({ actor, onChange }) {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [school, setSchool] = useState('')
  const [query, setQuery] = useState('')
  const [reviewer, setReviewer] = useState('')
  const [shown, setShown] = useState(PAGE)

  const load = useCallback(() => api('/api/equivalencies').then(setRows).catch((e) => setError(e.message)), [])
  useEffect(() => { load() }, [load])

  const groups = useMemo(() => {
    const byExt = new Map()
    for (const q of rows || []) {
      const id = q.external_course.id
      if (!byExt.has(id)) byExt.set(id, { ext: q.external_course, current: null, alternates: [] })
      const g = byExt.get(id)
      if (q.status === 'confirmed') g.current = q
      else if (q.status === 'proposed') g.alternates.push(q)
    }
    return [...byExt.values()]
      .filter((g) => g.alternates.length)
      .map((g) => ({ ...g, alternates: g.alternates.sort((a, b) => (b.confidence || 0) - (a.confidence || 0)) }))
      .sort((a, b) => a.ext.school.localeCompare(b.ext.school) || a.ext.subject.localeCompare(b.ext.subject)
        || a.ext.number.localeCompare(b.ext.number))
  }, [rows])

  const schools = useMemo(() => [...new Set(groups.map((g) => g.ext.school))].sort(), [groups])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return groups.filter((g) => (!school || g.ext.school === school) && (!q
      || `${g.ext.subject} ${g.ext.number} ${g.ext.subject}${g.ext.number} ${g.ext.title}`.toLowerCase().includes(q)))
  }, [groups, school, query])

  async function run(request, done) {
    setError(''); setMessage('')
    setBusy(true)
    try {
      await request()
      await load()
      onChange?.()
      setMessage(done)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  function needName() {
    if (actor.trim()) return false
    setError('Enter your name in the top-right corner first, so the decision is saved under it.')
    return true
  }

  const approve = (q) => !needName() && run(
    () => api(`/api/equivalencies/${q.id}/make-primary`, { method: 'POST', body: { decided_by: actor.trim() } }),
    `${lipscombLabel(q)} is now the approved match.`)

  const dismiss = (q) => !needName() && run(
    () => api(`/api/equivalencies/${q.id}`, { method: 'PUT', body: { status: 'rejected', decided_by: actor.trim() } }),
    `Dismissed ${lipscombLabel(q)}.`)

  function flag(q) {
    if (!reviewer.trim()) { setError('Enter a professor or department to flag it to (above the list).'); return }
    run(() => api(`/api/equivalencies/${q.id}/flag`, {
      method: 'POST', body: { reviewer: reviewer.trim(), requested_by: actor.trim() || 'registrar' },
    }), `Flagged for ${reviewer.trim()}.`)
  }

  return (
    <>
      <PageHead title="Review queue">
        Courses with more than one possible Lipscomb equivalent, or a suggested match nobody has approved yet.
        Pick the right one, dismiss the wrong ones, or ask a professor.
      </PageHead>

      <div className="filters">
        <input className="search" value={query} onChange={(e) => { setQuery(e.target.value); setShown(PAGE) }}
               placeholder="Search by course, e.g. ENG 100" />
        <select value={school} onChange={(e) => { setSchool(e.target.value); setShown(PAGE) }}>
          <option value="">All schools ({groups.length})</option>
          {schools.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <input value={reviewer} onChange={(e) => setReviewer(e.target.value)}
               placeholder="Professor to flag to (optional)" />
      </div>

      {error && <p className="error banner">{error}</p>}
      {message && !error && <p className="success banner">{message}</p>}

      {rows === null && !error && <p className="muted">Loading…</p>}
      {rows && filtered.length === 0 && (
        <section className="card empty">
          <h2>Nothing to review</h2>
          <p className="muted">{groups.length ? 'No courses match that search.' : 'Every equivalency on file has a single approved match.'}</p>
        </section>
      )}

      {filtered.slice(0, shown).map((g) => (
        <section className="card queue-card" key={g.ext.id}>
          <div className="queue-head">
            <div>
              <span className="code">{g.ext.subject} {g.ext.number}</span> <strong>{g.ext.title}</strong>
              <div className="muted small">{g.ext.school}{g.ext.credits ? ` · ${g.ext.credits} hrs` : ''}</div>
            </div>
          </div>

          <div className="current">
            {g.current
              ? <>Currently counts as <strong>{lipscombLabel(g.current)}</strong> <StatusBadge status="confirmed" kind={g.current.kind} /></>
              : <span className="muted">No approved match yet.</span>}
          </div>

          {g.alternates.map((q) => {
            const open = q.kind === 'direct' && !q.course
            return (
            <div className="alt-row" key={q.id}>
              <div className="alt-main">
                <div>{open ? 'Needs an answer' : g.current ? 'Also approved as ' : 'Suggested: '}
                  {!open && <strong>{lipscombLabel(q)}</strong>}
                  {q.pending_reviews > 0 && <span className="badge badge-elective">flagged for a professor</span>}
                </div>
                {q.notes && <div className="muted small">{q.notes}</div>}
                {open && <div className="muted small">Record what it counts as from Look Up once you know.</div>}
              </div>
              <div className="row-actions">
                {!open && (
                  <button type="button" className="btn-primary" disabled={busy} onClick={() => approve(q)}>
                    {g.current ? 'Use this instead' : 'Approve'}
                  </button>
                )}
                <button type="button" className="btn-danger" disabled={busy} onClick={() => dismiss(q)}>Dismiss</button>
                <button type="button" className="btn-ghost" disabled={busy} onClick={() => flag(q)}>Flag</button>
              </div>
            </div>
            )
          })}
        </section>
      ))}

      {filtered.length > shown && (
        <div className="more">
          <span className="muted small">Showing {shown} of {filtered.length}</span>
          <button type="button" className="btn-ghost" onClick={() => setShown(shown + PAGE)}>Show more</button>
        </div>
      )}
    </>
  )
}
