import { describe, expect, it } from 'vitest'

import { publicAchievementUrl } from '@/features/talent/model/candidate-presentation'
import { talentRequest, talentSearchSchema } from '@/features/talent/model/talent-search'
import { getSearchCandidatesApiV1TalentCandidatesGetUrl } from '@/shared/api/generated/talent/talent'

describe('candidate bank request', () => {
  it('preserves both FSP filter values and sends repeated skills/grades without UI state', () => {
    const search = talentSearchSchema.parse({ fsp: 'with', grade: ['middle', 'senior'], skills: 'React, TypeScript, React', candidate: '00000000-0000-4000-8000-000000000001', need: '00000000-0000-4000-8000-000000000002', hide_contacted: true })
    const params = new URL(getSearchCandidatesApiV1TalentCandidatesGetUrl(talentRequest(search)), 'https://benefit.example.test').searchParams
    expect(params.get('has_fsp')).toBe('true')
    expect(params.getAll('grade')).toEqual(['middle', 'senior'])
    expect(params.getAll('skills')).toEqual(['React', 'TypeScript'])
    expect(params.has('candidate')).toBe(false)
    expect(params.has('need')).toBe(false)
    expect(params.has('hide_contacted')).toBe(false)
    expect(params.has('fsp')).toBe(false)
    expect(talentRequest(talentSearchSchema.parse({ fsp: 'without' })).has_fsp).toBe(false)
    expect(talentRequest(talentSearchSchema.parse({})).has_fsp).toBeUndefined()
  })

  it('rejects executable achievement links and invalid search values', () => {
    expect(publicAchievementUrl('javascript:alert(1)')).toBeNull()
    expect(publicAchievementUrl('data:text/html,test')).toBeNull()
    expect(publicAchievementUrl('https://fsp.example.test/results')).toBe('https://fsp.example.test/results')
    expect(talentSearchSchema.parse({ grade: 'senior', experience_min: '', fsp: 'invalid', offset: -1 })).toMatchObject({ grade: ['senior'], experience_min: undefined, fsp: undefined, offset: 0 })
  })
})
