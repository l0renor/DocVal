import { describe, it, expect, vi } from 'vitest'
import { submitDocument } from '@/api/docverify.js'

// A fake fetch that routes by method/URL, mimicking the async job API:
//   POST /documents      -> 202 { job_id }
//   GET  /jobs/{job_id}   -> { status, results }
function fakeBackend({ jobId = 'job-1', pollResponses }) {
  const calls = []
  const fetchImpl = vi.fn(async (url, options = {}) => {
    const method = options.method || 'GET'
    calls.push({ url, method })
    if (method === 'POST' && url.endsWith('/documents')) {
      return { ok: true, status: 202, json: async () => ({ job_id: jobId }) }
    }
    if (method === 'GET' && url.endsWith(`/jobs/${jobId}`)) {
      const body = pollResponses.shift()
      return { ok: true, status: 200, json: async () => body }
    }
    throw new Error(`unexpected request: ${method} ${url}`)
  })
  return { fetchImpl, calls }
}

const DONE = {
  status: 'done',
  results: [{ validation_status: 'accepted', classification: { document_type: 'Personalausweis' } }],
}

describe('submitDocument', () => {
  it('uploads the file and returns the results once the job is done', async () => {
    const { fetchImpl, calls } = fakeBackend({ pollResponses: [DONE] })
    const file = new File(['x'], 'ausweis.pdf', { type: 'application/pdf' })

    const results = await submitDocument(file, { fetchImpl, baseUrl: '/api', delay: () => {} })

    expect(results).toEqual(DONE.results)
    expect(calls[0]).toEqual({ url: '/api/documents', method: 'POST' })
    expect(calls[1]).toEqual({ url: '/api/jobs/job-1', method: 'GET' })
  })

  it('keeps polling while the job is still pending', async () => {
    const { fetchImpl, calls } = fakeBackend({
      pollResponses: [{ status: 'pending', results: null }, DONE],
    })
    const file = new File(['x'], 'ausweis.pdf', { type: 'application/pdf' })

    const results = await submitDocument(file, { fetchImpl, baseUrl: '/api', delay: () => {} })

    expect(results).toEqual(DONE.results)
    expect(calls.filter((c) => c.method === 'GET')).toHaveLength(2)
  })

  it('throws a readable error when the upload is rejected', async () => {
    const fetchImpl = vi.fn(async () => ({ ok: false, status: 415, json: async () => ({}) }))
    const file = new File(['x'], 'ausweis.pdf', { type: 'application/pdf' })

    await expect(
      submitDocument(file, { fetchImpl, baseUrl: '/api', delay: () => {} }),
    ).rejects.toThrow(/415/)
  })
})
