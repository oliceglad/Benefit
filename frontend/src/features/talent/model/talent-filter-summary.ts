import { formatLabels, gradeLabels, industryLabels, roleLabels, talentSearchSchema, type TalentSearch } from './talent-search'

export function talentFilterSummary(search: TalentSearch) {
  const filters: { key: keyof TalentSearch; label: string }[] = []
  if (search.q) filters.push({ key: 'q', label: `Поиск: ${search.q}` })
  if (search.specialization) filters.push({ key: 'specialization', label: roleLabels[search.specialization] })
  if (search.grade?.length) filters.push({ key: 'grade', label: search.grade.map((grade) => gradeLabels[grade]).join(', ') })
  if (search.grade_status !== 'all') filters.push({ key: 'grade_status', label: search.grade_status === 'confirmed' ? 'Грейд подтверждён тестом' : 'Грейд ещё не подтверждён' })
  if (search.skills) filters.push({ key: 'skills', label: `${search.skills_mode === 'all' ? 'Все навыки' : 'Любой навык'}: ${search.skills}` })
  if (search.fsp) filters.push({ key: 'fsp', label: search.fsp === 'with' ? 'Есть достижения ФСП' : 'Без доступных достижений ФСП' })
  if (search.industry) filters.push({ key: 'industry', label: industryLabels[search.industry] })
  if (search.city) filters.push({ key: 'city', label: search.city })
  if (search.work_format) filters.push({ key: 'work_format', label: formatLabels[search.work_format] })
  if (search.experience_min != null) filters.push({ key: 'experience_min', label: `Опыт от ${search.experience_min} лет` })
  if (search.experience_max != null) filters.push({ key: 'experience_max', label: `Опыт до ${search.experience_max} лет` })
  if (search.salary_max != null) filters.push({ key: 'salary_max', label: `Ожидания до ${new Intl.NumberFormat('ru-RU').format(search.salary_max)} ₽` })
  if (search.active_only) filters.push({ key: 'active_only', label: 'Активны за 30 дней' })
  if (search.include_not_looking) filters.push({ key: 'include_not_looking', label: 'Включая тех, кто не ищет работу' })
  return filters
}

export function removeTalentFilter(search: TalentSearch, key: keyof TalentSearch): TalentSearch {
  return talentSearchSchema.parse({ ...search, [key]: key === 'grade_status' ? 'all' : undefined, offset: 0, candidate: undefined })
}
