import { vacancyStatusLabels, type VacancySearch } from '@/features/vacancies/model/vacancy-search'

export function employerVacancyEmptyCopy(allCount: number, status: VacancySearch['status'], hasFilters: boolean) {
  const statusName = status ? vacancyStatusLabels[status].toLocaleLowerCase('ru-RU') : ''
  const title = allCount === 0
    ? 'Пока нет вакансий'
    : hasFilters
      ? 'По этим условиям вакансии не найдены'
      : status
        ? `Нет вакансий со статусом «${statusName}»`
        : 'На этой странице вакансий нет'
  const description = allCount === 0
    ? 'Создайте первую вакансию, сохраните её как черновик и опубликуйте после проверки.'
    : hasFilters
      ? 'Измените запрос или сбросьте фильтры.'
      : status
        ? 'Выберите другой статус или создайте новую вакансию.'
        : 'Вернитесь на предыдущую страницу.'
  return { title, description }
}
