import { delay, http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'

import { orvalFetch, transportTestApi } from '@/shared/api/transport/orval-fetch'
import { logoutCandidate } from '@/features/auth/api/auth'
import { ApiError } from '@/shared/api/transport/api-error'
import { session } from '@/shared/session/session'
import { server } from '@/test/server'

afterEach(() => transportTestApi.reset())

describe('orvalFetch refresh', () => {
  it('runs one refresh for concurrent 401 responses and retries each request once', async () => {
    let refreshCount = 0
    server.use(
      http.post('*/api/v1/auth/refresh', async () => {
        refreshCount += 1
        await delay(20)
        return HttpResponse.json({
          access_token: 'new-access',
          refresh_token: 'new-refresh',
          expires_in: 900,
          refresh_expires_in: 604800,
        })
      }),
      http.get('*/api/v1/candidates/me', ({ request }) => {
        if (request.headers.get('Authorization') !== 'Bearer new-access') {
          return HttpResponse.json({ error: { code: 'unauthorized' } }, { status: 401 })
        }
        return HttpResponse.json({ user_id: 'candidate-id' })
      }),
    )
    session.setTokens({
      accessToken: 'expired-access',
      refreshToken: 'old-refresh',
      expiresIn: 0,
      refreshExpiresIn: 100,
    })

    const responses = await Promise.all([
      orvalFetch<{ data: { user_id: string } }>('/api/v1/candidates/me'),
      orvalFetch<{ data: { user_id: string } }>('/api/v1/candidates/me'),
    ])

    expect(refreshCount).toBe(1)
    expect(responses.map((response) => response.data.user_id)).toEqual([
      'candidate-id',
      'candidate-id',
    ])
    expect(session.getSnapshot().tokens?.accessToken).toBe('new-access')
  })

  it('settles all waiting requests when refresh fails', async () => {
    server.use(
      http.post('*/api/v1/auth/refresh', async () => {
        await delay(20)
        return HttpResponse.json({ error: { code: 'invalid_refresh_token' } }, { status: 401 })
      }),
      http.get('*/api/v1/candidates/me', () =>
        HttpResponse.json({ error: { code: 'unauthorized' } }, { status: 401 }),
      ),
    )
    session.setTokens({
      accessToken: 'expired-access',
      refreshToken: 'invalid-refresh',
      expiresIn: 0,
      refreshExpiresIn: 0,
    })

    const results = await Promise.allSettled([
      orvalFetch('/api/v1/candidates/me'),
      orvalFetch('/api/v1/candidates/me'),
    ])

    expect(results.every((result) => result.status === 'rejected')).toBe(true)
    expect(session.getSnapshot()).toEqual({ tokens: null, user: null })
  })

  it('does not restore a session when refresh completes after logout', async () => {
    let releaseRefresh = (): void => undefined
    let markRefreshStarted = (): void => undefined
    const refreshStarted = new Promise<void>((resolve) => {
      markRefreshStarted = resolve
    })
    const refreshReleased = new Promise<void>((resolve) => {
      releaseRefresh = resolve
    })
    server.use(
      http.post('*/api/v1/auth/refresh', async () => {
        markRefreshStarted()
        await refreshReleased
        return HttpResponse.json({
          access_token: 'late-access',
          refresh_token: 'late-refresh',
          expires_in: 900,
          refresh_expires_in: 604800,
        })
      }),
      http.post('*/api/v1/auth/logout', () => new HttpResponse(null, { status: 204 })),
      http.get('*/api/v1/candidates/me', () =>
        HttpResponse.json({ error: { code: 'unauthorized' } }, { status: 401 }),
      ),
    )
    session.setTokens({
      accessToken: 'expired-access',
      refreshToken: 'refresh-in-flight',
      expiresIn: 0,
      refreshExpiresIn: 100,
    })

    const protectedRequest = orvalFetch('/api/v1/candidates/me')
    await refreshStarted
    await logoutCandidate()
    releaseRefresh()

    await expect(protectedRequest).rejects.toBeInstanceOf(ApiError)
    expect(session.getSnapshot()).toEqual({ tokens: null, user: null })
  })
})
