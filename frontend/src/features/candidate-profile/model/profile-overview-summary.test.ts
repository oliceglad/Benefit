import { describe, expect, it } from 'vitest'

import { buildProfileOverviewSummary } from './profile-overview-summary'
import { createTestProfile, testProfileDictionaries } from '@/test/fixtures/candidate'

const dictionaries = {
  ...testProfileDictionaries,
  grades: [{ id: 'middle', title: 'Middle' }],
  work_formats: [{ id: 'remote', title: 'Удалённо' }],
  job_search_statuses: [{ id: 'open', title: 'Открыт к предложениям' }],
}

describe('mobile profile overview summaries', () => {
  it('describes saved values without declaring a partially filled section complete', () => {
    const summary = buildProfileOverviewSummary(createTestProfile({
      first_name: 'Иван',
      last_name: null,
      birth_date: null,
      city: null,
      phone: '+79991234567',
      contact_email: 'candidate@example.com',
      telegram: null,
    }), dictionaries)

    expect(summary.personal).toBe('Указано: имя')
    expect(summary.contacts).toBe('Телефон и почта указаны')
    expect(summary.specialization).toBe('Разработчик · грейд Middle')
  })

  it('limits the skills preview and uses real list counts', () => {
    const summary = buildProfileOverviewSummary(createTestProfile({
      skills: [{ name: 'TypeScript' }, { name: 'React' }, { name: 'PostgreSQL' }],
      experience: [createTestProfile().experience[0]],
      projects: [{ name: 'Benefit' }, { name: 'Портфолио' }],
      work_formats: ['remote'],
      salary_from: 180000,
    }), dictionaries)

    expect(summary.skills).toBe('TypeScript, React · ещё 1')
    expect(summary.experience).toBe('1 место работы · 2 проекта')
    expect(summary.preferences).toBe('Удалённо · 180 000 ₽')
  })

  it('keeps consent and publication states separate', () => {
    const summary = buildProfileOverviewSummary(createTestProfile({ status: 'published' }), dictionaries, [
      { type: 'personal_data', title: 'Данные', document_url: 'https://example.com', required_version: '1', granted: true, granted_version: '1', granted_at: '2026-10-09T10:00:00Z' },
      { type: 'publication', title: 'Публикация', document_url: 'https://example.com', required_version: '1', granted: false, granted_version: null, granted_at: null },
    ])

    expect(summary.consents).toBe('Принято 1 из 2 · профиль опубликован')
  })
})
