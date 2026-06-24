import { describe, it, expect, vi } from 'vitest'
import { fireEvent, waitFor } from '@testing-library/vue'
import { renderWithVuetify } from './render.js'
import App from '@/App.vue'

// Drop a File onto the (hidden) native file input that Vuetify's v-file-input
// renders, then fire the change event the component listens for.
async function uploadFile(container, file) {
  const input = container.querySelector('input[type="file"]')
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  await fireEvent.change(input)
}

const file = () => new File(['x'], 'ausweis.pdf', { type: 'application/pdf' })

describe('App', () => {
  it('shows an empty prompt before any document is submitted', () => {
    const { getByText } = renderWithVuetify(App, {
      props: { submitFn: vi.fn() },
    })

    expect(getByText(/Noch kein Dokument geprüft/i)).toBeTruthy()
  })

  it('renders a result card per sub-document after a successful submission', async () => {
    const submitFn = vi.fn(async () => [
      { validation_status: 'accepted', confidence: 0.9, classification: { document_type: 'Personalausweis' }, extracted_data: [], deficiencies: [], internal_note: null },
    ])
    const { container, getAllByTestId } = renderWithVuetify(App, { props: { submitFn } })

    await uploadFile(container, file())

    await waitFor(() => expect(getAllByTestId('result-card')).toHaveLength(1))
    expect(submitFn).toHaveBeenCalledOnce()
  })

  it('shows an error alert when the submission fails', async () => {
    const submitFn = vi.fn(async () => {
      throw new Error('Upload fehlgeschlagen (HTTP 415)')
    })
    const { container, getByText } = renderWithVuetify(App, { props: { submitFn } })

    await uploadFile(container, file())

    await waitFor(() => expect(getByText(/Upload fehlgeschlagen \(HTTP 415\)/)).toBeTruthy())
  })
})
