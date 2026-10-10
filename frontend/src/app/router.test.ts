import { createMemoryHistory } from '@tanstack/react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type * as AuthApi from '@/features/auth/api/auth'

const restoreCandidateSession = vi.fn<() => Promise<boolean>>()

vi.mock('@/features/auth/api/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof AuthApi>()),
  restoreCandidateSession: () => restoreCandidateSession(),
}))

const { router } = await import('@/app/router')

async function open(path: string): Promise<string> {
  router.update({ ...router.options, history: createMemoryHistory({ initialEntries: [path] }) })
  await router.load()
  return router.state.location.pathname
}

describe('root redirect', () => {
  beforeEach(() => {
    restoreCandidateSession.mockReset()
  })

  it('sends an anonymous visitor to the login page', async () => {
    restoreCandidateSession.mockResolvedValue(false)

    expect(await open('/')).toBe('/login')
  })

  it('sends a signed-in candidate to the profile', async () => {
    restoreCandidateSession.mockResolvedValue(true)

    expect(await open('/')).toBe('/profile')
  })

  it('treats a failed session check as anonymous', async () => {
    restoreCandidateSession.mockRejectedValue(new Error('network'))

    expect(await open('/')).toBe('/login')
  })
})
