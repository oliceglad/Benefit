import { useSyncExternalStore } from 'react'

const desktopQuery = '(min-width: 1024px)'

export function useDesktopLayout(): boolean {
  return useSyncExternalStore(
    (callback) => {
      const query = window.matchMedia(desktopQuery)
      query.addEventListener('change', callback)
      return () => query.removeEventListener('change', callback)
    },
    () => window.matchMedia(desktopQuery).matches,
    () => false,
  )
}
