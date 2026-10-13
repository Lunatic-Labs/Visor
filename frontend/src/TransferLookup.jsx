import { useEffect, useState } from 'react'

// Bare-bones UI for the transfer-equivalency API (KAN-38). Pick a school, enter the course
// the student took there, and see whether we already have a confirmed/proposed Lipscomb
// equivalent or whether it's unknown and needs the registrar's eyes on it.
export default function TransferLookup() {
  const [schools, setSchools] = useState([])
  const [schoolId, setSchoolId] = useState('')
  const [subject, setSubject] = useState('')
  const [number, setNumber] = useState('')
  const [title, setTitle] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch('/api/schools')
      .then((r) => r.json())
      .then((s) => { setSchools(s); if (s.length) setSchoolId(String(s[0].id)) })
      .catch(() => setError('Could not reach the API. Is the backend running?'))
  }, [])

  async function lookup(e) {
    e.preventDefault()
    setError('')
    setResult(null)
    if (!schoolId || !subject.trim() || !number.trim()) {
      setError('School, subject, and course number are required.')
      return
    }
    setLoading(true)
    try {
      const r = await fetch('/api/equivalencies/lookup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          school_id: Number(schoolId),
          subject: subject.trim(),
          number: number.trim(),
          title: title.trim(),
        }),
      })
      if (!r.ok) throw new Error((await r.json()).error || 'Lookup failed')
      setResult(await r.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <p className="hint">
        Look up whether a transfer course already has a Lipscomb equivalent. This is a first
        pass at the UI — layout and what fields the registrar actually wants are still TBD
        pending a meeting with her.
      </p>

      <form onSubmit={lookup} className="lookup-form">
        <label>
          School{' '}
          <select value={schoolId} onChange={(e) => setSchoolId(e.target.value)}>
            {schools.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
        <label>
          Subject{' '}
          <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="CS" />
        </label>
        <label>
          Number{' '}
          <input value={number} onChange={(e) => setNumber(e.target.value)} placeholder="1113" />
        </label>
        <label>
          Title (optional){' '}
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Intro to Programming" />
        </label>
        <button type="submit" disabled={loading}>{loading ? 'Looking up…' : 'Look up'}</button>
      </form>

      {error && <p className="error">{error}</p>}

      {result && (
        <section className={`lookup-result status-${result.status}`}>
          <h2>Result: {result.status}</h2>
          <p>
            {result.external_course.school} — {result.external_course.subject} {result.external_course.number}
            {result.external_course.title ? ` (${result.external_course.title})` : ''}
          </p>

          {result.status === 'confirmed' && result.equivalency.course && (
            <p>Equivalent to <b>{result.equivalency.course.code}</b> — {result.equivalency.course.title}
              {result.equivalency.decided_by ? ` (confirmed by ${result.equivalency.decided_by})` : ''}</p>
          )}

          {result.status === 'proposed' && result.candidates.length > 0 && (
            <>
              <p>No confirmed mapping yet. Candidates:</p>
              <ul>
                {result.candidates.map((c, i) => (
                  <li key={i}>{c.course?.code} — {c.course?.title} {c.why ? `(${c.why})` : ''}</li>
                ))}
              </ul>
            </>
          )}

          {result.status === 'unknown' && (
            <p>No existing mapping. This would need to be flagged for the registrar / a
              department professor to weigh in on.</p>
          )}
        </section>
      )}
    </>
  )
}
