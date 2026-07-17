// Thin client over the DocVerify async job API. `fetchImpl` and `delay` are
// injectable so the polling loop can be driven synchronously in tests.

const defaultDelay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * Upload one or more documents and poll until the job completes.
 *
 * @param {object} submission
 *   files          - File[] (one for dokument, one or more for antrag)
 *   submissionType - 'dokument' | 'antrag'  (default 'dokument')
 *   config         - JSON string for inline config, or null
 *
 * @returns {{ results: ValidationResult[], antragMetadata: object|null }}
 */
export async function submitDocument(
  { files, submissionType = 'dokument', config = null },
  { fetchImpl = fetch, baseUrl = '', pollDelayMs = 1000, delay = defaultDelay } = {},
) {
  const form = new FormData()
  form.append('submission_type', submissionType)
  for (const file of files) {
    form.append('files', file)
  }
  if (config !== null) {
    form.append('config', config)
  }

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
      const results = job.results || (job.result ? [job.result] : [])
      const antragMetadata = job.antrag_metadata ?? null
      return { results, antragMetadata }
    }
    if (job.status !== 'pending') {
      throw new Error(`Job beendet mit Status: ${job.status}`)
    }
    await delay(pollDelayMs)
  }
}
