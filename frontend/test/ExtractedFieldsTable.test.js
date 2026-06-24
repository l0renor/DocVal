import { describe, it, expect } from 'vitest'
import { renderWithVuetify } from './render.js'
import ExtractedFieldsTable from '@/components/ExtractedFieldsTable.vue'

describe('ExtractedFieldsTable', () => {
  it('renders each field name and its value', () => {
    const { getByText } = renderWithVuetify(ExtractedFieldsTable, {
      props: {
        fields: [{ name: 'Name', value: 'Erika Mustermann', legibility: 'legible' }],
      },
    })

    expect(getByText('Name')).toBeTruthy()
    expect(getByText('Erika Mustermann')).toBeTruthy()
  })

  it('does not flag a legible field that has a value', () => {
    const { getByTestId } = renderWithVuetify(ExtractedFieldsTable, {
      props: {
        fields: [{ name: 'Name', value: 'Erika Mustermann', legibility: 'legible' }],
      },
    })

    expect(getByTestId('field-Name').getAttribute('data-flagged')).toBe('false')
  })

  it('flags a field whose value is missing', () => {
    const { getByTestId } = renderWithVuetify(ExtractedFieldsTable, {
      props: {
        fields: [{ name: 'Geburtsdatum', value: null, legibility: 'legible' }],
      },
    })

    expect(getByTestId('field-Geburtsdatum').getAttribute('data-flagged')).toBe('true')
  })

  it('flags a field the model could not read (illegible)', () => {
    const { getByTestId } = renderWithVuetify(ExtractedFieldsTable, {
      props: {
        fields: [{ name: 'Unterschrift', value: 'kritzel', legibility: 'illegible' }],
      },
    })

    expect(getByTestId('field-Unterschrift').getAttribute('data-flagged')).toBe('true')
  })
})
