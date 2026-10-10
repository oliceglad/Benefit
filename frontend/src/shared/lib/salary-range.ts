export function publicationSalaryError(value: { salary_from?: number | null; salary_to?: number | null; currency?: string }): string | null {
  if (value.currency !== 'RUB') return 'Для публикации укажите зарплату в рублях (RUB).'
  if (value.salary_from == null || value.salary_to == null) return 'Для публикации заполните обе границы зарплаты: от и до.'
  if (![value.salary_from, value.salary_to].every((amount) => Number.isSafeInteger(amount) && amount >= 0 && amount <= 100_000_000)) return 'Укажите целые суммы от 0 до 100 000 000 ₽.'
  if (value.salary_from > value.salary_to) return 'Зарплата «до» должна быть не меньше зарплаты «от».'
  return null
}
