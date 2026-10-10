import { z } from 'zod'

// Labels follow backend/libs/benefit-common/benefit_common/dictionaries.py.
// Replace this snapshot with the employer dictionary API when it is available.
export const companyIndustryOptions = [
  { value: 'fintech', label: 'Финтех и банки' },
  { value: 'ecommerce', label: 'E-commerce и ритейл' },
  { value: 'govtech', label: 'Госсектор (GovTech)' },
  { value: 'telecom', label: 'Телеком' },
  { value: 'healthtech', label: 'Медицина (HealthTech)' },
  { value: 'edtech', label: 'Образование (EdTech)' },
  { value: 'gamedev', label: 'Игры' },
  { value: 'media', label: 'Медиа и развлечения' },
  { value: 'logistics', label: 'Логистика и транспорт' },
  { value: 'industry', label: 'Промышленность' },
  { value: 'energy', label: 'Энергетика' },
  { value: 'cybersecurity', label: 'Информационная безопасность' },
  { value: 'ai', label: 'Искусственный интеллект' },
  { value: 'travel', label: 'Путешествия' },
  { value: 'real_estate', label: 'Недвижимость (PropTech)' },
  { value: 'outsource', label: 'Аутсорс и заказная разработка' },
  { value: 'other', label: 'Другое' },
]

export const companyFormSchema = z.object({
  name: z.string().trim().min(1, 'Укажите название компании').max(200, 'Не более 200 символов'),
  industry: z.string().refine(
    (value) => companyIndustryOptions.some((option) => option.value === value),
    'Выберите отрасль',
  ),
  description: z.string().trim().min(1, 'Расскажите о компании').max(8000, 'Не более 8000 символов'),
  city: z.string().trim().max(100, 'Не более 100 символов'),
  website: z.string().trim().max(300, 'Не более 300 символов').refine(
    (value) => value === '' || z.url({ protocol: /^https?$/ }).safeParse(value).success,
    'Укажите полный адрес сайта, например https://company.ru',
  ),
  contactName: z.string().trim().max(200, 'Не более 200 символов'),
  contactEmail: z.string().trim().refine(
    (value) => value === '' || z.email().safeParse(value).success,
    'Введите корректную почту',
  ),
})

export type CompanyFormValues = z.infer<typeof companyFormSchema>
