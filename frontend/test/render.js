// Shared render helper: mounts a component with Vuetify installed, the way the
// real app does. Tests exercise components through the DOM, not internals.
import { render } from '@testing-library/vue'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

export function renderWithVuetify(component, options = {}) {
  const vuetify = createVuetify({ components, directives })
  return render(component, {
    ...options,
    global: {
      ...(options.global || {}),
      plugins: [...((options.global || {}).plugins || []), vuetify],
    },
  })
}

export * from '@testing-library/vue'
