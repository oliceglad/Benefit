import { z } from 'zod'

import { Grade, ITRole, WorkFormat, type NeedIn, type NeedResponse } from '@/shared/api/generated/employers/models'

export function needSkills(value: string): string[] {
  const seen = new Set<string>()
  return value.split(/[,;\n]/).map((skill) => skill.trim()).filter((skill) => {
    if (!skill || seen.has(skill.toLocaleLowerCase())) return false
    seen.add(skill.toLocaleLowerCase())
    return true
  })
}

const integerText = (max: number, required = false) => z.string().trim().refine(
  (value) => !value ? !required : /^\d+$/.test(value) && Number(value) <= max,
  `Укажите целое число от ${required ? 1 : 0} до ${max}`,
)
const skillsText = z.string()
  .refine((value) => needSkills(value).length <= 30, 'Не более 30 навыков')
  .refine((value) => needSkills(value).every((skill) => skill.length <= 64), 'Навык — не более 64 символов')

export const needFormSchema = z.object({
  title: z.string().trim().min(1, 'Укажите название потребности').max(200, 'Не более 200 символов'),
  team_description: z.string().trim().min(1, 'Расскажите о задачах команды').max(8000, 'Не более 8000 символов'),
  specialization: z.enum(ITRole), grade: z.enum(Grade),
  required_skills: skillsText.refine((value) => needSkills(value).length > 0, 'Укажите хотя бы один обязательный навык'),
  optional_skills: skillsText, work_formats: z.array(z.enum(WorkFormat)).max(3),
  city: z.string().trim().max(100, 'Не более 100 символов'),
  headcount: integerText(100, true).refine((value) => Number(value) >= 1, 'Нужен хотя бы один сотрудник'),
  salary_from: integerText(100_000_000), salary_to: integerText(100_000_000),
  currency: z.string().regex(/^[A-Z]{3}$/, 'Трёхбуквенный код валюты'),
  require_confirmed_grade: z.boolean(), strict_skills: z.boolean(),
  grade_tolerance: z.number().int().min(0).max(4), min_experience_months: integerText(600),
  hard_budget: z.boolean(), strict_format: z.boolean(),
}).superRefine((value, context) => {
  if (value.salary_from && value.salary_to && Number(value.salary_from) > Number(value.salary_to)) {
    context.addIssue({ code: 'custom', path: ['salary_to'], message: 'Верхняя граница должна быть не меньше нижней' })
  }
  if (value.hard_budget && (!value.salary_to || Number(value.salary_to) === 0)) {
    context.addIssue({ code: 'custom', path: ['salary_to'], message: 'Для строгого бюджета укажите верхнюю границу больше нуля' })
  }
  if (value.strict_format && value.work_formats.length === 0) {
    context.addIssue({ code: 'custom', path: ['work_formats'], message: 'Выберите хотя бы один формат для строгого отбора' })
  }
})

export type NeedFormValues = z.infer<typeof needFormSchema>

export function needFormValues(need?: NeedResponse): NeedFormValues {
  return {
    title: need?.title ?? '', team_description: need?.team_description ?? '',
    specialization: need?.specialization ?? 'backend', grade: need?.grade ?? 'middle',
    required_skills: need?.required_skills.join(', ') ?? '', optional_skills: need?.optional_skills?.join(', ') ?? '',
    work_formats: need?.work_formats ?? [], city: need?.city ?? '', headcount: String(need?.headcount ?? 1),
    salary_from: need?.salary_from?.toString() ?? '', salary_to: need?.salary_to?.toString() ?? '', currency: need?.currency ?? 'RUB',
    require_confirmed_grade: need?.require_confirmed_grade ?? false, strict_skills: need?.strict_skills ?? false,
    grade_tolerance: need?.grade_tolerance ?? 1, min_experience_months: need?.min_experience_months?.toString() ?? '',
    hard_budget: need?.hard_budget ?? false, strict_format: need?.strict_format ?? false,
  }
}

export function needPayload(values: NeedFormValues): NeedIn {
  return {
    ...values,
    required_skills: needSkills(values.required_skills), optional_skills: needSkills(values.optional_skills),
    headcount: Number(values.headcount), city: values.city || null,
    salary_from: values.salary_from ? Number(values.salary_from) : null,
    salary_to: values.salary_to ? Number(values.salary_to) : null,
    min_experience_months: values.min_experience_months ? Number(values.min_experience_months) : null,
  }
}
