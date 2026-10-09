import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'

import {
  authTestApi,
  loginCandidate,
  registerCandidate,
  restoreCandidateSession,
  verifyCandidateEmail,
} from '@/features/auth/api/auth'
import { getCandidateProfile } from '@/features/candidate-profile/api/profile'
import { ApiError } from '@/shared/api/transport/api-error'
import { session } from '@/shared/session/session'
import { server } from '@/test/server'

const cookieTokens = {
  access_token: null,
  refresh_token: null,
  token_type: 'Bearer',
  expires_in: 900,
  refresh_expires_in: 604800,
  delivery: 'cookie',
  csrf_token: 'csrf-token',
}

const candidateResponse = {
  id: 'candidate-id',
  email: 'candidate@example.ru',
  role: 'candidate',
  full_name: 'Анна Очень-Длинная-Фамилия',
  is_email_verified: true,
  created_at: '2026-10-08T00:00:00Z',
}

afterEach(() => {
  document.cookie = 'benefit_csrf=; Max-Age=0; Path=/'
  authTestApi.reset()
  session.reset()
})

describe('loginCandidate', () => {
  it('requests an HttpOnly-cookie session and loads the current candidate', async () => {
    server.use(
      http.post('*/api/v1/auth/login', ({ request }) => {
        expect(request.headers.get('X-Auth-Mode')).toBe('cookie')
        return HttpResponse.json(cookieTokens)
      }),
      http.get('*/api/v1/users/me', ({ request }) => {
        expect(request.headers.has('Authorization')).toBe(false)
        return HttpResponse.json(candidateResponse)
      }),
    )

    await loginCandidate({ email: 'candidate@example.ru', password: 'Password123!' })

    expect(session.getSnapshot()).toMatchObject({
      status: 'authenticated',
      user: { email: 'candidate@example.ru', role: 'candidate' },
    })
    expect(localStorage).toHaveLength(0)
  })

  it('exposes Retry-After and leaves no local session after rate limiting', async () => {
    server.use(
      http.post(
        '*/api/v1/auth/login',
        () => HttpResponse.json({ error: { code: 'rate_limited', message: 'Слишком много попыток' } }, {
          status: 429,
          headers: { 'Retry-After': '12' },
        }),
      ),
    )

    const error = await loginCandidate({ email: 'candidate@example.ru', password: 'bad' }).catch(
      (caught: unknown) => caught,
    )

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 429, retryAfterSeconds: 12 })
    expect(session.getSnapshot()).toEqual({ status: 'anonymous', user: null })
  })

  it('rejects a valid account without the candidate role and clears its cookie session', async () => {
    let logoutCalled = false
    server.use(
      http.post('*/api/v1/auth/login', () => HttpResponse.json(cookieTokens)),
      http.get('*/api/v1/users/me', () => HttpResponse.json({
        ...candidateResponse,
        id: 'employer-id',
        email: 'employer@example.ru',
        role: 'employer',
      })),
      http.post('*/api/v1/auth/logout', () => {
        logoutCalled = true
        return new HttpResponse(null, { status: 204 })
      }),
    )

    const error = await loginCandidate({ email: 'employer@example.ru', password: 'Password123!' }).catch(
      (caught: unknown) => caught,
    )

    expect(error).toMatchObject({ status: 403, code: 'candidate_access_required' })
    expect(logoutCalled).toBe(true)
    expect(session.getSnapshot()).toEqual({ status: 'anonymous', user: null })
  })
})

describe('cookie session restoration', () => {
  it('refreshes an expired access cookie and restores /users/me after a page reload', async () => {
    let accessValid = false
    let refreshCount = 0
    document.cookie = 'benefit_csrf=restore-csrf; Path=/'
    session.reset()
    server.use(
      http.get('*/api/v1/users/me', () => {
        if (!accessValid) {
          return HttpResponse.json({ error: { code: 'unauthorized' } }, { status: 401 })
        }
        return HttpResponse.json(candidateResponse)
      }),
      http.post('*/api/v1/auth/refresh', ({ request }) => {
        refreshCount += 1
        expect(request.headers.get('X-CSRF-Token')).toBe('restore-csrf')
        accessValid = true
        return HttpResponse.json(cookieTokens)
      }),
    )

    await expect(restoreCandidateSession()).resolves.toBe(true)

    expect(refreshCount).toBe(1)
    expect(session.getSnapshot()).toMatchObject({
      status: 'authenticated',
      user: { id: 'candidate-id' },
    })
  })
})

describe('candidate registration', () => {
  it('registers, verifies with cookie mode, loads the current user and opens the profile', async () => {
    const calls: string[] = []
    server.use(
      http.post('*/api/v1/auth/register', async ({ request }) => {
        calls.push('register')
        const body = (await request.json()) as Record<string, unknown>
        expect(body).toMatchObject({
          email: 'new-candidate@example.ru',
          role: 'candidate',
          full_name: 'Анна Иванова',
        })
        return HttpResponse.json({
          email: 'new-candidate@example.ru',
          code_expires_in: 600,
          resend_available_in: 60,
        }, { status: 201 })
      }),
      http.post('*/api/v1/auth/verify-email', async ({ request }) => {
        calls.push('verify')
        expect(request.headers.get('X-Auth-Mode')).toBe('cookie')
        expect(await request.json()).toEqual({
          email: 'new-candidate@example.ru',
          code: '012345',
        })
        return HttpResponse.json(cookieTokens)
      }),
      http.get('*/api/v1/users/me', () => {
        calls.push('me')
        return HttpResponse.json({
          ...candidateResponse,
          id: 'new-candidate-id',
          email: 'new-candidate@example.ru',
          full_name: 'Анна Иванова',
        })
      }),
      http.get('*/api/v1/candidates/me', () => {
        calls.push('profile')
        return HttpResponse.json({ user_id: 'new-candidate-id' })
      }),
    )

    const registration = await registerCandidate({
      email: 'new-candidate@example.ru',
      password: 'Password123!',
      fullName: 'Анна Иванова',
    })
    await verifyCandidateEmail(registration.email, '012345')
    const profile = await getCandidateProfile()

    expect(profile.user_id).toBe('new-candidate-id')
    expect(calls).toEqual(['register', 'verify', 'me', 'profile'])
    expect(session.getSnapshot().user?.email).toBe('new-candidate@example.ru')
  })

  it('keeps field errors from the unified backend envelope', async () => {
    server.use(
      http.post('*/api/v1/auth/register', () => HttpResponse.json({
        error: {
          code: 'validation_error',
          message: 'Проверьте данные: password',
          service: 'auth-service',
          request_id: 'request-password',
          details: [{ field: 'password', message: 'Пароль должен содержать буквы и цифры' }],
        },
      }, { status: 422 })),
    )

    const error = await registerCandidate({
      email: 'candidate@example.ru',
      password: '12345678',
    }).catch((caught: unknown) => caught)

    expect(error).toMatchObject({
      status: 422,
      service: 'auth-service',
      requestId: 'request-password',
      fieldIssues: [{ field: 'password', message: 'Пароль должен содержать буквы и цифры' }],
    })
  })
})
