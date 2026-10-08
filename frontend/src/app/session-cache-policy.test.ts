import { afterEach, describe, expect, it } from 'vitest'

import { queryClient } from '@/app/query-client'
import { installSessionCachePolicy } from '@/app/session-cache-policy'
import { session } from '@/shared/session/session'

installSessionCachePolicy()

afterEach(() => {
  session.clear()
  queryClient.clear()
})

describe('session cache policy', () => {
  it('removes private data before another account can sign in', () => {
    session.setTokens({
      accessToken: 'first-access',
      refreshToken: 'first-refresh',
      expiresIn: 900,
      refreshExpiresIn: 604800,
    })
    queryClient.setQueryData(['candidate', 'profile'], { user_id: 'first-user' })

    session.clear()

    expect(queryClient.getQueryData(['candidate', 'profile'])).toBeUndefined()
  })
})
