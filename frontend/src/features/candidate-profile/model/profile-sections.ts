import type { Completeness } from '@/shared/api/generated/candidates/models'

export const profileSectionIds = [
  'personal',
  'contacts',
  'specialization',
  'skills',
  'experience',
  'preferences',
  'consents',
] as const

export type ProfileSectionId = (typeof profileSectionIds)[number]

export const profileSections: ReadonlyArray<{
  id: ProfileSectionId
  title: string
  shortTitle: string
}> = [
  { id: 'personal', title: 'Личные данные', shortTitle: 'Личные данные' },
  { id: 'contacts', title: 'Контакты', shortTitle: 'Контакты' },
  { id: 'specialization', title: 'Специализация и грейд', shortTitle: 'Специализация' },
  { id: 'skills', title: 'Навыки', shortTitle: 'Навыки' },
  { id: 'experience', title: 'Опыт и образование', shortTitle: 'Опыт и образование' },
  { id: 'preferences', title: 'Пожелания к работе', shortTitle: 'Пожелания' },
  { id: 'consents', title: 'Согласия и публикация', shortTitle: 'Согласия' },
]

const missingFieldLabels: Record<string, string> = {
  last_name: 'Фамилия',
  first_name: 'Имя',
  contacts: 'Контакт для связи',
  headline: 'Желаемая должность',
  grade: 'Заявленный грейд',
  roles: 'IT-роль',
  skills: 'Хотя бы один навык',
  experience_or_projects: 'Опыт, проект или образование',
  consents: 'Действующие согласия',
}

export function isProfileSectionId(value: unknown): value is ProfileSectionId {
  return typeof value === 'string' && profileSectionIds.some((section) => section === value)
}

export function nextProfileSection(section: ProfileSectionId): ProfileSectionId | null {
  const index = profileSectionIds.indexOf(section)
  return profileSectionIds[index + 1] ?? null
}

export function missingFieldLabel(field: string): string {
  return missingFieldLabels[field] ?? field
}

export function nextStepTitle(completeness: Completeness): string | null {
  const next = completeness.steps.find((step) => step.id === completeness.next_step)
  return next?.title ?? null
}
