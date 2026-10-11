import { describe, expect, it } from 'vitest'

import { publicAchievementUrl } from '@/features/talent/model/candidate-presentation'
import { talentDefaults, talentFilterKey, talentRequest, talentSearchSchema } from '@/features/talent/model/talent-search'
import { removeTalentFilter, talentFilterSummary } from '@/features/talent/model/talent-filter-summary'
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

  it('starts with confirmed categories and lets employers explicitly include every status', () => {
    expect(talentRequest(talentDefaults).grade_status).toBe('confirmed')
    expect(talentRequest(talentSearchSchema.parse({ grade_status: 'all' })).grade_status).toBeUndefined()
    expect(removeTalentFilter(talentDefaults, 'grade_status').grade_status).toBe('all')
  })

  it('sends supported employer settings and clears only the selected condition', () => {
    const search = talentSearchSchema.parse({ industry: 'fintech', experience_min: 2, experience_max: 6, salary_max: 220000, city: 'Самара', offset: 12 })
    expect(talentRequest(search)).toMatchObject({ industry: 'fintech', experience_min: 2, experience_max: 6, salary_max: 220000 })
    expect(removeTalentFilter(search, 'salary_max')).toMatchObject({ salary_max: undefined, city: 'Самара', offset: 0 })
    expect(talentFilterSummary(search).some((filter) => filter.key === 'salary_max')).toBe(true)
    expect(talentFilterKey(search)).toBe(talentFilterKey({ ...search, offset: 24, sort: 'fsp', candidate: '00000000-0000-4000-8000-000000000001' }))
  })
})
