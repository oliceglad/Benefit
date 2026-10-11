import { describe, expect, it } from 'vitest'

import { candidateVerifiedSkills, publicAchievementUrl } from './candidate-presentation'

describe('verified candidate evidence', () => {
  it('reads main’s verified skill records without confusing them with self-declared skills', () => {
    expect(candidateVerifiedSkills([
      { skill: ' SQL ', level: 'advanced', title: 'Продвинутый', percent: 92 },
      { name: 'Python', level: 'expert', years: 5 },
      null,
      { skill: '' },
    ])).toEqual([{ skill: 'SQL', level: 'advanced', title: 'Продвинутый', percent: 92 }])
  })

  it('supports an older API without per-skill test results', () => {
    expect(candidateVerifiedSkills()).toEqual([])
  })

  it('keeps a verified skill but hides an invalid percentage', () => {
    expect(candidateVerifiedSkills([{ skill: 'Python', percent: 150 }])).toEqual([
      { skill: 'Python', percent: null },
    ])
  })

  it('rejects executable and malformed achievement links', () => {
    for (const value of ['javascript:alert(1)', 'data:text/html,test', '/private', 'broken url']) {
      expect(publicAchievementUrl(value)).toBeNull()
    }
    expect(publicAchievementUrl('https://fsp.example.test/result/1')).toBe('https://fsp.example.test/result/1')
  })
})
