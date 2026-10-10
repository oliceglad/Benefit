import { createMemoryHistory } from '@tanstack/react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type * as AuthApi from '@/features/auth/api/auth'
import { session } from '@/shared/session/session'

const restoreAccountSession = vi.fn<() => Promise<boolean>>()

vi.mock('@/features/auth/api/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof AuthApi>()),
  restoreAccountSession: () => restoreAccountSession(),
}))

const { router } = await import('@/app/router')

// Like the real restore: a restored session puts the user into the session store.
function signedInAs(role: 'candidate' | 'employer') {
  restoreAccountSession.mockImplementation(() => {
    session.setAuthenticated({ id: 'user-1', email: 'user@example.com', role, isEmailVerified: true })
    return Promise.resolve(true)
  })
}

async function open(path: string): Promise<string> {
  router.update({ ...router.options, history: createMemoryHistory({ initialEntries: [path] }) })
  await router.load()
  return router.state.location.pathname
}

describe('root redirect', () => {
  beforeEach(() => {
    restoreAccountSession.mockReset()
    session.setUnknown()
  })

  it('sends an anonymous visitor to the login page', async () => {
    restoreAccountSession.mockResolvedValue(false)

    expect(await open('/')).toBe('/login')
  })

  it('sends a signed-in candidate to the profile', async () => {
    signedInAs('candidate')

    expect(await open('/')).toBe('/profile')
  })

  it('sends a signed-in employer to the vacancies', async () => {
    signedInAs('employer')

    expect(await open('/')).toBe('/vacancies')
  })

  it('treats a failed session check as anonymous', async () => {
    restoreAccountSession.mockRejectedValue(new Error('network'))

    expect(await open('/')).toBe('/login')
  })

  it('keeps the candidate bank restricted to employers', async () => {
    signedInAs('candidate')
    expect(await open('/talent')).toBe('/vacancies')
  })
})
