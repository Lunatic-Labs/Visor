import { useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import { CourseList, CoursePicker, lipscombLabel, splitCode } from './ui.jsx'

// Record an equivalency by hand: a course from any school (added to Visor if it isn't there yet)
// and what it counts as at Lipscomb. Saved as approved under the name in the top bar, so the next
// lookup of that course comes back approved.
export default function AddEquivalency({ actor, onSaved, onCancel }) {
  const [schools, setSchools] = useState([])
  const [courses, setCourses] = useState([])
  const [schoolName, setSchoolName] = useState('')
  const [state, setState] = useState('')
  const [code, setCode] = useState('')
  const [title, setTitle] = useState('')
  const [credits, setCredits] = useState('')
  const [kind, setKind] = useState('direct')
  const [courseId, setCourseId] = useState('')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api('/api/schools').then(setSchools).catch((e) => setError(e.message))
    api('/api/courses').then(setCourses).catch((e) => setError(e.message))
  }, [])

  const existing = useMemo(
    () => schools.find((s) => s.name.toLowerCase() === schoolName.trim().replace(/\s+/g, ' ').toLowerCase()),
    [schools, schoolName])
  const isNewSchool = schoolName.trim() && !existing

  async function save(e) {
    e.preventDefault()
    setError('')
    const [subject, number] = splitCode(code) || []
    if (!actor.trim()) { setError('Enter your name in the top-right corner first, so the decision is saved under it.'); return }
    if (!schoolName.trim()) { setError('Enter the school the course is from.'); return }
    if (!subject || !number) { setError('Enter the course code as it appears on the transcript, e.g. MATH 1910.'); return }
    if (credits.trim() && !/^\d{1,2}$/.test(credits.trim())) { setError('Credit hours must be a whole number.'); return }
    if (kind === 'direct' && !courseId) { setError('Pick the Lipscomb course it counts as.'); return }

    setBusy(true)
    try {
      const school = existing
        || await api('/api/schools', { method: 'POST', body: { name: schoolName.trim(), state: state.trim() } })
      const found = await api('/api/equivalencies/lookup', {
        method: 'POST',
        body: { school_id: school.id, subject, number, title: title.trim(), credits: credits.trim() || null },
      })
      const label = `${school.name} ${found.external_course.subject} ${found.external_course.number}`
      if (found.status === 'confirmed') {
        setError(`${label} is already on file: it counts as ${lipscombLabel(found.equivalency)}. `
          + 'Use Look Up or the Review Queue to change it.')
        return
      }
      const decision = {
        kind,
        course_id: kind === 'direct' ? Number(courseId) : null,
        status: 'confirmed',
        decided_by: actor.trim(),
        ...(notes.trim() && { notes: notes.trim() }),
      }
      const eq = found.equivalency
      const placeholder = eq && eq.status === 'proposed' && eq.kind === 'direct' && !eq.course
      const saved = placeholder
        ? await api(`/api/equivalencies/${eq.id}`, { method: 'PUT', body: decision })
        : await api('/api/equivalencies', { method: 'POST', body: { ...decision, external_course_id: found.external_course.id } })
      onSaved(`Saved. ${label} now counts as ${lipscombLabel(saved)}${isNewSchool ? `, and ${school.name} was added to Visor` : ''}.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <h2>Add an equivalency</h2>
      <p className="muted small">
        For a course that isn't in Visor yet, from any school. It's saved as approved under your name, so the
        next time anyone looks it up it comes back approved.
      </p>
      <form onSubmit={save}>
        <div className="lookup-form">
          <label className="grow">
            School
            <input list="visor-add-schools" value={schoolName} onChange={(e) => setSchoolName(e.target.value)}
                   placeholder="Start typing, e.g. University of Tennessee" />
            <datalist id="visor-add-schools">{schools.map((s) => <option key={s.id} value={s.name} />)}</datalist>
          </label>
          {isNewSchool && (
            <label>
              State (optional)
              <input value={state} onChange={(e) => setState(e.target.value)} placeholder="TN" maxLength={2} size={4} />
            </label>
          )}
        </div>
        {isNewSchool && (
          <p className="hint small">
            "{schoolName.trim()}" isn't in Visor yet. It will be added. Check the list first in case it's there
            under a slightly different name.
          </p>
        )}
        <div className="lookup-form">
          <label>
            Course code
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="MATH 1910" />
          </label>
          <label className="grow">
            Title
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Calculus I" />
          </label>
          <label>
            Credit hours (optional)
            <input value={credits} onChange={(e) => setCredits(e.target.value)} placeholder="4" size={4} />
          </label>
        </div>
        <div className="lookup-form">
          <label>
            It counts as
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="direct">a specific Lipscomb course</option>
              <option value="elective">general elective credit</option>
              <option value="none">no credit (doesn't transfer)</option>
            </select>
          </label>
          {kind === 'direct' && (
            <label className="grow">
              Lipscomb course
              <CoursePicker courses={courses} onChange={setCourseId} placeholder="Start typing, e.g. MA 1314" />
            </label>
          )}
        </div>
        <CourseList courses={courses} />
        <div className="lookup-form">
          <label className="grow">
            Who approved it, and how (optional)
            <input value={notes} onChange={(e) => setNotes(e.target.value)}
                   placeholder="e.g. Math department approved by email, 11/3" />
          </label>
          <button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save as approved'}</button>
          <button type="button" className="btn-ghost" onClick={onCancel} disabled={busy}>Cancel</button>
        </div>
        {error && <p className="error">{error}</p>}
      </form>
    </section>
  )
}
