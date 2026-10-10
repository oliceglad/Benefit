import { z } from 'zod'

import { EmploymentType, Grade, ITRole, WorkFormat, type VacancyIn, type VacancyResponse } from '@/shared/api/generated/employers/models'

const salary = z.string().trim().refine((value) => !value || (/^\d+$/.test(value) && Number.isSafeInteger(Number(value)) && Number(value) <= 100_000_000), 'Укажите целую сумму от 0 до 100 000 000')

export function parseSkills(value: string): string[] {
  return [...new Set(value.split(/[,;\n]/).map((skill) => skill.trim()).filter(Boolean))]
}

export const vacancyFormSchema = z.object({
  title: z.string().trim().min(1, 'Укажите название вакансии').max(200, 'Не более 200 символов'),
  description: z.string().trim().min(1, 'Расскажите о работе').max(8000, 'Не более 8000 символов'),
  specialization: z.enum(ITRole),
  grade: z.enum(Grade),
  work_format: z.union([z.enum(WorkFormat), z.literal('')]),
  employment_type: z.union([z.enum(EmploymentType), z.literal('')]),
  city: z.string().trim().max(100, 'Не более 100 символов'),
  currency: z.string().trim().toUpperCase().regex(/^[A-Z]{3}$/, 'Трёхбуквенный код, например RUB'),
  salary_from: salary,
  salary_to: salary,
  skills: z.string().refine((value) => parseSkills(value).length <= 30, 'Не более 30 навыков')
    .refine((value) => parseSkills(value).every((skill) => skill.length <= 64), 'Название навыка — не более 64 символов'),
}).refine((value) => !value.salary_from || !value.salary_to || Number(value.salary_from) <= Number(value.salary_to), {
  path: ['salary_to'], message: 'Верхняя граница должна быть не меньше нижней',
})

export type VacancyFormValues = z.infer<typeof vacancyFormSchema>

export function vacancyFormValues(vacancy?: VacancyResponse): VacancyFormValues {
  return {
    title: vacancy?.title ?? '', description: vacancy?.description ?? '',
    specialization: vacancy?.specialization ?? 'backend', grade: vacancy?.grade ?? 'middle',
    work_format: vacancy?.work_format ?? '', employment_type: vacancy?.employment_type ?? '',
    city: vacancy?.city ?? '', currency: vacancy?.currency ?? 'RUB',
    salary_from: vacancy?.salary_from?.toString() ?? '', salary_to: vacancy?.salary_to?.toString() ?? '',
    skills: vacancy?.skills?.join(', ') ?? '',
  }
}

export function vacancyPayload(values: VacancyFormValues, needId?: string | null): VacancyIn {
  return {
    ...values,
    title: values.title.trim(), description: values.description.trim(),
    city: values.city.trim() || null, currency: values.currency.trim().toUpperCase(),
    salary_from: values.salary_from ? Number(values.salary_from) : null,
    salary_to: values.salary_to ? Number(values.salary_to) : null,
    work_format: values.work_format || null, employment_type: values.employment_type || null,
    skills: parseSkills(values.skills), need_id: needId ?? null,
  }
}

export const specializationLabels: Record<ITRole, string> = {
  backend: 'Backend-разработка', frontend: 'Frontend-разработка', fullstack: 'Fullstack-разработка',
  mobile: 'Мобильная разработка', devops: 'DevOps', qa: 'Тестирование', qa_automation: 'Автоматизация тестирования',
  data_scientist: 'Data Science', ml_engineer: 'Machine Learning', data_engineer: 'Инженерия данных',
  data_analyst: 'Аналитика данных', system_analyst: 'Системная аналитика', business_analyst: 'Бизнес-аналитика',
  product_manager: 'Управление продуктом', project_manager: 'Управление проектами', designer: 'Дизайн',
  gamedev: 'Разработка игр', security: 'Информационная безопасность', embedded: 'Embedded-разработка',
  dba: 'Администрирование баз данных', team_lead: 'Руководство командой', architect: 'Архитектура',
}
export const employmentLabels = {
  full_time: 'Полная занятость', part_time: 'Частичная занятость', project: 'Проектная работа', internship: 'Стажировка',
}
