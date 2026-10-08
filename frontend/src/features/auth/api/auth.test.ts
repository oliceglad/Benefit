import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'

import {
  loginCandidate,
  registerCandidate,
  verifyCandidateEmail,
} from '@/features/auth/api/auth'
import { getCandidateProfile } from '@/features/candidate-profile/api/profile'
import { ApiError } from '@/shared/api/transport/api-error'
import { session } from '@/shared/session/session'
import { server } from '@/test/server'

const tokens = {
  access_token: 'access-token',
  refresh_token: 'refresh-token',
  token_type: 'Bearer',
  expires_in: 900,
  refresh_expires_in: 604800,
}

afterEach(() => session.clear())

describe('loginCandidate', () => {
  it('stores tokens only in memory and loads the current candidate', async () => {
    server.use(
      http.post('*/api/v1/auth/login', () => HttpResponse.json(tokens)),
      http.get('*/api/v1/users/me', ({ request }) => {
        expect(request.headers.get('Authorization')).toBe('Bearer access-token')
        return HttpResponse.json({
          id: 'candidate-id',
          email: 'candidate@example.ru',
          role: 'candidate',
          full_name: 'Анна Очень-Длинная-Фамилия',
          is_email_verified: true,
          created_at: '2026-10-08T00:00:00Z',
        })
      }),
    )

    await loginCandidate({ email: 'candidate@example.ru', password: 'Password123!' })

    expect(session.getSnapshot()).toMatchObject({
      tokens: { accessToken: 'access-token', refreshToken: 'refresh-token' },
      user: { email: 'candidate@example.ru', role: 'candidate' },
    })
    expect(localStorage).toHaveLength(0)
  })

  it('exposes Retry-After and leaves no session after rate limiting', async () => {
    server.use(
      http.post(
        '*/api/v1/auth/login',
        () => HttpResponse.json({ error: { code: 'rate_limited', message: 'Too many attempts' } }, {
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
    expect(session.getSnapshot()).toEqual({ tokens: null, user: null })
  })

  it('rejects a valid account without the candidate role', async () => {
    server.use(
      http.post('*/api/v1/auth/login', () => HttpResponse.json(tokens)),
      http.get('*/api/v1/users/me', () =>
        HttpResponse.json({
          id: 'employer-id',
          email: 'employer@example.ru',
          role: 'employer',
          full_name: 'Работодатель',
          is_email_verified: true,
          created_at: '2026-10-08T00:00:00Z',
        }),
      ),
    )

    const error = await loginCandidate({ email: 'employer@example.ru', password: 'Password123!' }).catch(
      (caught: unknown) => caught,
    )

    expect(error).toMatchObject({ status: 403, code: 'candidate_access_required' })
    expect(session.getSnapshot()).toEqual({ tokens: null, user: null })
  })
})

describe('candidate registration', () => {
  it('registers, verifies, loads the current user and opens the profile', async () => {
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
        return HttpResponse.json(
          {
            email: 'new-candidate@example.ru',
            code_expires_in: 600,
            resend_available_in: 60,
          },
          { status: 201 },
        )
      }),
      http.post('*/api/v1/auth/verify-email', async ({ request }) => {
        calls.push('verify')
        expect(await request.json()).toEqual({
          email: 'new-candidate@example.ru',
          code: '012345',
        })
        return HttpResponse.json(tokens)
      }),
      http.get('*/api/v1/users/me', () => {
        calls.push('me')
        return HttpResponse.json({
          id: 'new-candidate-id',
          email: 'new-candidate@example.ru',
          role: 'candidate',
          full_name: 'Анна Иванова',
          is_email_verified: true,
          created_at: '2026-10-08T00:00:00Z',
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

  it('keeps server registration field errors', async () => {
    server.use(
      http.post('*/api/v1/auth/register', () =>
        HttpResponse.json(
          {
            detail: [
              { loc: ['body', 'password'], msg: 'Пароль должен содержать буквы и цифры' },
            ],
          },
          { status: 422 },
        ),
      ),
    )

    const error = await registerCandidate({
      email: 'candidate@example.ru',
      password: '12345678',
    }).catch((caught: unknown) => caught)

    expect(error).toMatchObject({
      status: 422,
      fieldIssues: [{ field: 'password', message: 'Пароль должен содержать буквы и цифры' }],
    })
  })
})
