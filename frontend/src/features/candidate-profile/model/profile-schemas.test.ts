import { describe, expect, it } from 'vitest'

import { experienceSchema } from '@/features/candidate-profile/model/profile-schemas'

const experienceEntry = {
  company: 'Benefit',
  position: 'Разработчик',
  startDate: '2020-06',
  endDate: '',
  current: true,
  city: '',
  description: '',
  achievements: '',
  technologies: '',
}

const formValues = {
  experience: [experienceEntry],
  education: [],
  courses: [],
  projects: [],
}

describe('experienceSchema', () => {
  it('не требует дату окончания для текущей работы', () => {
    expect(experienceSchema.safeParse(formValues).success).toBe(true)
  })

  it('игнорирует незавершённое значение окончания для текущей работы', () => {
    expect(experienceSchema.safeParse({
      ...formValues,
      experience: [{ ...experienceEntry, endDate: '2024-' }],
    }).success).toBe(true)
  })

  it('требует полный месяц окончания для завершённой работы', () => {
    expect(experienceSchema.safeParse({
      ...formValues,
      experience: [{ ...experienceEntry, current: false }],
    }).success).toBe(false)
  })
})
