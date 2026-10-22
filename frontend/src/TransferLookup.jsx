import { useEffect, useState } from 'react'

// Look up whether a transfer course already has a Lipscomb equivalent (KAN-38 API), and act on
// what comes back: confirm or reject a proposed match, flag something for a professor to weigh
// in on, or record a brand-new mapping when nothing exists yet. Nothing here auto-confirms
// anything -- every confirm/reject is attributed to whoever typed their name in "Your name".
export default function TransferLookup() {
  const [schools, setSchools] = useState([])
  const [courses, setCourses] = useState([])
  const [schoolId, setSchoolId] = useState('')
  const [subject, setSubject] = useState('')
  const [number, setNumber] = useState('')
  const [title, setTitle] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [actor, setActor] = useState('')
  const [reviewer, setReviewer] = useState('')
  const [manualKind, setManualKind] = useState('direct')
  const [manualCourseId, setManualCourseId] = useState('')
  const [actionBusy, setActionBusy] = useState(false)
  const [actionError, setActionError] = useState('')
  const [actionNote, setActionNote] = useState('')

  useEffect(() => {
    fetch('/api/schools')
      .then((r) => r.json())
      .then((s) => { setSchools(s); if (s.length) setSchoolId(String(s[0].id)) })
      .catch(() => setError('Could not reach the API. Is the backend running?'))
    fetch('/api/courses').then((r) => r.json()).then(setCourses).catch(() => {})
  }, [])

  async function runLookup() {
    const r = await fetch('/api/equivalencies/lookup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        school_id: Number(schoolId), subject: subject.trim(), number: number.trim(), title: title.trim(),
      }),
    })
    if (!r.ok) throw new Error((await r.json()).error || 'Lookup failed')
    return r.json()
  }

  async function lookup(e) {
    e.preventDefault()
    setError(''); setActionError(''); setActionNote(''); setResult(null)
    if (!schoolId || !subject.trim() || !number.trim()) {
      setError('School, subject, and course number are required.')
      return
    }
    setLoading(true)
    try {
      setResult(await runLookup())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Shared by confirm/reject/flag/create: run the API call, then refresh the lookup so the
  // screen reflects what's actually saved instead of guessing at the new state locally.
  async function act(request) {
    setActionError(''); setActionNote('')
    setActionBusy(true)
    try {
      const r = await request()
      if (!r.ok) throw new Error((await r.json()).error || 'That didn\'t save.')
      setResult(await runLookup())
      setActionNote('Saved.')
    } catch (err) {
      setActionError(err.message)
    } finally {
      setActionBusy(false)
    }
  }

  function decide(id, status) {
    if (!actor.trim()) { setActionError('Enter your name first.'); return }
    act(() => fetch(`/api/equivalencies/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, decided_by: actor.trim() }),
    }))
  }

  function flag(id) {
    if (!reviewer.trim()) { setActionError('Enter who should review it first.'); return }
    act(() => fetch(`/api/equivalencies/${id}/flag`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reviewer: reviewer.trim(), requested_by: actor.trim() || 'registrar' }),
    }))
  }

  function createManual() {
    if (!actor.trim()) { setActionError('Enter your name first.'); return }
    if (manualKind === 'direct' && !manualCourseId) { setActionError('Pick the Lipscomb course it counts as.'); return }
    act(() => fetch('/api/equivalencies', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        external_course_id: result.external_course.id,
        kind: manualKind,
        course_id: manualKind === 'direct' ? Number(manualCourseId) : null,
        status: 'confirmed',
        decided_by: actor.trim(),
      }),
    }))
  }

  return (
    <>
      <p className="hint">
        Look up whether a transfer course already has a Lipscomb equivalent, and confirm, reject,
        flag, or record a mapping right here. Every decision is saved under whoever's name is
        entered below — nothing confirms itself.
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
          <h2>Result <span className={`badge badge-${result.status}`}>{result.status}</span></h2>
          <p>
            {result.external_course.school} — {result.external_course.subject} {result.external_course.number}
            {result.external_course.title ? ` (${result.external_course.title})` : ''}
          </p>

          {result.status === 'confirmed' && (
            <p>
              {result.equivalency.kind === 'direct' && result.equivalency.course
                ? <>Equivalent to <b>{result.equivalency.course.code}</b> — {result.equivalency.course.title}</>
                : result.equivalency.kind === 'elective'
                  ? 'Counts as general elective credit.'
                  : 'This course does not transfer.'}
              {result.equivalency.decided_by ? ` (confirmed by ${result.equivalency.decided_by})` : ''}
            </p>
          )}

          {result.status === 'proposed' && result.candidates.length > 0 && (
            <>
              <p>No confirmed mapping yet. Candidates:</p>
              <div>
                {result.candidates.map((c) => (
                  <div className="candidate-row" key={c.id}>
                    <span>{c.course?.code} — {c.course?.title} {c.why ? `(${c.why})` : ''}</span>
                    <span className="candidate-actions">
                      <button type="button" className="btn-primary" disabled={actionBusy}
                             onClick={() => decide(c.id, 'confirmed')}>
                        Confirm this match
                      </button>
                      <button type="button" className="btn-danger" disabled={actionBusy}
                             onClick={() => decide(c.id, 'rejected')}>
                        Reject
                      </button>
                      <button type="button" className="btn-ghost" disabled={actionBusy} onClick={() => flag(c.id)}>
                        Flag for a professor
                      </button>
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}

          {result.status === 'unknown' && (
            <>
              <p>No existing mapping yet. Record one now, or flag it for a professor to weigh in on.</p>
              <div className="card-form lookup-form">
                <label>
                  This counts as
                  <select value={manualKind} onChange={(e) => setManualKind(e.target.value)}>
                    <option value="direct">a specific Lipscomb course</option>
                    <option value="elective">general elective credit</option>
                    <option value="none">it doesn't transfer</option>
                  </select>
                </label>
                {manualKind === 'direct' && (
                  <label>
                    Lipscomb course
                    <select value={manualCourseId} onChange={(e) => setManualCourseId(e.target.value)}>
                      <option value="">Pick a course…</option>
                      {courses.map((c) => <option key={c.id} value={c.id}>{c.code} — {c.title}</option>)}
                    </select>
                  </label>
                )}
                <button type="button" className="btn-primary" disabled={actionBusy} onClick={createManual}>
                  Save as confirmed
                </button>
              </div>
            </>
          )}

          {(result.status === 'proposed' || result.status === 'unknown') && (
            <div className="actor-fields">
              <label>Your name
                <input value={actor} onChange={(e) => setActor(e.target.value)} placeholder="required to confirm/reject" />
              </label>
              <label>Reviewer (for flagging)
                <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="professor or department" />
              </label>
            </div>
          )}

          {actionError && <p className="error">{actionError}</p>}
          {actionNote && !actionError && <p>{actionNote}</p>}
        </section>
      )}
    </>
  )
}
