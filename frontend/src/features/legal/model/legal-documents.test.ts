import { describe, expect, it } from 'vitest'

import { legalText, personalDataConsentSections, privacyPolicySections, publicationConsentSections, termsSections } from '@/features/legal/model/legal-documents'

describe('legal documents', () => {
  it('describe Benefit instead of retaining foreign bot and game placeholders', () => {
    const text = legalText([...privacyPolicySections, ...termsSections, ...personalDataConsentSections, ...publicationConsentSections])

    expect(text).toContain('Benefit')
    expect(text).toContain('профил')
    expect(text).toContain('персональн')
    expect(text).not.toMatch(/Telegram-бот|Smart VPN|игровой валюты|\[название бота\]/i)
  })

  it('keeps separate consent and publication semantics explicit', () => {
    const text = legalText([...privacyPolicySections, ...termsSections, ...personalDataConsentSections, ...publicationConsentSections])

    expect(text).toContain('Отдельные согласия')
    expect(text).toContain('Полное заполнение профиля само по себе не означает публикацию')
    expect(text).toContain('Контактные данные кандидата не входят в общий поиск')
  })
})
