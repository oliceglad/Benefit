import { z } from 'zod'

import {
  CompanySize,
  Industry,
  type CompanyIn,
  type CompanyResponse,
} from '@/shared/api/generated/employers/models'

export const companyIndustryLabels: Record<Industry, string> = {
  fintech: 'Финтех и банки',
  ecommerce: 'E-commerce и ритейл',
  govtech: 'Госсектор (GovTech)',
  telecom: 'Телеком',
  healthtech: 'Медицина (HealthTech)',
  edtech: 'Образование (EdTech)',
  gamedev: 'Игры',
  media: 'Медиа и развлечения',
  logistics: 'Логистика и транспорт',
  industry: 'Промышленность',
  energy: 'Энергетика',
  cybersecurity: 'Информационная безопасность',
  ai: 'Искусственный интеллект',
  travel: 'Путешествия',
  real_estate: 'Недвижимость (PropTech)',
  outsource: 'Аутсорс и заказная разработка',
  other: 'Другое',
}

export const companySizeLabels: Record<CompanySize, string> = {
  '1-10': '1–10 сотрудников',
  '11-50': '11–50 сотрудников',
  '51-200': '51–200 сотрудников',
  '201-1000': '201–1000 сотрудников',
  '1000+': 'Более 1000 сотрудников',
}

const optionalText = (maximum: number, message: string) =>
  z.string().trim().max(maximum, message)

export const companyProfileFormSchema = z.object({
  name: z.string().trim().min(1, 'Укажите название компании').max(200, 'Не более 200 символов'),
  legal_name: optionalText(300, 'Не более 300 символов'),
  inn: z.string().trim().refine(
    (value) => value === '' || /^\d{10}(?:\d{2})?$/.test(value),
    'ИНН должен содержать 10 или 12 цифр',
  ),
  industry: z.enum(Industry),
  description: z.string().trim().min(1, 'Расскажите о компании').max(8000, 'Не более 8000 символов'),
  website: optionalText(300, 'Не более 300 символов').refine(
    (value) => value === '' || z.url({ protocol: /^https?$/ }).safeParse(value).success,
    'Укажите полный адрес сайта, например https://company.ru',
  ),
  city: optionalText(100, 'Не более 100 символов'),
  size: z.union([z.literal(''), z.enum(CompanySize)]),
  tech_stack: z.string().superRefine((value, context) => {
    const items = splitTechStack(value)
    if (items.length > 50) {
      context.addIssue({ code: 'custom', message: 'Не более 50 технологий' })
    }
    if (items.some((item) => item.length > 64)) {
      context.addIssue({ code: 'custom', message: 'Каждая технология — не более 64 символов' })
    }
  }),
  contact_name: optionalText(200, 'Не более 200 символов'),
  contact_email: z.string().trim().refine(
    (value) => value === '' || z.email().safeParse(value).success,
    'Введите корректную почту',
  ),
  contact_phone: optionalText(32, 'Не более 32 символов'),
  telegram: optionalText(64, 'Не более 64 символов'),
})

export type CompanyProfileFormValues = z.infer<typeof companyProfileFormSchema>

export function splitTechStack(value: string): string[] {
  const seen = new Set<string>()
  return value
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter((item) => {
      if (!item) return false
      const key = item.toLocaleLowerCase('ru-RU')
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
}

export function companyProfileFormValues(
  company: CompanyResponse | null,
): CompanyProfileFormValues {
  return {
    name: company?.name ?? '',
    legal_name: company?.legal_name ?? '',
    inn: company?.inn ?? '',
    industry: company?.industry ?? Industry.other,
    description: company?.description ?? '',
    website: company?.website ?? '',
    city: company?.city ?? '',
    size: company?.size ?? '',
    tech_stack: company?.tech_stack?.join(', ') ?? '',
    contact_name: company?.contact_name ?? '',
    contact_email: company?.contact_email ?? '',
    contact_phone: company?.contact_phone ?? '',
    telegram: company?.telegram ?? '',
  }
}

function nullable(value: string): string | null {
  const normalized = value.trim()
  return normalized || null
}

export function companyProfilePayload(
  values: CompanyProfileFormValues,
): CompanyIn {
  return {
    name: values.name.trim(),
    legal_name: nullable(values.legal_name),
    inn: nullable(values.inn),
    industry: values.industry,
    description: values.description.trim(),
    website: nullable(values.website),
    city: nullable(values.city),
    size: values.size || null,
    tech_stack: splitTechStack(values.tech_stack),
    contact_name: nullable(values.contact_name),
    contact_email: nullable(values.contact_email),
    contact_phone: nullable(values.contact_phone),
    telegram: nullable(values.telegram),
  }
}
