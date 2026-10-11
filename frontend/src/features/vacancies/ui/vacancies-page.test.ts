import { describe, expect, it } from 'vitest'

import { employerVacancyEmptyCopy } from '@/features/vacancies/model/employer-vacancy-empty'

describe('employer vacancy empty states', () => {
  it('offers creation only when the employer has no vacancies at all', () => {
    expect(employerVacancyEmptyCopy(0, undefined, false)).toEqual({
      title: 'Пока нет вакансий',
      description: 'Создайте первую вакансию, сохраните её как черновик и опубликуйте после проверки.',
    })
  })

  it('explains an empty search independently of the total vacancy count', () => {
    expect(employerVacancyEmptyCopy(7, undefined, true).title).toBe('По этим условиям вакансии не найдены')
  })

  it('names the selected server status when its tab is empty', () => {
    expect(employerVacancyEmptyCopy(7, 'closed', false).title).toBe('Нет вакансий со статусом «закрыта»')
  })
})
