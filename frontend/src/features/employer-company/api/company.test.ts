import { describe, expect, it } from 'vitest'

import { employerCompanyQueryKey } from '@/features/employer-company/api/company'

describe('employer company query key', () => {
  it('isolates private company data by account', () => {
    expect(employerCompanyQueryKey('employer-a')).toEqual([
      'employer',
      'employer-a',
      'company',
    ])
    expect(employerCompanyQueryKey('employer-a')).not.toEqual(
      employerCompanyQueryKey('employer-b'),
    )
  })
})
