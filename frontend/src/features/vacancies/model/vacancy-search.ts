import { z } from 'zod'
import { Grade, VacancyStatus, WorkFormat } from '@/shared/api/generated/employers/models'

export const vacancySearchSchema = z.object({
  q: z.string().trim().max(100).catch('').optional(),
  city: z.string().trim().max(100).catch('').optional(),
  grade: z.enum(Grade).optional().catch(undefined),
  work_format: z.enum(WorkFormat).optional().catch(undefined),
  status: z.enum(VacancyStatus).optional().catch(undefined),
  salary_min: z.coerce.number().int().min(0).max(100_000_000).optional().catch(undefined),
  offset: z.coerce.number().int().min(0).max(1_000_000).catch(0).default(0),
})
export type VacancySearch = z.infer<typeof vacancySearchSchema>
export const vacancyPageSize = 12
export const gradeLabels = { intern: 'Стажёр', junior: 'Junior', middle: 'Middle', senior: 'Senior', lead: 'Lead' }
export const formatLabels = { remote: 'Удалённо', hybrid: 'Гибрид', office: 'Офис' }
export const vacancyStatusLabels = { draft: 'Черновик', published: 'Опубликована', closed: 'Закрыта' }

export function salaryLabel(from?: number | null, to?: number | null, currency = 'RUB'): string {
  const money = (value: number) => new Intl.NumberFormat('ru-RU').format(value)
  const unit = currency === 'RUB' ? '₽' : currency
  if (from != null && to != null) return `${money(from)} – ${money(to)} ${unit}`
  if (from != null) return `от ${money(from)} ${unit}`
  if (to != null) return `до ${money(to)} ${unit}`
  return 'Зарплата не указана'
}
