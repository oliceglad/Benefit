import { queryClient } from '@/app/query-client'
import { session } from '@/shared/session/session'

let installed = false

export function installSessionCachePolicy(): void {
  if (installed) return
  installed = true
  session.subscribe(() => {
    if (!session.getSnapshot().tokens) queryClient.clear()
  })
}
