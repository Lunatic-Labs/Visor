import { useState } from 'react'
import { PageHead } from './ui.jsx'

const FILES = [
  { key: 'terms', label: 'Terms' },
  { key: 'courses', label: 'Courses' },
  { key: 'prereqs', label: 'Prerequisites' },
  { key: 'sections', label: 'Sections' },
]

// Upload form for the registrar's catalog/section CSVs (KAN-25). Any subset of the four files
// can be uploaded at once -- e.g. just sections.csv for a new term's schedule, reusing courses
// that already exist.
export default function CatalogImport() {
  const [files, setFiles] = useState({})
  const [dryRun, setDryRun] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function upload(e) {
    e.preventDefault()
    setError('')
    setResult(null)
    const chosen = Object.entries(files).filter(([, f]) => f)
    if (chosen.length === 0) {
      setError('Choose at least one CSV file to import.')
      return
    }
    const body = new FormData()
    for (const [key, file] of chosen) body.append(key, file)

    setLoading(true)
    try {
      const r = await fetch(`/api/import/catalog${dryRun ? '?dry_run=1' : ''}`, { method: 'POST', body })
      if (!r.ok) throw new Error((await r.json()).error || 'Import failed')
      setResult(await r.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <PageHead title="Import catalog">
        Upload Lipscomb's course catalog and section schedule as CSV files. Any row with a problem is skipped
        and listed with its line number; everything else still imports. Uploading the same file twice is safe.
      </PageHead>

      <section className="card">
      <form onSubmit={upload} className="lookup-form">
        {FILES.map(({ key, label }) => (
          <label key={key}>
            {label}{' '}
            <input type="file" accept=".csv"
                  onChange={(e) => setFiles((f) => ({ ...f, [key]: e.target.files[0] || null }))} />
          </label>
        ))}
        <label>
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />{' '}
          Dry run (check only, don't save)
        </label>
        <button type="submit" disabled={loading}>{loading ? 'Importing…' : 'Import'}</button>
      </form>
      {error && <p className="error">{error}</p>}
      </section>

      {result && (
        <section className={`lookup-result status-${result.ok ? 'confirmed' : 'proposed'}`}>
          <h2>
            Import result
            <span className={`badge badge-${result.ok ? 'confirmed' : 'proposed'}`}>
              {result.ok ? 'all rows saved' : `${result.errors.length} rejected`}
            </span>
          </h2>
          <ul>
            {Object.entries(result.counts).map(([k, v]) => <li key={k}>{k}: {v}</li>)}
          </ul>
          {result.errors.length > 0 && (
            <>
              <p>Rejected rows:</p>
              <ul className="conflicts">
                {result.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </>
          )}
        </section>
      )}
    </>
  )
}
