import { describe, it, expect } from 'vitest'
import { renderWithVuetify } from './render.js'
import StatusAmpel from '@/components/StatusAmpel.vue'

describe('StatusAmpel', () => {
  it('shows a green Ampel labelled "Akzeptiert" for an accepted verdict', () => {
    const { getByText, getByTestId } = renderWithVuetify(StatusAmpel, {
      props: { status: 'accepted' },
    })

    expect(getByText('Akzeptiert')).toBeTruthy()
    expect(getByTestId('ampel').getAttribute('data-ampel')).toBe('green')
  })

  it('shows a yellow Ampel labelled "Unvollständig" for an incomplete verdict', () => {
    const { getByText, getByTestId } = renderWithVuetify(StatusAmpel, {
      props: { status: 'incomplete' },
    })

    expect(getByText('Unvollständig')).toBeTruthy()
    expect(getByTestId('ampel').getAttribute('data-ampel')).toBe('yellow')
  })

  it('shows a red Ampel labelled "Falscher Dokumenttyp" for an invalid_type verdict', () => {
    const { getByText, getByTestId } = renderWithVuetify(StatusAmpel, {
      props: { status: 'invalid_type' },
    })

    expect(getByText('Falscher Dokumenttyp')).toBeTruthy()
    expect(getByTestId('ampel').getAttribute('data-ampel')).toBe('red')
  })
})
