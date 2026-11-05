import { useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import { PageHead, formatWhen, isStale, timeAgo } from './ui.jsx'

const PAGE = 40
const meets = (s) => (s.meetings.length
  ? s.meetings.map((m) => `${m.days} ${m.start}–${m.end}`).join(', ')
  : <span className="muted">No set meeting time</span>)

// Search a term's sections, add the ones a student is considering, and check just those for time
// conflicts. (Comparing every section in the university against every other would flag nearly all.)
export default function Schedule({ navigate }) {
  const [terms, setTerms] = useState([])
  const [term, setTerm] = useState('')
  const [sections, setSections] = useState([])
  const [query, setQuery] = useState('')
  const [shown, setShown] = useState(PAGE)
  const [picked, setPicked] = useState([])
  const [conflicts, setConflicts] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    api('/api/terms')
      .then((t) => { setTerms(t); if (t.length) setTerm(t[t.length - 1].code) })
      .catch(() => setError('Could not reach the API. Is the backend running?'))
  }, [])

  useEffect(() => {
    if (!term) return
    setPicked([]); setConflicts([]); setShown(PAGE)
    api(`/api/terms/${term}/sections`).then(setSections).catch((e) => setError(e.message))
  }, [term])

  useEffect(() => {
    if (picked.length < 2) { setConflicts([]); return }
    api(`/api/terms/${term}/conflicts?sections=${encodeURIComponent(picked.join(','))}`)
      .then(setConflicts).catch((e) => setError(e.message))
  }, [picked, term])

  const current = terms.find((t) => t.code === term) || {}
  const updatedAt = current.schedule_updated_at
  const byLabel = useMemo(() => new Map(sections.map((s) => [s.label, s])), [sections])
  const inConflict = useMemo(() => new Set(conflicts.flatMap((c) => [c.a, c.b])), [conflicts])

  const results = useMemo(() => {
    const q = query.trim().toLowerCase().replace(/\s+/g, ' ')
    if (!q) return sections
    return sections.filter((s) => `${s.label} ${s.label.replace(' ', '')} ${s.title}`.toLowerCase().includes(q))
  }, [sections, query])

  const add = (label) => setPicked((p) => (p.includes(label) ? p : [...p, label]))
  const remove = (label) => setPicked((p) => p.filter((x) => x !== label))

  return (
    <>
      <PageHead
        title="Schedule"
        actions={
          <label className="inline-field">
            Term
            <select value={term} onChange={(e) => setTerm(e.target.value)}>
              {terms.map((t) => <option key={t.code} value={t.code}>{t.name}</option>)}
            </select>
          </label>
        }
      >
        Search a term's sections and add the ones a student is considering. Visor checks those for time conflicts.
      </PageHead>

      {error && <p className="error">{error}</p>}

      {term && (
        <div className={`updated-note${updatedAt && isStale(updatedAt) ? ' stale' : ''}`}>
          <span>
            {updatedAt
              ? <>Seats and sections last updated <strong>{formatWhen(updatedAt)}</strong> ({timeAgo(updatedAt)})
                {current.schedule_file && <span className="muted"> from {current.schedule_file}</span>}</>
              : "Seats and sections haven't been updated from a schedule file yet."}
          </span>
          {navigate && <button type="button" className="btn-ghost" onClick={() => navigate('import')}>Update now</button>}
        </div>
      )}

      <section className="card">
        <h2>Student's schedule ({picked.length})</h2>
        {picked.length === 0 && <p className="muted">No sections added yet. Search below and click Add.</p>}
        {picked.map((label) => {
          const s = byLabel.get(label)
          return s && (
            <div className={`alt-row${inConflict.has(label) ? ' conflict-row' : ''}`} key={label}>
              <div className="alt-main"><span className="code">{label}</span> {s.title}
                <div className="muted small">{meets(s)}</div></div>
              <div className="row-actions">
                <button type="button" className="btn-ghost" onClick={() => remove(label)}>Remove</button>
              </div>
            </div>
          )
        })}
        {picked.length === 1 && <p className="muted small">Add one more to check for conflicts.</p>}
        {picked.length >= 2 && (conflicts.length === 0
          ? <p className="success">No time conflicts.</p>
          : (
            <ul className="conflicts">
              {conflicts.map((c) => <li key={c.a + c.b}><b>{c.a}</b> overlaps <b>{c.b}</b></li>)}
            </ul>
          ))}
      </section>

      <section className="card">
        <div className="filters">
          <input className="search" value={query} onChange={(e) => { setQuery(e.target.value); setShown(PAGE) }}
                 placeholder={`Search ${sections.length.toLocaleString()} sections by course or title, e.g. CS 1213`} />
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Section</th><th>Title</th><th>Meets</th><th>Seats</th><th /></tr></thead>
            <tbody>
              {results.slice(0, shown).map((s) => (
                <tr key={s.id} className={inConflict.has(s.label) ? 'conflict' : ''}>
                  <td className="nowrap"><span className="code">{s.label}</span></td>
                  <td>{s.title}</td>
                  <td>{meets(s)}</td>
                  <td className="nowrap">
                    {s.enrolled}/{s.capacity}
                    {s.full && <span className="badge badge-unknown">full</span>}
                  </td>
                  <td>
                    <button type="button" className="btn-ghost" disabled={picked.includes(s.label)}
                            onClick={() => add(s.label)}>{picked.includes(s.label) ? 'Added' : 'Add'}</button>
                  </td>
                </tr>
              ))}
              {results.length === 0 && <tr><td colSpan={5} className="muted">No sections match.</td></tr>}
            </tbody>
          </table>
        </div>
        {results.length > shown && (
          <div className="more">
            <span className="muted small">Showing {shown} of {results.length.toLocaleString()}</span>
            <button type="button" className="btn-ghost" onClick={() => setShown(shown + PAGE)}>Show more</button>
          </div>
        )}
      </section>
    </>
  )
}
