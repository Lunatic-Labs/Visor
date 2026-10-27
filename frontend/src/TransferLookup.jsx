import { useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import { PageHead, StatusBadge, lipscombLabel } from './ui.jsx'

// "ENG 100", "ENG100", "eng-100" -> ["ENG", "100"]; same split the SIS importer uses.
function splitCode(code) {
  const m = code.trim().toUpperCase().replace(/\s+/g, ' ').match(/^([A-Z]+)[\s-]*(.+)$/)
  return m ? [m[1], m[2].trim()] : null
}

// Look up what a transfer course counts as, and act on the answer. Nothing confirms itself:
// every approve/reject is saved under the name entered in the top bar.
export default function TransferLookup({ actor, onChange }) {
  const [schools, setSchools] = useState([])
  const [courses, setCourses] = useState([])
  const [schoolName, setSchoolName] = useState('')
  const [code, setCode] = useState('')
  const [title, setTitle] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [reviewer, setReviewer] = useState('')
  const [manualKind, setManualKind] = useState('direct')
  const [manualCourseId, setManualCourseId] = useState('')
  const [manualNotes, setManualNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    api('/api/schools').then(setSchools).catch(() => setError('Could not reach Visor. Is the backend running?'))
    api('/api/courses').then(setCourses).catch(() => {})
  }, [])

  const school = useMemo(() => schools.find((s) => s.name.toLowerCase() === schoolName.trim().toLowerCase()),
    [schools, schoolName])
  const [subject, number] = splitCode(code) || []

  async function runLookup() {
    return api('/api/equivalencies/lookup', {
      method: 'POST', body: { school_id: school.id, subject, number, title: title.trim() },
    })
  }

  async function lookup(e) {
    e.preventDefault()
    setError(''); setActionError(''); setMessage(''); setResult(null)
    if (!school) { setError('Pick a school from the list (start typing its name).'); return }
    if (!subject || !number) { setError('Enter the course code as it appears on the transcript, e.g. ENG 100.'); return }
    setLoading(true)
    try {
      setResult(await runLookup())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function act(request, done) {
    setActionError(''); setMessage('')
    setBusy(true)
    try {
      await request()
      setResult(await runLookup())
      onChange?.()
      setMessage(done)
    } catch (err) {
      setActionError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function needName() {
    if (actor.trim()) return false
    setActionError('Enter your name in the top-right corner first, so the decision is saved under it.')
    return true
  }

  const approve = (q) => !needName() && act(
    () => api(`/api/equivalencies/${q.id}/make-primary`, { method: 'POST', body: { decided_by: actor.trim() } }),
    'Approved.')

  const reject = (q) => !needName() && act(
    () => api(`/api/equivalencies/${q.id}`, { method: 'PUT', body: { status: 'rejected', decided_by: actor.trim() } }),
    'Rejected.')

  function flag(q) {
    if (!reviewer.trim()) { setActionError('Enter who should review it, below.'); return }
    act(() => api(`/api/equivalencies/${q.id}/flag`, {
      method: 'POST', body: { reviewer: reviewer.trim(), requested_by: actor.trim() || 'registrar' },
    }), `Flagged for ${reviewer.trim()}.`)
  }

  const ext = result?.external_course
  const eq = result?.equivalency
  // A proposed row with no course is a placeholder made by flagging an unknown course.
  const placeholder = eq && eq.status === 'proposed' && eq.kind === 'direct' && !eq.course ? eq : null
  const needsAnswer = result && (result.status === 'unknown' || (result.status === 'proposed' && !result.candidates.length))

  function record() {
    if (needName()) return
    if (manualKind === 'direct' && !manualCourseId) { setActionError('Pick the Lipscomb course it counts as.'); return }
    const body = {
      kind: manualKind,
      course_id: manualKind === 'direct' ? Number(manualCourseId) : null,
      status: 'confirmed',
      decided_by: actor.trim(),
      ...(manualNotes.trim() && { notes: manualNotes.trim() }),
    }
    act(() => (placeholder
      ? api(`/api/equivalencies/${placeholder.id}`, { method: 'PUT', body })
      : api('/api/equivalencies', { method: 'POST', body: { ...body, external_course_id: ext.id } })),
    'Saved. The next time anyone looks this course up, it will come back approved.')
  }

  function flagUnknown() {
    if (!reviewer.trim()) { setActionError('Enter who should review it first.'); return }
    act(async () => {
      const row = placeholder || await api('/api/equivalencies', {
        method: 'POST',
        body: { external_course_id: ext.id, kind: 'direct', course_id: null, status: 'proposed',
          notes: 'No match on file; flagged from Look Up' },
      })
      return api(`/api/equivalencies/${row.id}/flag`, {
        method: 'POST', body: { reviewer: reviewer.trim(), requested_by: actor.trim() || 'registrar' },
      })
    }, `Flagged for ${reviewer.trim()}. It's in the review queue until someone records the answer.`)
  }

  return (
    <>
      <PageHead title="Look up a transfer course">
        Enter the school and course code from the student's transcript to see what it counts as at Lipscomb.
      </PageHead>

      <section className="card">
        <form onSubmit={lookup} className="lookup-form">
          <label className="grow">
            School
            <input list="visor-schools" value={schoolName} onChange={(e) => setSchoolName(e.target.value)}
                   placeholder={`Start typing… (${schools.length} schools)`} />
            <datalist id="visor-schools">
              {schools.map((s) => <option key={s.id} value={s.name} />)}
            </datalist>
          </label>
          <label>
            Course code
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="ENG 100" />
          </label>
          <label>
            Title (optional)
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Freshman English" />
          </label>
          <button type="submit" disabled={loading}>{loading ? 'Looking up…' : 'Look up'}</button>
        </form>
        {error && <p className="error">{error}</p>}
      </section>

      {result && (
        <section className={`lookup-result status-${result.status}`}>
          <div className="result-head">
            <div>
              <span className="code">{ext.subject} {ext.number}</span> <strong>{ext.title}</strong>
              <div className="muted small">{ext.school}{ext.credits ? ` · ${ext.credits} hrs` : ''}</div>
            </div>
            {eq ? <StatusBadge status={result.status} kind={eq.kind} /> : <StatusBadge status={result.status} />}
          </div>

          {result.status === 'confirmed' && (
            <>
              <div className="answer">
                <span className="muted small">Counts at Lipscomb as</span>
                <div className="answer-main">
                  {eq.kind === 'direct' && eq.course
                    ? <><span className="code">{eq.course.code}</span> {eq.course.title} · {eq.course.credits} hrs</>
                    : lipscombLabel(eq)}
                </div>
                <div className="muted small">
                  Approved by {eq.decided_by || 'unknown'}{eq.decided_at ? ` on ${eq.decided_at}` : ''}
                </div>
                {eq.notes && <div className="note">{eq.notes}</div>}
              </div>

              {result.alternates?.length > 0 && (
                <div className="alternates">
                  <p><strong>Also approved as</strong> <span className="muted small">(the SIS has more than one approval for this course)</span></p>
                  {result.alternates.map((q) => (
                    <div className="alt-row" key={q.id}>
                      <div className="alt-main">
                        <strong>{lipscombLabel(q)}</strong>
                        {q.notes && <div className="muted small">{q.notes}</div>}
                      </div>
                      <div className="row-actions">
                        <button type="button" className="btn-ghost" disabled={busy} onClick={() => approve(q)}>Use this instead</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {result.status === 'proposed' && result.candidates.length > 0 && (
            <>
              <p>There's a likely match, but nobody has approved it yet.</p>
              {result.candidates.map((c) => (
                <div className="alt-row" key={c.id}>
                  <div className="alt-main">
                    <strong>{c.course?.code} — {c.course?.title}</strong>
                    {c.why && <div className="muted small">{c.why}</div>}
                  </div>
                  <div className="row-actions">
                    <button type="button" className="btn-primary" disabled={busy} onClick={() => approve(c)}>Approve</button>
                    <button type="button" className="btn-danger" disabled={busy} onClick={() => reject(c)}>Reject</button>
                    <button type="button" className="btn-ghost" disabled={busy} onClick={() => flag(c)}>Flag for a professor</button>
                  </div>
                </div>
              ))}
              <div className="actor-fields">
                <label>Professor or department to flag to
                  <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="e.g. Dr. Nordstrom" />
                </label>
              </div>
            </>
          )}

          {needsAnswer && (
            <>
              {placeholder
                ? <p>No answer on file yet{placeholder.pending_reviews
                  ? ` — flagged for a professor (${placeholder.pending_reviews} waiting)` : ''}. Record it once you know.</p>
                : <p>This course isn't on file yet. If you know what it counts as, record it now and it will be
                  approved for every future student.</p>}
              <div className="lookup-form">
                <label>
                  It counts as
                  <select value={manualKind} onChange={(e) => setManualKind(e.target.value)}>
                    <option value="direct">a specific Lipscomb course</option>
                    <option value="elective">general elective credit</option>
                    <option value="none">no credit (doesn't transfer)</option>
                  </select>
                </label>
                {manualKind === 'direct' && (
                  <label className="grow">
                    Lipscomb course
                    <select value={manualCourseId} onChange={(e) => setManualCourseId(e.target.value)}>
                      <option value="">Pick a course…</option>
                      {courses.map((c) => <option key={c.id} value={c.id}>{c.code} — {c.title}</option>)}
                    </select>
                  </label>
                )}
                <label className="grow">
                  Who approved it, and how (optional)
                  <input value={manualNotes} onChange={(e) => setManualNotes(e.target.value)}
                         placeholder="e.g. Dr. Nordstrom approved by email, 10/22" />
                </label>
                <button type="button" disabled={busy} onClick={record}>Save as approved</button>
              </div>
              <p className="muted small">Not sure? Flag it for a professor instead. Visor won't guess for you.</p>
              <div className="lookup-form">
                <label className="grow">
                  Professor or department
                  <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="e.g. Dr. Nordstrom" />
                </label>
                <button type="button" className="btn-ghost" disabled={busy} onClick={flagUnknown}>Flag for a professor</button>
              </div>
            </>
          )}

          {actionError && <p className="error">{actionError}</p>}
          {message && !actionError && <p className="success">{message}</p>}
        </section>
      )}
    </>
  )
}
