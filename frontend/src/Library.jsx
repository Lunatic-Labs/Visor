import { Fragment, useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import { PageHead, StatusBadge, lipscombLabel, statusKey } from './ui.jsx'

const PAGE = 25
const FILTERS = [
  ['all', 'All'],
  ['approved', 'Approved'],
  ['proposed', 'Needs review'],
  ['elective', 'Elective'],
  ['none', 'No credit'],
  ['rejected', 'Rejected'],
]

// Spreadsheet apps run cells starting with these as formulas.
const cell = (v) => {
  let s = v == null ? '' : String(v)
  if (/^[=+\-@]/.test(s)) s = `'${s}`
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

function downloadCsv(rows) {
  const head = ['School', 'Incoming course', 'Incoming title', 'Incoming hrs', 'Lipscomb course', 'Lipscomb title',
    'Lipscomb hrs', 'Counts as', 'Status', 'Decided by', 'Decided on', 'Notes']
  const lines = rows.map((q) => [
    q.external_course.school, `${q.external_course.subject} ${q.external_course.number}`, q.external_course.title,
    q.external_course.credits, q.course?.code, q.course?.title, q.course?.credits, q.kind, q.status,
    q.decided_by, q.decided_at, q.notes,
  ].map(cell).join(','))
  const blob = new Blob([[head.join(','), ...lines].join('\r\n')], { type: 'text/csv' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'visor-equivalencies.csv'
  a.click()
  URL.revokeObjectURL(a.href)
}

export default function Library() {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [school, setSchool] = useState('')
  const [filter, setFilter] = useState('all')
  const [page, setPage] = useState(0)
  const [open, setOpen] = useState(null)

  useEffect(() => { api('/api/equivalencies').then(setRows).catch((e) => setError(e.message)) }, [])

  const schools = useMemo(() => [...new Set((rows || []).map((q) => q.external_course.school))].sort(), [rows])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (rows || []).filter((r) => {
      if (school && r.external_course.school !== school) return false
      if (filter !== 'all' && statusKey(r.status, r.kind) !== filter) return false
      if (!q) return true
      const e = r.external_course
      return `${e.subject} ${e.number} ${e.subject}${e.number} ${e.title} ${e.school} ${r.course?.code || ''} ${r.course?.title || ''}`
        .toLowerCase().includes(q)
    })
  }, [rows, query, school, filter])

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE))
  const visible = filtered.slice(page * PAGE, page * PAGE + PAGE)
  const reset = (fn) => (e) => { fn(e.target.value); setPage(0); setOpen(null) }

  return (
    <>
      <PageHead
        title="Equivalency library"
        actions={<button type="button" className="btn-ghost" disabled={!filtered.length} onClick={() => downloadCsv(filtered)}>
          Download spreadsheet ({filtered.length.toLocaleString()})
        </button>}
      >
        Every incoming course on file and what it counts as at Lipscomb. Click a row for details.
      </PageHead>

      <section className="card">
        <div className="filters">
          <input className="search" value={query} onChange={reset(setQuery)}
                 placeholder="Search by course, title, or school" />
          <select value={school} onChange={reset(setSchool)}>
            <option value="">All schools</option>
            {schools.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="pills">
          {FILTERS.map(([key, label]) => (
            <button type="button" key={key} className={`pill${filter === key ? ' active' : ''}`}
                    onClick={() => { setFilter(key); setPage(0); setOpen(null) }}>{label}</button>
          ))}
        </div>

        {error && <p className="error">{error}</p>}
        {rows === null && !error && <p className="muted">Loading…</p>}

        {rows && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Incoming course</th><th>School</th><th>Lipscomb equivalent</th><th>Hrs</th><th>Status</th><th>Decided by</th></tr>
              </thead>
              <tbody>
                {visible.map((q) => (
                  <Fragment key={q.id}>
                    <tr className={`clickable${open === q.id ? ' selected' : ''}`} onClick={() => setOpen(open === q.id ? null : q.id)}>
                      <td><span className="code">{q.external_course.subject} {q.external_course.number}</span>
                        <div className="muted small">{q.external_course.title}</div></td>
                      <td>{q.external_course.school}</td>
                      <td>{q.kind === 'direct' && q.course
                        ? <><span className="code">{q.course.code}</span><div className="muted small">{q.course.title}</div></>
                        : lipscombLabel(q)}</td>
                      <td>{q.course?.credits ?? q.external_course.credits ?? '—'}</td>
                      <td><StatusBadge status={q.status} kind={q.kind} /></td>
                      <td className="small">{q.decided_by || '—'}</td>
                    </tr>
                    {open === q.id && (
                      <tr className="detail-row">
                        <td colSpan={6}>
                          <div className="detail">
                            <div><span className="muted small">Notes</span><div>{q.notes || 'None'}</div></div>
                            <div><span className="muted small">Decided on</span><div>{q.decided_at || '—'}</div></div>
                            <div><span className="muted small">Source</span><div>{q.source === 'sis_import' ? 'SIS export' : q.source}</div></div>
                            <div><span className="muted small">Flagged for review</span><div>{q.pending_reviews ? `${q.pending_reviews} pending` : 'No'}</div></div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
                {visible.length === 0 && (
                  <tr><td colSpan={6} className="muted">No equivalencies match these filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {rows && filtered.length > PAGE && (
          <div className="pager">
            <span className="muted small">
              {(page * PAGE + 1).toLocaleString()}–{Math.min(filtered.length, page * PAGE + PAGE).toLocaleString()} of {filtered.length.toLocaleString()}
            </span>
            <button type="button" className="btn-ghost" disabled={page === 0} onClick={() => { setPage(page - 1); setOpen(null) }}>Previous</button>
            <button type="button" className="btn-ghost" disabled={page >= pages - 1} onClick={() => { setPage(page + 1); setOpen(null) }}>Next</button>
          </div>
        )}
      </section>
    </>
  )
}
