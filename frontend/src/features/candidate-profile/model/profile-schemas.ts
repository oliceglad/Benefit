import { z } from 'zod'

import { parseLocalizedNumber, salaryDigits } from '@/features/candidate-profile/model/form-values'

const optionalShortText = z.string().trim().max(200, 'Не более 200 символов')
const optionalLongText = z.string().trim().max(4000, 'Не более 4000 символов')
const optionalUrl = z.string().trim().refine(
  (value) => value === '' || z.url().safeParse(value).success,
  'Введите корректную ссылку',
)

function validBirthDate(value: string): boolean {
  if (value === '') return true
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const birthDate = new Date(`${value}T00:00:00`)
  if (Number.isNaN(birthDate.getTime())) return false
  const today = new Date()
  let age = today.getFullYear() - birthDate.getFullYear()
  if (
    today.getMonth() < birthDate.getMonth()
    || (today.getMonth() === birthDate.getMonth() && today.getDate() < birthDate.getDate())
  ) age -= 1
  return age >= 14 && age <= 100
}

export const personalSchema = z.object({
  lastName: z.string().trim().max(100, 'Не более 100 символов'),
  firstName: z.string().trim().max(100, 'Не более 100 символов'),
  middleName: z.string().trim().max(100, 'Не более 100 символов'),
  birthDate: z.string().refine(validBirthDate, 'Возраст должен быть от 14 до 100 лет'),
  city: z.string().trim().max(100, 'Не более 100 символов'),
  relocationReady: z.boolean(),
})

export const gradeSchema = z.enum(['intern', 'junior', 'middle', 'senior', 'lead'])
export const roleSchema = z.enum([
  'backend', 'frontend', 'fullstack', 'mobile', 'devops', 'qa', 'qa_automation',
  'data_scientist', 'ml_engineer', 'data_engineer', 'data_analyst', 'system_analyst',
  'business_analyst', 'product_manager', 'project_manager', 'designer', 'gamedev',
  'security', 'embedded', 'dba', 'team_lead', 'architect',
])

export const specializationSchema = z.object({
  headline: optionalShortText,
  about: optionalLongText,
  grade: z.union([gradeSchema, z.literal('')]),
  roles: z.array(roleSchema).max(5, 'Можно выбрать не более пяти ролей'),
})

export const skillLevelSchema = z.enum(['basic', 'intermediate', 'advanced', 'expert'])
export const languageLevelSchema = z.enum(['A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'native'])

export const skillsSchema = z.object({
  skills: z.array(z.object({
    name: z.string().min(1),
    level: z.union([skillLevelSchema, z.literal('')]),
    years: z.string().refine((value) => {
      if (value === '') return true
      if (!/^(?:\d+(?:[.,]\d*)?|[.,]\d+)$/.test(value)) return false
      const parsed = parseLocalizedNumber(value)
      return Number.isFinite(parsed) && parsed >= 0 && parsed <= 50
    }, 'Укажите стаж от 0 до 50 лет, например 1,5'),
  })).max(100),
  softSkills: z.array(z.string()).max(30),
  languages: z.array(z.object({
    language: z.string().min(1, 'Выберите язык'),
    level: languageLevelSchema,
  })).max(15),
})

const monthSchema = z.string().regex(/^\d{4}-\d{2}$/, 'Выберите месяц')
const optionalYearSchema = z.string().refine((value) => {
  if (value === '') return true
  const year = Number(value)
  return Number.isInteger(year) && year >= 1950 && year <= 2100
}, 'Год должен быть от 1950 до 2100')

export const educationLevelSchema = z.enum([
  'secondary_special', 'incomplete_higher', 'bachelor', 'specialist', 'master', 'phd',
])

export const experienceSchema = z.object({
  experience: z.array(z.object({
    company: z.string().trim().min(1, 'Укажите компанию').max(200),
    position: z.string().trim().min(1, 'Укажите должность').max(200),
    startDate: monthSchema,
    endDate: z.string(),
    current: z.boolean(),
    city: z.string().trim().max(100),
    description: optionalLongText,
    achievements: z.string().max(4000),
    technologies: z.string().max(3200),
  }).superRefine((entry, context) => {
    if (!entry.current && !/^\d{4}-\d{2}$/.test(entry.endDate)) {
      context.addIssue({
        code: 'custom',
        path: ['endDate'],
        message: 'Укажите месяц окончания или отметьте текущую работу',
      })
    }
  })).max(50),
  education: z.array(z.object({
    institution: z.string().trim().min(1, 'Укажите учебное заведение').max(200),
    level: z.union([educationLevelSchema, z.literal('')]),
    faculty: optionalShortText,
    specialization: optionalShortText,
    graduationYear: optionalYearSchema,
  })).max(20),
  courses: z.array(z.object({
    name: z.string().trim().min(1, 'Укажите название курса').max(200),
    organization: optionalShortText,
    year: optionalYearSchema,
    url: optionalUrl,
  })).max(50),
  projects: z.array(z.object({
    name: z.string().trim().min(1, 'Укажите название проекта').max(200),
    role: optionalShortText,
    description: optionalLongText,
    url: optionalUrl,
    technologies: z.string().max(1000),
  })).max(30),
})

export const employmentTypeSchema = z.enum(['full_time', 'part_time', 'project', 'internship'])
export const workFormatSchema = z.enum(['office', 'remote', 'hybrid'])
export const jobSearchStatusSchema = z.enum(['active', 'open', 'not_looking'])

export const preferencesSchema = z.object({
  salaryFrom: z.string().refine((value) => {
    if (value === '') return true
    const digits = salaryDigits(value)
    if (!/^\d+$/.test(digits)) return false
    const salary = Number(digits)
    return Number.isInteger(salary) && salary >= 0 && salary <= 100_000_000
  }, 'Введите сумму от 0 до 100 000 000'),
  employmentTypes: z.array(employmentTypeSchema),
  workFormats: z.array(workFormatSchema),
  jobSearchStatus: jobSearchStatusSchema,
  showBirthDate: z.boolean(),
  showPhoto: z.boolean(),
  showSalary: z.boolean(),
  showFspAchievements: z.boolean(),
  hideCurrentCompany: z.boolean(),
})

export type PersonalValues = z.infer<typeof personalSchema>
export type SpecializationValues = z.infer<typeof specializationSchema>
export type SkillsValues = z.infer<typeof skillsSchema>
export type ExperienceValues = z.infer<typeof experienceSchema>
export type PreferencesValues = z.infer<typeof preferencesSchema>
