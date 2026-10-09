import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { queryClient } from '@/app/query-client'
import { installSessionCachePolicy } from '@/app/session-cache-policy'
import { createPrivateObjectUrl, privateObjectUrlTestApi } from '@/shared/lib/private-object-url'
import { session } from '@/shared/session/session'

installSessionCachePolicy()

let revokeObjectUrl: ReturnType<typeof vi.fn>

beforeEach(() => {
  privateObjectUrlTestApi.reset()
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:private-photo') })
  revokeObjectUrl = vi.fn()
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectUrl })
})

afterEach(() => {
  session.clear()
  queryClient.clear()
  privateObjectUrlTestApi.reset()
  vi.restoreAllMocks()
})

describe('session cache policy', () => {
  it('removes private data before another account can sign in', () => {
    session.setAuthenticated({
      id: 'first-user',
      email: 'first@example.ru',
      role: 'candidate',
      isEmailVerified: true,
    })
    queryClient.setQueryData(['candidate', 'profile'], { user_id: 'first-user' })

    session.clear()

    expect(queryClient.getQueryData(['candidate', 'profile'])).toBeUndefined()
  })

  it('revokes private image URLs when the session ends', () => {
    session.setAuthenticated({
      id: 'first-user',
      email: 'first@example.ru',
      role: 'candidate',
      isEmailVerified: true,
    })
    createPrivateObjectUrl(new Blob(['private photo'], { type: 'image/jpeg' }))

    session.clear()

    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:private-photo')
    expect(privateObjectUrlTestApi.size()).toBe(0)
  })

  it('clears private data when an authenticated account is replaced', () => {
    session.setAuthenticated({ id: 'first-user', email: 'first@example.ru', role: 'candidate', isEmailVerified: true })
    queryClient.setQueryData(['candidate', 'profile'], { user_id: 'first-user' })
    createPrivateObjectUrl(new Blob(['private photo'], { type: 'image/jpeg' }))

    session.setAuthenticated({ id: 'second-user', email: 'second@example.ru', role: 'candidate', isEmailVerified: true })

    expect(queryClient.getQueryData(['candidate', 'profile'])).toBeUndefined()
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:private-photo')
  })
})
