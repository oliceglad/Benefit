import { describe, expect, it } from 'vitest'

import { buildExperienceUpdate, buildSkillsUpdate, withoutSelectedSkills } from './profile-updates'

describe('candidate profile section updates', () => {
  it('builds a skills-only PATCH and does not include neighbouring profile fields', () => {
    const update = buildSkillsUpdate({
      skills: [{ name: 'TypeScript', level: 'advanced', years: '5' }],
      softSkills: ['Работа в команде'],
      languages: [{ language: 'Английский', level: 'B2' }],
    })

    expect(update).toEqual({
      skills: [{ name: 'TypeScript', level: 'advanced', years: 5 }],
      soft_skills: ['Работа в команде'],
      languages: [{ language: 'Английский', level: 'B2' }],
    })
    expect(update).not.toHaveProperty('contacts')
    expect(update).not.toHaveProperty('experience')
  })

  it('serializes edited and deleted repeated records as complete replacement arrays', () => {
    const update = buildExperienceUpdate({
      experience: [{ company: 'Benefit', position: 'Разработчик', startDate: '2024-01', endDate: '', current: true, city: '', description: '', achievements: 'Запуск профиля\nДоступность', technologies: 'React, TypeScript' }],
      education: [],
      courses: [],
      projects: [{ name: 'Профиль', role: '', description: '', url: '', technologies: 'React' }],
    })

    expect(update.experience).toEqual([{ company: 'Benefit', position: 'Разработчик', start_date: '2024-01-01', end_date: null, city: null, description: null, achievements: ['Запуск профиля', 'Доступность'], technologies: ['React', 'TypeScript'] }])
    expect(update.education).toEqual([])
    expect(update.courses).toEqual([])
    expect(update.projects).toEqual([{ name: 'Профиль', role: null, description: null, url: null, technologies: ['React'] }])
  })

  it('excludes duplicate skill suggestions case-insensitively', () => {
    expect(withoutSelectedSkills(['TypeScript', 'React', 'Python'], ['typescript', 'REACT'])).toEqual(['Python'])
  })
})
