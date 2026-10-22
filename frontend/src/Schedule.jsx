import { useEffect, useMemo, useState } from 'react'
import { PageHead } from './ui.jsx'

// Scaffold screen: pick a term, see its sections, and see which ones conflict.
export default function Schedule() {
  const [terms, setTerms] = useState([])
  const [term, setTerm] = useState('')
  const [sections, setSections] = useState([])
  const [conflicts, setConflicts] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/terms')
      .then((r) => r.json())
      .then((t) => { setTerms(t); if (t.length) setTerm(t[t.length - 1].code) })
      .catch(() => setError('Could not reach the API. Is the backend running?'))
  }, [])

  useEffect(() => {
    if (!term) return
    Promise.all([
      fetch(`/api/terms/${term}/sections`).then((r) => r.json()),
      fetch(`/api/terms/${term}/conflicts`).then((r) => r.json()),
    ]).then(([s, c]) => { setSections(s); setConflicts(c) })
  }, [term])

  const inConflict = useMemo(
    () => new Set(conflicts.flatMap((c) => [c.a, c.b])),
    [conflicts],
  )

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
        Every section in a term, with time conflicts and full sections highlighted. Sample schedule data for
        now, until we have the real section list.
      </PageHead>

      {error && <p className="error">{error}</p>}

      <section className="card">
        <h2>Time conflicts ({conflicts.length})</h2>
        {conflicts.length === 0 ? <p>None found.</p> : (
          <ul className="conflicts">
            {conflicts.map((c) => <li key={c.a + c.b}><b>{c.a}</b> overlaps <b>{c.b}</b></li>)}
          </ul>
        )}
      </section>

      <section className="card">
        <h2>Sections</h2>
        <table>
          <thead><tr><th>Section</th><th>Title</th><th>Meets</th><th>Seats</th></tr></thead>
          <tbody>
            {sections.map((s) => (
              <tr key={s.id} className={inConflict.has(s.label) ? 'conflict' : ''}>
                <td>{s.label}</td>
                <td>{s.title}</td>
                <td>{s.meetings.map((m) => `${m.days} ${m.start}–${m.end}`).join(', ')}</td>
                <td>
                  {s.enrolled}/{s.capacity}
                  {s.full && <span className="badge badge-unknown">full</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  )
}
