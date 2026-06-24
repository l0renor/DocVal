import { describe, it, expect } from 'vitest'
import { renderWithVuetify } from './render.js'
import ResultCard from '@/components/ResultCard.vue'

function makeResult(overrides = {}) {
  return {
    validation_status: 'accepted',
    confidence: 0.97,
    classification: { document_type: 'Personalausweis' },
    extracted_data: [],
    deficiencies: [],
    internal_note: null,
    ...overrides,
  }
}

describe('ResultCard', () => {
  it('shows the internal_note as a Sachbearbeiter-Hinweis when present', () => {
    const { getByText } = renderWithVuetify(ResultCard, {
      props: {
        result: makeResult({
          internal_note: 'Indexmiete-Klausel — manuelle Prüfung empfohlen',
        }),
      },
    })

    expect(getByText('Hinweis')).toBeTruthy()
    expect(getByText('Indexmiete-Klausel — manuelle Prüfung empfohlen')).toBeTruthy()
  })

  it('does not render a Hinweis section when internal_note is null', () => {
    const { queryByText } = renderWithVuetify(ResultCard, {
      props: { result: makeResult({ internal_note: null }) },
    })

    expect(queryByText('Hinweis')).toBeNull()
  })
})
