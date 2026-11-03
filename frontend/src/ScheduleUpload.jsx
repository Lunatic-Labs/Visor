import { useEffect, useState } from 'react'
import { api } from './api.js'
import { formatWhen, timeAgo } from './ui.jsx'

const LINES = [
  ['sections_added', 'New sections'],
  ['sections_updated', 'Seat counts updated'],
  ['courses_added', 'New courses'],
  ['meetings_added', 'New meeting times'],
  ['meetings_removed', 'Old meeting times removed'],
  ['sections_removed', 'Classes removed (no longer in the file)'],
  ['sections_skipped', 'Sections skipped'],
]

// Upload the CSV exported from the university's public class-schedule page. Re-uploading is how
// seat counts get refreshed; the Schedule tab shows when that last happened.
export default function ScheduleUpload() {
  const [file, setFile] = useState(null)
  const [checkOnly, setCheckOnly] = useState(false)
  const [removeMissing, setRemoveMissing] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [last, setLast] = useState(null)

  function loadLast() {
    api('/api/terms').then((terms) => {
      const stamped = terms.filter((t) => t.schedule_updated_at)
        .sort((a, b) => b.schedule_updated_at.localeCompare(a.schedule_updated_at))
      setLast(stamped[0] || null)
    }).catch(() => {})
  }
  useEffect(loadLast, [])

  async function upload(e) {
    e.preventDefault()
    setError(''); setResult(null)
    if (!file) { setError('Choose the schedule CSV first.'); return }
    if (removeMissing && !checkOnly && !window.confirm(
      "This permanently removes every class that isn't in this file. Continue?\n\n" +
      "(Tip: tick 'Check only' first to see how many.)")) return
    const body = new FormData()
    body.append('schedule', file)
    const params = new URLSearchParams()
    if (checkOnly) params.set('dry_run', '1')
    if (removeMissing) params.set('remove_missing', '1')
    const qs = params.toString()
    setLoading(true)
    try {
      const r = await fetch(`/api/import/schedule${qs ? `?${qs}` : ''}`, { method: 'POST', body })
      const data = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(data.error || `Upload failed (${r.status})`)
      setResult(data)
      if (!data.dry_run) loadLast()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="card">
      <h2>Class schedule</h2>
      <p className="muted">
        On the university's class-schedule page, choose <strong>Export → CSV</strong>, then upload that file here
        whenever you want seat counts and sections refreshed. Uploading the same file again is always safe.
      </p>
      <p className={last ? 'small' : 'small muted'}>
        {last
          ? <>Last updated <strong>{formatWhen(last.schedule_updated_at)}</strong> ({timeAgo(last.schedule_updated_at)})
            {last.schedule_file && <span className="muted"> from {last.schedule_file}</span>}</>
          : "The schedule hasn't been loaded through Visor yet."}
      </p>

      <form onSubmit={upload} className="lookup-form">
        <label className="grow">
          Schedule CSV
          <input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files[0] || null)} />
        </label>
        <button type="submit" disabled={loading}>
          {loading ? 'Uploading…' : checkOnly ? 'Check file' : 'Upload schedule'}
        </button>
        <div className="upload-options">
          <label className="check">
            <input type="checkbox" checked={removeMissing} onChange={(e) => setRemoveMissing(e.target.checked)} />
            This file is the complete schedule: remove classes that aren't in it
          </label>
          <label className="check">
            <input type="checkbox" checked={checkOnly} onChange={(e) => setCheckOnly(e.target.checked)} />
            Check only, don't save (shows what would change)
          </label>
        </div>
      </form>
      {error && <p className="error">{error}</p>}

      {result && (
        <div className={`lookup-result status-${result.ok ? 'confirmed' : 'proposed'}`}>
          <h2>
            {result.dry_run ? 'Checked, nothing saved. This is what would change' : 'Schedule updated'}
            <span className={`badge badge-${result.ok ? 'confirmed' : 'proposed'}`}>
              {result.ok ? 'no file problems' : `${result.issues.length} file note${result.issues.length === 1 ? '' : 's'}`}
            </span>
          </h2>
          <p>{result.counts.sections_in_file.toLocaleString()} sections in the file.</p>
          <ul>
            {LINES.filter(([key]) => result.counts[key] > 0).map(([key, label]) => (
              <li key={key}>{label}: {result.counts[key].toLocaleString()}</li>
            ))}
            {LINES.every(([key]) => !result.counts[key]) && <li>Nothing changed. It was already up to date.</li>}
          </ul>
          {!result.remove_missing && result.counts.sections_not_in_file > 0 && (
            <p className="muted small">
              {result.counts.sections_not_in_file.toLocaleString()} class{result.counts.sections_not_in_file === 1 ? '' : 'es'} in
              Visor {result.counts.sections_not_in_file === 1 ? "isn't" : "aren't"} in this file, so
              {result.counts.sections_not_in_file === 1 ? ' it was' : ' they were'} kept. If this file is the complete
              schedule, tick "remove classes that aren't in it" to drop them.
            </p>
          )}
          {result.issues.length > 0 && (
            <details>
              <summary>
                {result.issues.length} row{result.issues.length === 1 ? '' : 's'} in the university's file Visor
                couldn't fully use
              </summary>
              <p className="muted small">
                These are problems in the export itself, not changes waiting to be made. Visor imported everything
                else. They'll be listed every time this file is checked or uploaded, until the university's
                schedule data is corrected; uploading again won't clear them.
              </p>
              <ul className="conflicts">
                {result.issues.map((i, n) => <li key={n}>{i}</li>)}
              </ul>
            </details>
          )}
        </div>
      )}
    </section>
  )
}
