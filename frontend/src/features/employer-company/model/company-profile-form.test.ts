import { describe, expect, it } from 'vitest'

import {
  companyProfileFormValues,
  companyProfilePayload,
  splitTechStack,
} from '@/features/employer-company/model/company-profile-form'
import type { CompanyResponse } from '@/shared/api/generated/employers/models'

const company: CompanyResponse = {
  id: 'company-1',
  owner_id: 'employer-1',
  name: 'Benefit',
  legal_name: null,
  inn: null,
  industry: 'ai',
  description: 'Платформа найма',
  website: null,
  city: null,
  size: null,
  tech_stack: ['TypeScript', 'Python'],
  contact_name: null,
  contact_email: null,
  contact_phone: null,
  telegram: null,
  created_at: '2026-10-11T10:00:00Z',
  updated_at: '2026-10-11T10:00:00Z',
}

describe('company profile form model', () => {
  it('keeps every server field when building a full PUT payload', () => {
    const values = companyProfileFormValues(company)
    values.city = ' Самара '
    values.tech_stack = 'TypeScript, python\nPostgreSQL'

    expect(companyProfilePayload(values)).toEqual({
      name: 'Benefit',
      legal_name: null,
      inn: null,
      industry: 'ai',
      description: 'Платформа найма',
      website: null,
      city: 'Самара',
      size: null,
      tech_stack: ['TypeScript', 'python', 'PostgreSQL'],
      contact_name: null,
      contact_email: null,
      contact_phone: null,
      telegram: null,
    })
  })

  it('normalizes and deduplicates technologies without changing their order', () => {
    expect(splitTechStack(' Python, python\nPostgreSQL, , Docker ')).toEqual([
      'Python',
      'PostgreSQL',
      'Docker',
    ])
  })
})
