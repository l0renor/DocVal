// Vuetify components rely on ResizeObserver, which jsdom does not implement.
import { vi } from 'vitest'

global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// jsdom lacks visualViewport / matchMedia used by some Vuetify layout code.
// jsdom does not implement object URLs, used by the document preview.
global.URL.createObjectURL = global.URL.createObjectURL || (() => 'blob:mock')
global.URL.revokeObjectURL = global.URL.revokeObjectURL || (() => {})

global.matchMedia =
  global.matchMedia ||
  ((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
