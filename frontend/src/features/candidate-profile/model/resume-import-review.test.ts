import { describe, expect, it } from 'vitest'

import { buildResumeReview } from './resume-import-review'
import { createTestProfile, testProfileDictionaries } from '@/test/fixtures/candidate'

const profile = createTestProfile()

describe('resume import review', () => {
  it('reflects fill, merge and keep rules without treating the preview as a profile update', () => {
    const sections = buildResumeReview({
      last_name: 'Петров',
      city: 'Самара',
      skills: [
        { name: 'typescript', level: 'expert', years: 10 },
        { name: 'React', level: 'advanced', years: 4 },
      ],
      experience: [{ company: 'Other', position: 'Lead' }],
      education: [{ institution: 'Самарский университет' }],
    }, profile, testProfileDictionaries)
    const fields = sections.flatMap((section) => section.fields)

    expect(fields.find((field) => field.key === 'last_name')?.effect).toBe('replace')
    expect(fields.find((field) => field.key === 'city')?.effect).toBe('fill')
    expect(fields.find((field) => field.key === 'skills')?.effect).toBe('merge')
    expect(fields.find((field) => field.key === 'experience')?.effect).toBe('replace')
    expect(fields.find((field) => field.key === 'education')?.effect).toBe('fill')
    expect(profile).toMatchObject({ last_name: 'Иванов', city: null, skills: [{ name: 'TypeScript' }] })
  })

  it('does not expose protected or unknown draft fields as supported import operations', () => {
    const fields = buildResumeReview({
      verified_grade: 'senior',
      status: 'published',
      consents: ['personal_data'],
    }, profile, testProfileDictionaries).flatMap((section) => section.fields)

    expect(fields).toHaveLength(0)
  })
})
