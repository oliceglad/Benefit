import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'

import { server } from '@/test/server'
import { session } from '@/shared/session/session'

class TestResizeObserver implements ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

globalThis.ResizeObserver = TestResizeObserver
document.elementFromPoint = () => null
HTMLElement.prototype.hasPointerCapture = () => false
HTMLElement.prototype.setPointerCapture = () => undefined
HTMLElement.prototype.releasePointerCapture = () => undefined
HTMLElement.prototype.scrollIntoView = () => undefined
if (!window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    }),
  })
}

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  session.clear()
})
afterAll(() => server.close())
