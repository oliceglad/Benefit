import { describe, expect, it } from 'vitest'

import { invitationFormSchema, invitationPayload } from './invitation-form'
import { publicationSalaryError } from '@/shared/lib/salary-range'

const values = { vacancyId: '', title: '  Python-разработчик  ', companyName: 'Тестовая компания', salaryFrom: '180000', salaryTo: '240000', workFormat: 'remote' as const, city: '', message: '  Приглашаем обсудить команду.  ' }

describe('Обязательные условия предложения', () => {
  it('не допускает отправку без двух границ, с перевёрнутой вилкой или дробными суммами', () => {
    for (const patch of [{ salaryFrom: '' }, { salaryTo: '' }, { salaryFrom: '250000' }, { salaryTo: '240000.5' }, { salaryTo: '-1' }]) {
      expect(invitationFormSchema.safeParse({ ...values, ...patch }).success).toBe(false)
    }
  })

  it('создаёт персональное предложение в рублях без обязательной вакансии', () => {
    const parsed = invitationFormSchema.parse(values)
    const payload = invitationPayload('6d0abd13-fbb2-44ce-b679-dcbd4844f0c4', parsed)
    expect(payload.vacancy).toMatchObject({ vacancy_id: null, title: 'Python-разработчик', salary_from: 180000, salary_to: 240000, currency: 'RUB', work_format: 'remote', city: null })
    expect(payload.message).toBe('Приглашаем обсудить команду.')
  })

  it('разрешает публикацию только с корректной вилкой в RUB', () => {
    expect(publicationSalaryError({ salary_from: null, salary_to: null, currency: 'RUB' })).not.toBeNull()
    expect(publicationSalaryError({ salary_from: 180000, salary_to: 240000, currency: 'USD' })).not.toBeNull()
    expect(publicationSalaryError({ salary_from: 250000, salary_to: 240000, currency: 'RUB' })).not.toBeNull()
    expect(publicationSalaryError({ salary_from: 180000, salary_to: 240000, currency: 'RUB' })).toBeNull()
  })
})
