import { describe, expect, it } from 'vitest'

import {
  formatPhone,
  formatSalary,
  normalizePhone,
  normalizeTelegram,
  parseLocalizedNumber,
  parseSalary,
} from '@/features/candidate-profile/model/form-values'

describe('contact values', () => {
  it.each([
    ['8 (999) 123-45-67', '+79991234567'],
    ['+7 (999) 123-45-67', '+79991234567'],
    ['+49 30 123456', '+4930123456'],
    ['', ''],
  ])('normalizes phone %s for the backend', (input, expected) => {
    expect(normalizePhone(input)).toBe(expected)
  })

  it('formats only complete Russian numbers and preserves other input', () => {
    expect(formatPhone('+79991234567')).toBe('+7 (999) 123-45-67')
    expect(formatPhone('+4930123456')).toBe('+4930123456')
    expect(formatPhone('+7 999')).toBe('+7 999')
  })

  it.each([
    ['@benefit_user', '@benefit_user'],
    ['https://t.me/benefit_user', '@benefit_user'],
    ['t.me/benefit_user', '@benefit_user'],
    ['@@benefit_user', '@@benefit_user'],
    ['', ''],
  ])('normalizes supported Telegram value %s once', (input, expected) => {
    expect(normalizeTelegram(input)).toBe(expected)
  })
})

describe('numeric form values', () => {
  it('supports comma in fractional experience', () => {
    expect(parseLocalizedNumber('1,5')).toBe(1.5)
  })

  it('formats salary without changing its numeric value', () => {
    const formatted = formatSalary('180000')
    expect(formatted.replace(/\s/g, '')).toBe('180000')
    expect(parseSalary(formatted)).toBe(180000)
  })
})
