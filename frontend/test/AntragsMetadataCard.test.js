import { describe, it, expect } from 'vitest'
import { renderWithVuetify } from './render.js'
import AntragsMetadataCard from '@/components/AntragsMetadataCard.vue'

function makeMetadata(overrides = {}) {
  return {
    antrag_status: 'accepted',
    cross_document_findings: [],
    missing_required_documents: [],
    summary: 'Alle Dokumente in Ordnung.',
    ...overrides,
  }
}

describe('AntragsMetadataCard', () => {
  it('shows the German summary text', () => {
    const { getByText } = renderWithVuetify(AntragsMetadataCard, {
      props: { metadata: makeMetadata({ summary: 'Alle Dokumente geprüft.' }) },
    })
    expect(getByText('Alle Dokumente geprüft.')).toBeTruthy()
  })

  it('shows cross-document findings when present', () => {
    const { getByText } = renderWithVuetify(AntragsMetadataCard, {
      props: {
        metadata: makeMetadata({
          cross_document_findings: ['Name im Ausweis stimmt nicht mit Mietvertrag überein.'],
        }),
      },
    })
    expect(getByText('Name im Ausweis stimmt nicht mit Mietvertrag überein.')).toBeTruthy()
  })

  it('shows missing required documents when present', () => {
    const { getByText } = renderWithVuetify(AntragsMetadataCard, {
      props: {
        metadata: makeMetadata({ missing_required_documents: ['personalausweis'] }),
      },
    })
    expect(getByText(/personalausweis/i)).toBeTruthy()
  })

  it('shows accepted bundle status with data-antrag-status attribute', () => {
    const { container } = renderWithVuetify(AntragsMetadataCard, {
      props: { metadata: makeMetadata({ antrag_status: 'accepted' }) },
    })
    expect(container.querySelector('[data-antrag-status="accepted"]')).toBeTruthy()
  })

  it('shows incomplete bundle status with data-antrag-status attribute', () => {
    const { container } = renderWithVuetify(AntragsMetadataCard, {
      props: {
        metadata: makeMetadata({
          antrag_status: 'incomplete',
          cross_document_findings: ['Diskrepanz gefunden.'],
        }),
      },
    })
    expect(container.querySelector('[data-antrag-status="incomplete"]')).toBeTruthy()
  })
})
