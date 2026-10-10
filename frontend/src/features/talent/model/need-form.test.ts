import { describe, expect, it } from 'vitest'

import { needFormSchema, needFormValues, needPayload } from '@/features/talent/model/need-form'
import type { NeedIn, NeedResponse } from '@/shared/api/generated/employers/models'

describe('employer need form', () => {
  const saved: NeedResponse = {
    id: '00000000-0000-4000-8000-000000000001', company_id: '00000000-0000-4000-8000-000000000002',
    status: 'active', created_at: '2026-10-11T10:00:00Z', updated_at: '2026-10-11T10:00:00Z',
    title: 'Backend', team_description: 'Развивать API команды', specialization: 'backend', grade: 'senior',
    required_skills: ['Python', 'PostgreSQL'], optional_skills: ['Docker'], work_formats: ['remote', 'hybrid'],
    city: 'Самара', headcount: 2, salary_from: 150000, salary_to: 250000, currency: 'USD',
    require_confirmed_grade: true, strict_skills: true, grade_tolerance: 2, min_experience_months: 36,
    hard_budget: true, strict_format: true,
  }

  it('preserves every saved requirement and currency when editing', () => {
    const expected: NeedIn = {
      title: saved.title, team_description: saved.team_description, specialization: saved.specialization, grade: saved.grade,
      required_skills: saved.required_skills, optional_skills: saved.optional_skills, work_formats: saved.work_formats,
      city: saved.city, headcount: saved.headcount, salary_from: saved.salary_from, salary_to: saved.salary_to, currency: saved.currency,
      require_confirmed_grade: true, strict_skills: true, grade_tolerance: 2, min_experience_months: 36, hard_budget: true, strict_format: true,
    }
    expect(needPayload(needFormSchema.parse(needFormValues(saved)))).toEqual(expected)
  })

  it('deduplicates skills and explicitly clears optional requirements', () => {
    const values = needFormSchema.parse({
      ...needFormValues(saved), required_skills: ' Python, python; PostgreSQL\nPostgreSQL ', optional_skills: '',
      city: ' ', salary_from: '', salary_to: '', min_experience_months: '', hard_budget: false, strict_format: false, work_formats: [],
    })
    expect(needPayload(values)).toMatchObject({
      required_skills: ['Python', 'PostgreSQL'], optional_skills: [], city: null, salary_from: null, salary_to: null,
      min_experience_months: null, work_formats: [], hard_budget: false, strict_format: false,
    })
  })

  it('rejects inverted budgets and strict conditions without their required values', () => {
    const invalid = needFormSchema.safeParse({ ...needFormValues(saved), salary_from: '300000', salary_to: '200000', work_formats: [] })
    expect(invalid.success).toBe(false)
    if (!invalid.success) expect(invalid.error.issues.map((issue) => issue.path[0])).toEqual(expect.arrayContaining(['salary_to', 'work_formats']))
    expect(needFormSchema.safeParse({ ...needFormValues(saved), salary_to: '' }).success).toBe(false)
    expect(needFormSchema.safeParse({ ...needFormValues(saved), required_skills: ' , ' }).success).toBe(false)
  })
})
