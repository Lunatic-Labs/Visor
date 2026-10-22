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
