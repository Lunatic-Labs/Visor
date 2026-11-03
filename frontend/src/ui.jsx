import { useState } from 'react'

// "Tue, Nov 3, 12:15 PM" in the viewer's own timezone (the API sends UTC).
export function formatWhen(iso) {
  const d = new Date(iso)
  const opts = { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }
  if (d.getFullYear() !== new Date().getFullYear()) opts.year = 'numeric'
  return d.toLocaleString([], opts)
}

export function timeAgo(iso) {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000))
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.round(hours / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

export const isStale = (iso) => Date.now() - new Date(iso).getTime() > 24 * 3600 * 1000

const courseLabel = (c) => `${c.code} — ${c.title}`

// Render once per screen; every CoursePicker on it reads from this list.
export function CourseList({ courses }) {
  return <datalist id="visor-courses">{courses.map((c) => <option key={c.id} value={courseLabel(c)} />)}</datalist>
}

// Type-to-search course box (there are over a thousand courses, too many for a dropdown).
// Calls onChange with the course id as a string, or '' until the text matches a course.
export function CoursePicker({ courses, onChange, placeholder = 'Start typing, e.g. CS 1213' }) {
  const [text, setText] = useState('')
  function change(value) {
    setText(value)
    const typed = value.trim().toLowerCase()
    const match = courses.find((c) => courseLabel(c) === value || c.code.toLowerCase() === typed)
    onChange(match ? String(match.id) : '')
  }
  return <input list="visor-courses" value={text} onChange={(e) => change(e.target.value)} placeholder={placeholder} />
}

// Registrar-facing wording for statuses. The API keeps confirmed/proposed/unknown.
const STATUS = {
  approved: ['Approved', 'confirmed'],
  elective: ['Elective credit', 'elective'],
  none: ['No credit', 'muted'],
  proposed: ['Needs review', 'proposed'],
  rejected: ['Rejected', 'unknown'],
  unknown: ['Not on file', 'unknown'],
}

export function statusKey(status, kind) {
  if (status === 'confirmed') return kind === 'elective' ? 'elective' : kind === 'none' ? 'none' : 'approved'
  return status
}

export function StatusBadge({ status, kind }) {
  const [label, tone] = STATUS[statusKey(status, kind)] || [status, 'muted']
  return <span className={`badge badge-${tone}`}>{label}</span>
}

// What an equivalency row counts as at Lipscomb, in words.
export function lipscombLabel(q) {
  if (q.kind === 'elective') return 'General elective credit'
  if (q.kind === 'none') return 'Does not transfer'
  return q.course ? `${q.course.code} — ${q.course.title}` : 'No match picked yet'
}

export function PageHead({ title, children, actions }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {children && <p className="page-sub">{children}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}
