import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'

// A calm, public-sector palette: a trustworthy blue with clear Ampel accents.
const docverify = {
  dark: false,
  colors: {
    background: '#F4F6FB',
    surface: '#FFFFFF',
    primary: '#1457A8',
    secondary: '#4A5C73',
    success: '#2E7D32',
    warning: '#F9A825',
    error: '#C62828',
    info: '#1457A8',
  },
}

export default createVuetify({
  theme: {
    defaultTheme: 'docverify',
    themes: { docverify },
  },
  defaults: {
    VCard: { rounded: 'lg' },
    VBtn: { rounded: 'lg' },
    VChip: { rounded: 'lg' },
    VFileInput: { variant: 'outlined', density: 'comfortable' },
  },
})
