import { describe, expect, it } from 'vitest'

import { registerSchema } from '@/features/auth/model/register-schema'

describe('registerSchema', () => {
  it('accepts a candidate password and Russian email domain', () => {
    expect(
      registerSchema.safeParse({
        fullName: 'Анна Иванова',
        email: 'Candidate@Example.RU',
        password: 'Пароль123',
      }).success,
    ).toBe(true)
  })

  it('rejects unsupported domains and passwords without letters', () => {
    const result = registerSchema.safeParse({
      fullName: '',
      email: 'candidate@example.com',
      password: '12345678',
    })

    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues.map((issue) => issue.path[0])).toEqual(
        expect.arrayContaining(['email', 'password']),
      )
    }
  })
})
