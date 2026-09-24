import { useEffect, useMemo, useState } from 'react'

// Scaffold screen: pick a term, see its sections, and see which ones conflict.
export default function App() {
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
    <main>
      <header>
        <h1>Visor</h1>
        <label>
          Term{' '}
          <select value={term} onChange={(e) => setTerm(e.target.value)}>
            {terms.map((t) => <option key={t.code} value={t.code}>{t.name}</option>)}
          </select>
        </label>
      </header>

      {error && <p className="error">{error}</p>}

      <section>
        <h2>Time conflicts ({conflicts.length})</h2>
        {conflicts.length === 0 ? <p>None found.</p> : (
          <ul className="conflicts">
            {conflicts.map((c) => <li key={c.a + c.b}><b>{c.a}</b> overlaps <b>{c.b}</b></li>)}
          </ul>
        )}
      </section>

      <section>
        <h2>Sections</h2>
        <table>
          <thead><tr><th>Section</th><th>Title</th><th>Meets</th><th>Seats</th></tr></thead>
          <tbody>
            {sections.map((s) => (
              <tr key={s.id} className={inConflict.has(s.label) ? 'conflict' : ''}>
                <td>{s.label}</td>
                <td>{s.title}</td>
                <td>{s.meetings.map((m) => `${m.days} ${m.start}–${m.end}`).join(', ')}</td>
                <td className={s.full ? 'full' : ''}>{s.enrolled}/{s.capacity}{s.full ? ' (full)' : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  )
}
