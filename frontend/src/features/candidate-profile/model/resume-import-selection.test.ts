import { describe, expect, it } from 'vitest'

import { buildSelectedResumeUpdate, selectableResumeFields } from './resume-import-selection'
import { createTestProfile } from '@/test/fixtures/candidate'

describe('selected resume import', () => {
  it('builds a PATCH from selected fields only and merges catalog skills without duplicates', () => {
    const draft = {
      last_name: 'Петров',
      city: 'Самара',
      skills: [{ name: 'typescript', level: 'expert', years: 8 }, { name: 'React', level: 'advanced', years: 4 }],
      experience: [{ company: 'Новая компания', position: 'Lead', start_date: '2025-01-01' }],
    }

    const update = buildSelectedResumeUpdate(draft, createTestProfile(), new Set(['last_name', 'skills']))

    expect(update).toEqual({
      last_name: 'Петров',
      skills: [
        { name: 'TypeScript', level: 'advanced', years: 3 },
        { name: 'React', level: 'advanced', years: 4 },
      ],
    })
    expect(update).not.toHaveProperty('city')
    expect(update).not.toHaveProperty('experience')
  })

  it('never exposes protected server fields as selectable', () => {
    expect(selectableResumeFields({
      first_name: 'Иван',
      status: 'published',
      verified_grade: 'lead',
      consents: ['personal_data'],
    })).toEqual(['first_name'])
  })
})
