import { useState } from 'react'

// Bare-bones UI for the prereq-check endpoint, which is already live on the backend.
export default function PrereqCheck() {
  const [subject, setSubject] = useState('')
  const [number, setNumber] = useState('')
  const [completed, setCompleted] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function check(e) {
    e.preventDefault()
    setError('')
    setResult(null)
    if (!subject.trim() || !number.trim()) {
      setError('Subject and course number are required.')
      return
    }
    try {
      const normalizedCompleted = completed
        .split(',')
        .map((course) => course.trim().toUpperCase())
        .filter(Boolean)
        .join(',')
      const params = new URLSearchParams({ completed: normalizedCompleted })
      const courseSubject = encodeURIComponent(subject.trim().toUpperCase())
      const courseNumber = encodeURIComponent(number.trim().toUpperCase())
      const r = await fetch(`/api/courses/${courseSubject}/${courseNumber}/prereq-check?${params}`)
      if (!r.ok) throw new Error('Course not found')
      setResult(await r.json())
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <p className="hint">Check whether a student has the prerequisites for a course.</p>

      <form onSubmit={check} className="lookup-form">
        <label>
          Subject{' '}
          <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="CS" />
        </label>
        <label>
          Number{' '}
          <input value={number} onChange={(e) => setNumber(e.target.value)} placeholder="3233" />
        </label>
        <label>
          Completed courses (comma-separated){' '}
          <input value={completed} onChange={(e) => setCompleted(e.target.value)} placeholder="CS 1113, MA 1314" />
        </label>
        <button type="submit">Check</button>
      </form>

      {error && <p className="error">{error}</p>}

      {result && (
        <section>
          <h2>{result.course}</h2>
          {result.missing.length === 0
            ? <p>All prerequisites met.</p>
            : (
              <>
                <p>Missing at least one course from each of these groups:</p>
                <ul>
                  {result.missing.map((group, i) => <li key={i}>{group.join(' or ')}</li>)}
                </ul>
              </>
            )}
        </section>
      )}
    </>
  )
}
