// Thin client over the DocVerify async job API. `fetchImpl` and `delay` are
// injectable so the polling loop can be driven synchronously in tests.

const defaultDelay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * Upload a document, then poll the job until it is done, and return the
 * `results` array (one ValidationResult per detected sub-document).
 */
export async function submitDocument(
  file,
  { fetchImpl = fetch, baseUrl = '', pollDelayMs = 1000, delay = defaultDelay } = {},
) {
  const form = new FormData()
  form.append('file', file)

  const submitRes = await fetchImpl(`${baseUrl}/documents`, { method: 'POST', body: form })
  if (!submitRes.ok) {
    throw new Error(`Upload fehlgeschlagen (HTTP ${submitRes.status})`)
  }
  const { job_id: jobId } = await submitRes.json()

  for (;;) {
    const jobRes = await fetchImpl(`${baseUrl}/jobs/${jobId}`, { method: 'GET' })
    if (!jobRes.ok) {
      throw new Error(`Statusabfrage fehlgeschlagen (HTTP ${jobRes.status})`)
    }
    const job = await jobRes.json()
    if (job.status === 'done') {
      return job.results
    }
    await delay(pollDelayMs)
  }
}
