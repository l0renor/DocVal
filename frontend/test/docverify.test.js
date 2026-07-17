import { describe, it, expect, vi } from 'vitest'
import { submitDocument } from '@/api/docverify.js'

// A fake fetch that routes by method/URL, mimicking the async job API:
//   POST /documents      -> 202 { job_id }
//   GET  /jobs/{job_id}  -> { status, results, antrag_metadata? }
function fakeBackend({ jobId = 'job-1', pollResponses }) {
  const calls = []
  const capturedForms = []
  const fetchImpl = vi.fn(async (url, options = {}) => {
    const method = options.method || 'GET'
    calls.push({ url, method })
    if (method === 'POST' && url.endsWith('/documents')) {
      capturedForms.push(options.body)
      return { ok: true, status: 202, json: async () => ({ job_id: jobId }) }
    }
    if (method === 'GET' && url.endsWith(`/jobs/${jobId}`)) {
      const body = pollResponses.shift()
      return { ok: true, status: 200, json: async () => body }
    }
    throw new Error(`unexpected request: ${method} ${url}`)
  })
  return { fetchImpl, calls, capturedForms }
}

const DONE_DOKUMENT = {
  status: 'done',
  result: { validation_status: 'accepted', classification: { document_type: 'Personalausweis' } },
}

const DONE_ANTRAG = {
  status: 'done',
  results: [
    { validation_status: 'accepted', classification: { document_type: 'personalausweis' } },
  ],
  antrag_metadata: {
    antrag_status: 'accepted',
    cross_document_findings: [],
    missing_required_documents: [],
    summary: 'Alles in Ordnung.',
  },
}

const file = () => new File(['x'], 'ausweis.pdf', { type: 'application/pdf' })

describe('submitDocument', () => {
  it('uploads the file and returns results + null antragMetadata for a dokument job', async () => {
    const { fetchImpl, calls } = fakeBackend({ pollResponses: [DONE_DOKUMENT] })

    const { results, antragMetadata } = await submitDocument(
      { files: [file()] },
      { fetchImpl, baseUrl: '/api', delay: () => {} },
    )

    expect(results).toEqual([DONE_DOKUMENT.result])
    expect(antragMetadata).toBeNull()
    expect(calls[0]).toEqual({ url: '/api/documents', method: 'POST' })
    expect(calls[1]).toEqual({ url: '/api/jobs/job-1', method: 'GET' })
  })

  it('keeps polling while the job is still pending', async () => {
    const { fetchImpl, calls } = fakeBackend({
      pollResponses: [{ status: 'pending' }, DONE_DOKUMENT],
    })

    const { results } = await submitDocument(
      { files: [file()] },
      { fetchImpl, baseUrl: '/api', delay: () => {} },
    )

    expect(results).toEqual([DONE_DOKUMENT.result])
    expect(calls.filter((c) => c.method === 'GET')).toHaveLength(2)
  })

  it('throws a readable error when the upload is rejected', async () => {
    const fetchImpl = vi.fn(async () => ({ ok: false, status: 415, json: async () => ({}) }))

    await expect(
      submitDocument({ files: [file()] }, { fetchImpl, baseUrl: '/api', delay: () => {} }),
    ).rejects.toThrow(/415/)
  })

  it('sends submission_type=antrag and returns antragMetadata for an antrag job', async () => {
    const { fetchImpl, capturedForms } = fakeBackend({ pollResponses: [DONE_ANTRAG] })
    const f1 = new File(['a'], 'a.jpg', { type: 'image/jpeg' })
    const f2 = new File(['b'], 'b.jpg', { type: 'image/jpeg' })

    const { results, antragMetadata } = await submitDocument(
      { files: [f1, f2], submissionType: 'antrag', config: '{"document_types":[]}' },
      { fetchImpl, baseUrl: '/api', delay: () => {} },
    )

    expect(results).toEqual(DONE_ANTRAG.results)
    expect(antragMetadata).toEqual(DONE_ANTRAG.antrag_metadata)

    // Verify the form contained submission_type and config
    const form = capturedForms[0]
    expect(form.get('submission_type')).toBe('antrag')
    expect(form.get('config')).toBe('{"document_types":[]}')
    // Both files appended under the 'files' key
    expect(form.getAll('files')).toHaveLength(2)
  })

  it('throws a readable error when the job status is "error"', async () => {
    const { fetchImpl } = fakeBackend({ pollResponses: [{ status: 'error', message: 'model timeout' }] })

    await expect(
      submitDocument({ files: [file()] }, { fetchImpl, baseUrl: '/api', delay: () => {} }),
    ).rejects.toThrow(/error/)
  })

  it('omits config field when config is null', async () => {
    const { fetchImpl, capturedForms } = fakeBackend({ pollResponses: [DONE_DOKUMENT] })

    await submitDocument(
      { files: [file()], config: null },
      { fetchImpl, baseUrl: '/api', delay: () => {} },
    )

    expect(capturedForms[0].has('config')).toBe(false)
  })
})
