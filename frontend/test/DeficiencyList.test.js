import { describe, it, expect } from 'vitest'
import { renderWithVuetify } from './render.js'
import DeficiencyList from '@/components/DeficiencyList.vue'

describe('DeficiencyList', () => {
  it('lists each deficiency with its field and reason', () => {
    const { getByText } = renderWithVuetify(DeficiencyList, {
      props: {
        deficiencies: [
          { field: 'Gültigkeitsdatum', reason: 'Dokument ist abgelaufen' },
        ],
      },
    })

    expect(getByText('Gültigkeitsdatum')).toBeTruthy()
    expect(getByText('Dokument ist abgelaufen')).toBeTruthy()
  })

  it('shows a "keine Mängel" message when there are none', () => {
    const { getByText } = renderWithVuetify(DeficiencyList, {
      props: { deficiencies: [] },
    })

    expect(getByText('Keine Mängel')).toBeTruthy()
  })
})
