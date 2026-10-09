import { queryClient } from '@/app/query-client'
import { revokeAllPrivateObjectUrls } from '@/shared/lib/private-object-url'
import { session } from '@/shared/session/session'

let installed = false
let authenticatedUserId: string | null = null

export function installSessionCachePolicy(): void {
  if (installed) return
  installed = true
  session.subscribe(() => {
    const snapshot = session.getSnapshot()
    const nextUserId = snapshot.status === 'authenticated' ? snapshot.user?.id ?? null : null
    const accountChanged = authenticatedUserId !== null && nextUserId !== null && authenticatedUserId !== nextUserId
    authenticatedUserId = nextUserId
    if (snapshot.status !== 'authenticated' || accountChanged) {
      revokeAllPrivateObjectUrls()
      queryClient.clear()
    }
  })
}
