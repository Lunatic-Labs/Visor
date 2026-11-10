// The write key (VISOR_WRITE_TOKEN on the server, KAN-46) is typed into the top bar: never in the
// code or a VITE_ env var, which would put it in the public bundle. Requests use the copy in memory;
// sessionStorage only carries it across a reload, so if storage is blocked, saves still work.
const WRITE_KEY = 'visor.writeKey'
let writeKey = null

export function getWriteKey() {
  if (writeKey === null) {
    try { writeKey = sessionStorage.getItem(WRITE_KEY) || '' } catch { writeKey = '' }
  }
  return writeKey
}

export function setWriteKey(key) {
  writeKey = key
  try {
    if (key) sessionStorage.setItem(WRITE_KEY, key)
    else sessionStorage.removeItem(WRITE_KEY)
  } catch { /* storage blocked: the key works until the page is reloaded */ }
}

// Headers for a request that changes data. Also used by the CSV uploads, which call fetch directly.
export function writeHeaders() {
  const key = getWriteKey().trim()
  return key ? { 'X-Visor-Token': key } : {}
}

// What to tell the user when a request fails. 401/403 come from the write guard (backend/visor/auth.py).
export function failureMessage(status, data, fallback = `Request failed (${status})`) {
  if (status === 401) {
    return getWriteKey().trim()
      ? 'That write key was not accepted. Check the "Write key" box in the top bar and try again.'
      : 'Enter the write key in the top bar to save changes.'
  }
  if (status === 403) return 'Saving is turned off on this deployment (no write key is set up on the server yet).'
  return data?.error || fallback
}

export async function api(path, { method = 'GET', body } = {}) {
  const headers = {
    ...(body && { 'Content-Type': 'application/json' }),
    ...(method !== 'GET' && writeHeaders()),
  }
  const r = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(failureMessage(r.status, data))
  return data
}

// The SIS importer's decided_by; decisions made in Visor itself carry a person's name instead.
export const SIS_DECIDER = "Registrar's office (SIS)"
