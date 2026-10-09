import { delay, http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'

import { logoutCandidate } from '@/features/auth/api/auth'
import { ApiError } from '@/shared/api/transport/api-error'
import { orvalFetch, transportTestApi } from '@/shared/api/transport/orval-fetch'
import { session } from '@/shared/session/session'
import { server } from '@/test/server'

const candidate = {
  id: 'candidate-id',
  email: 'candidate@example.ru',
  role: 'candidate',
  isEmailVerified: true,
}

const cookieTokenResponse = {
  access_token: null,
  refresh_token: null,
  token_type: 'Bearer',
  expires_in: 900,
  refresh_expires_in: 604800,
  delivery: 'cookie',
  csrf_token: 'rotated-csrf',
}

function installCsrfCookie(): void {
  document.cookie = 'benefit_csrf=test-csrf; Path=/'
}

afterEach(() => {
  document.cookie = 'benefit_csrf=; Max-Age=0; Path=/'
  transportTestApi.reset()
})

describe('orvalFetch cookie refresh', () => {
  it('runs one refresh for concurrent 401 responses and retries each request once', async () => {
    let refreshCount = 0
    let accessValid = false
    installCsrfCookie()
    session.setAuthenticated(candidate)
    server.use(
      http.post('*/api/v1/auth/refresh', async ({ request }) => {
        refreshCount += 1
        expect(request.headers.get('X-Auth-Mode')).toBe('cookie')
        expect(request.headers.get('X-CSRF-Token')).toBe('test-csrf')
        expect(await request.text()).toBe('')
        await delay(20)
        accessValid = true
        return HttpResponse.json(cookieTokenResponse)
      }),
      http.get('*/api/v1/candidates/me', ({ request }) => {
        expect(request.headers.has('Authorization')).toBe(false)
        if (!accessValid) {
          return HttpResponse.json({ error: { code: 'unauthorized' } }, { status: 401 })
        }
        return HttpResponse.json({ user_id: 'candidate-id' })
      }),
    )

    const responses = await Promise.all([
      orvalFetch<{ data: { user_id: string } }>('/api/v1/candidates/me'),
      orvalFetch<{ data: { user_id: string } }>('/api/v1/candidates/me'),
    ])

    expect(refreshCount).toBe(1)
    expect(responses.map((response) => response.data.user_id)).toEqual([
      'candidate-id',
      'candidate-id',
    ])
    expect(session.getSnapshot()).toMatchObject({ status: 'authenticated', user: candidate })
  })

  it('settles all waiting requests and closes the local session when refresh fails', async () => {
    installCsrfCookie()
    session.setAuthenticated(candidate)
    server.use(
      http.post('*/api/v1/auth/refresh', async () => {
        await delay(20)
        return HttpResponse.json({ error: { code: 'invalid_refresh_token' } }, { status: 401 })
      }),
      http.get('*/api/v1/candidates/me', () =>
        HttpResponse.json({ error: { code: 'unauthorized' } }, { status: 401 }),
      ),
    )

    const results = await Promise.allSettled([
      orvalFetch('/api/v1/candidates/me'),
      orvalFetch('/api/v1/candidates/me'),
    ])

    expect(results.every((result) => result.status === 'rejected')).toBe(true)
    expect(session.getSnapshot()).toEqual({ status: 'anonymous', user: null })
  })

  it('waits for an in-flight refresh before logout and never restores the local session', async () => {
    let releaseRefresh = (): void => undefined
    let markRefreshStarted = (): void => undefined
    const refreshStarted = new Promise<void>((resolve) => {
      markRefreshStarted = resolve
    })
    const refreshReleased = new Promise<void>((resolve) => {
      releaseRefresh = resolve
    })
    const calls: string[] = []
    installCsrfCookie()
    session.setAuthenticated(candidate)
    server.use(
      http.post('*/api/v1/auth/refresh', async () => {
        calls.push('refresh-started')
        markRefreshStarted()
        await refreshReleased
        calls.push('refresh-finished')
        return HttpResponse.json(cookieTokenResponse)
      }),
      http.post('*/api/v1/auth/logout', ({ request }) => {
        calls.push('logout')
        expect(request.headers.get('X-CSRF-Token')).toBe('test-csrf')
        return new HttpResponse(null, { status: 204 })
      }),
      http.get('*/api/v1/candidates/me', () =>
        HttpResponse.json({ error: { code: 'unauthorized' } }, { status: 401 }),
      ),
    )

    const protectedRequest = orvalFetch('/api/v1/candidates/me').catch((error: unknown) => error)
    await refreshStarted
    const logout = logoutCandidate()
    releaseRefresh()

    await logout
    expect(await protectedRequest).toBeInstanceOf(ApiError)
    expect(calls).toEqual(['refresh-started', 'refresh-finished', 'logout'])
    expect(session.getSnapshot()).toEqual({ status: 'anonymous', user: null })
  })

  it('maps the unified backend validation envelope and support metadata', async () => {
    session.setAnonymous()
    server.use(
      http.post('*/api/v1/auth/register', () => HttpResponse.json({
        error: {
          code: 'validation_error',
          message: 'Проверьте данные: email',
          service: 'auth-service',
          request_id: 'request-42',
          details: [{ field: 'email', message: 'некорректный адрес почты' }],
        },
      }, { status: 422 })),
    )

    const error = await orvalFetch('/api/v1/auth/register', { method: 'POST' }).catch(
      (caught: unknown) => caught,
    )

    expect(error).toMatchObject({
      status: 422,
      code: 'validation_error',
      service: 'auth-service',
      requestId: 'request-42',
      fieldIssues: [{ field: 'email', message: 'некорректный адрес почты' }],
    })
  })
})
