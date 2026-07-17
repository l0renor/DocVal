import { describe, it, expect, vi } from 'vitest'
import { fireEvent, waitFor } from '@testing-library/vue'
import { renderWithVuetify } from './render.js'
import App from '@/App.vue'

// Drop files onto the (hidden) native file input that Vuetify's v-file-input renders.
async function uploadFiles(container, files) {
  const input = container.querySelector('input[type="file"]')
  Object.defineProperty(input, 'files', { value: files, configurable: true })
  await fireEvent.change(input)
}

const file = () => new File(['x'], 'ausweis.pdf', { type: 'application/pdf' })

// Minimal submitFn that returns the new { results, antragMetadata } shape.
function makeSubmitFn(results = [], antragMetadata = null) {
  return vi.fn(async () => ({ results, antragMetadata }))
}

describe('App', () => {
  it('shows an empty prompt before any document is submitted', () => {
    const { getByText } = renderWithVuetify(App, {
      props: { submitFn: makeSubmitFn() },
    })
    expect(getByText(/Noch kein Dokument geprüft/i)).toBeTruthy()
  })

  it('renders a result card per sub-document after a successful dokument submission', async () => {
    const submitFn = makeSubmitFn([
      {
        validation_status: 'accepted',
        confidence: 0.9,
        classification: { document_type: 'Personalausweis' },
        extracted_data: [],
        deficiencies: [],
        internal_note: null,
      },
    ])
    const { container, getAllByTestId } = renderWithVuetify(App, { props: { submitFn } })

    await uploadFiles(container, [file()])

    await waitFor(() => expect(getAllByTestId('result-card')).toHaveLength(1))
    expect(submitFn).toHaveBeenCalledOnce()
  })

  it('shows an error alert when the submission fails', async () => {
    const submitFn = vi.fn(async () => {
      throw new Error('Upload fehlgeschlagen (HTTP 415)')
    })
    const { container, getByText } = renderWithVuetify(App, { props: { submitFn } })

    await uploadFiles(container, [file()])

    await waitFor(() => expect(getByText(/Upload fehlgeschlagen \(HTTP 415\)/)).toBeTruthy())
  })

  it('shows the mode toggle with dokument and antrag options', () => {
    const { getAllByText } = renderWithVuetify(App, {
      props: { submitFn: makeSubmitFn() },
    })
    // Toggle buttons: at least one element with exactly "Dokument" and "Antrag"
    expect(getAllByText('Dokument').length).toBeGreaterThan(0)
    expect(getAllByText('Antrag').length).toBeGreaterThan(0)
  })

  it('shows the config editor textarea', () => {
    const { container } = renderWithVuetify(App, {
      props: { submitFn: makeSubmitFn() },
    })
    expect(container.querySelector('textarea')).toBeTruthy()
  })

  it('shows AntragsMetadataCard above results when job has antrag_metadata', async () => {
    const submitFn = makeSubmitFn(
      [
        {
          validation_status: 'accepted',
          confidence: 0.95,
          classification: { document_type: 'personalausweis' },
          extracted_data: [],
          deficiencies: [],
          internal_note: null,
        },
      ],
      {
        antrag_status: 'accepted',
        cross_document_findings: [],
        missing_required_documents: [],
        summary: 'Antrag vollständig und widerspruchsfrei.',
      },
    )
    const { container, getByText } = renderWithVuetify(App, { props: { submitFn } })

    await uploadFiles(container, [file()])

    await waitFor(() => getByText('Antrag vollständig und widerspruchsfrei.'))
    // AntragsMetadataCard rendered before result cards
    expect(container.querySelector('[data-antrag-status="accepted"]')).toBeTruthy()
    expect(container.querySelectorAll('[data-testid="result-card"]')).toHaveLength(1)
  })
})
