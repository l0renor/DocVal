import { describe, it, expect } from 'vitest'
import { renderWithVuetify } from './render.js'
import ResultsList from '@/components/ResultsList.vue'

function result(type, status = 'accepted') {
  return {
    validation_status: status,
    confidence: 0.9,
    classification: { document_type: type },
    extracted_data: [],
    deficiencies: [],
    internal_note: null,
  }
}

describe('ResultsList', () => {
  it('renders one result card per detected sub-document', () => {
    const { getAllByTestId } = renderWithVuetify(ResultsList, {
      props: {
        results: [result('Personalausweis'), result('Mietvertrag'), result('Sprachzertifikat')],
      },
    })

    expect(getAllByTestId('result-card')).toHaveLength(3)
  })

  it('shows each sub-document type', () => {
    const { getByText } = renderWithVuetify(ResultsList, {
      props: { results: [result('Personalausweis'), result('Mietvertrag')] },
    })

    expect(getByText('Personalausweis')).toBeTruthy()
    expect(getByText('Mietvertrag')).toBeTruthy()
  })
})
