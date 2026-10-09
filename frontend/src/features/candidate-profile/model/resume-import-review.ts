import type { ProfileDictionaries } from '@/features/candidate-profile/model/dictionaries'
import type { ProfileResponse } from '@/shared/api/generated/candidates/models'

export type ResumeFieldEffect = 'fill' | 'merge' | 'replace' | 'keep'

export type ResumeReviewField = {
  key: string
  label: string
  incoming: unknown
  current: unknown
  effect: ResumeFieldEffect
}

export type ResumeReviewSection = {
  id: string
  title: string
  fields: ResumeReviewField[]
}

const fieldDefinitions: Record<string, { section: string; sectionTitle: string; label: string }> = {
  last_name: { section: 'personal', sectionTitle: 'Личные данные', label: 'Фамилия' },
  first_name: { section: 'personal', sectionTitle: 'Личные данные', label: 'Имя' },
  middle_name: { section: 'personal', sectionTitle: 'Личные данные', label: 'Отчество' },
  birth_date: { section: 'personal', sectionTitle: 'Личные данные', label: 'Дата рождения' },
  city: { section: 'personal', sectionTitle: 'Личные данные', label: 'Город' },
  relocation_ready: { section: 'personal', sectionTitle: 'Личные данные', label: 'Готовность к переезду' },
  phone: { section: 'contacts', sectionTitle: 'Контакты', label: 'Телефон' },
  contact_email: { section: 'contacts', sectionTitle: 'Контакты', label: 'Контактная почта' },
  telegram: { section: 'contacts', sectionTitle: 'Контакты', label: 'Telegram' },
  links: { section: 'contacts', sectionTitle: 'Контакты', label: 'Ссылки' },
  headline: { section: 'specialization', sectionTitle: 'Специализация', label: 'Желаемая должность' },
  about: { section: 'specialization', sectionTitle: 'Специализация', label: 'О себе' },
  grade: { section: 'specialization', sectionTitle: 'Специализация', label: 'Заявленный грейд' },
  industry: { section: 'specialization', sectionTitle: 'Специализация', label: 'Отрасль' },
  roles: { section: 'specialization', sectionTitle: 'Специализация', label: 'IT-роли' },
  skills: { section: 'skills', sectionTitle: 'Навыки', label: 'Технические навыки' },
  soft_skills: { section: 'skills', sectionTitle: 'Навыки', label: 'Гибкие навыки' },
  languages: { section: 'skills', sectionTitle: 'Навыки', label: 'Языки' },
  experience: { section: 'experience', sectionTitle: 'Опыт и образование', label: 'Опыт работы' },
  education: { section: 'experience', sectionTitle: 'Опыт и образование', label: 'Образование' },
  courses: { section: 'experience', sectionTitle: 'Опыт и образование', label: 'Курсы' },
  projects: { section: 'experience', sectionTitle: 'Опыт и образование', label: 'Проекты' },
  salary_from: { section: 'preferences', sectionTitle: 'Пожелания к работе', label: 'Зарплатные ожидания' },
  employment_types: { section: 'preferences', sectionTitle: 'Пожелания к работе', label: 'Занятость' },
  work_formats: { section: 'preferences', sectionTitle: 'Пожелания к работе', label: 'Формат работы' },
  job_search_status: { section: 'preferences', sectionTitle: 'Пожелания к работе', label: 'Статус поиска' },
}

const mergeable = new Set(['skills', 'soft_skills', 'roles', 'languages', 'links'])
const replaceable = new Set(['experience', 'education', 'courses', 'projects'])

function sameValue(current: unknown, incoming: unknown): boolean {
  return JSON.stringify(current) === JSON.stringify(incoming)
}

function currentValue(profile: ProfileResponse, key: string): unknown {
  switch (key) {
    case 'last_name': return profile.last_name
    case 'first_name': return profile.first_name
    case 'middle_name': return profile.middle_name
    case 'birth_date': return profile.birth_date
    case 'city': return profile.city
    case 'relocation_ready': return profile.relocation_ready
    case 'phone': return profile.phone
    case 'contact_email': return profile.contact_email
    case 'telegram': return profile.telegram
    case 'links': return profile.links
    case 'headline': return profile.headline
    case 'about': return profile.about
    case 'grade': return profile.grade
    case 'industry': return profile.industry
    case 'roles': return profile.roles
    case 'skills': return profile.skills
    case 'soft_skills': return profile.soft_skills
    case 'languages': return profile.languages
    case 'experience': return profile.experience
    case 'education': return profile.education
    case 'courses': return profile.courses
    case 'projects': return profile.projects
    case 'salary_from': return profile.salary_from
    case 'employment_types': return profile.employment_types
    case 'work_formats': return profile.work_formats
    case 'job_search_status': return profile.job_search_status
    default: return undefined
  }
}

function itemIdentity(key: string, value: unknown): string | null {
  if (typeof value === 'string') return value.toLocaleLowerCase('ru-RU')
  if (!value || typeof value !== 'object') return null
  const record = value as Record<string, unknown>
  const identityKey = key === 'skills' ? 'name' : key === 'languages' ? 'language' : key === 'links' ? 'url' : null
  const identity = identityKey ? record[identityKey] : null
  return typeof identity === 'string' ? identity.toLocaleLowerCase('ru-RU') : null
}

function effectFor(key: string, current: unknown, incoming: unknown): ResumeFieldEffect {
  if (mergeable.has(key) && Array.isArray(incoming)) {
    const existing = new Set((Array.isArray(current) ? current : []).map((item) => itemIdentity(key, item)).filter(Boolean))
    return incoming.some((item) => !existing.has(itemIdentity(key, item))) ? 'merge' : 'keep'
  }
  if (replaceable.has(key)) {
    if (sameValue(current, incoming)) return 'keep'
    return Array.isArray(current) && current.length > 0 ? 'replace' : 'fill'
  }
  if (sameValue(current, incoming)) return 'keep'
  return current === null || current === undefined || current === '' ? 'fill' : 'replace'
}

function optionTitle(options: ProfileDictionaries[keyof ProfileDictionaries], value: unknown): unknown {
  if (!Array.isArray(options) || typeof value !== 'string') return value
  const option = options.find((item: unknown) => item && typeof item === 'object' && 'id' in item && item.id === value)
  return option && typeof option === 'object' && 'title' in option && typeof option.title === 'string' ? option.title : value
}

function presentNestedList(key: string, value: unknown, dictionaries: ProfileDictionaries): unknown {
  if (!Array.isArray(value)) return value
  const items: unknown[] = value
  if (key === 'roles') return items.map((item) => optionTitle(dictionaries.roles, item))
  if (key === 'employment_types') return items.map((item) => optionTitle(dictionaries.employment_types, item))
  if (key === 'work_formats') return items.map((item) => optionTitle(dictionaries.work_formats, item))
  return items.map((item) => {
    if (!item || typeof item !== 'object') return item
    const record = { ...item } as Record<string, unknown>
    if (key === 'skills') record.level = optionTitle(dictionaries.skill_levels, record.level)
    if (key === 'languages') record.level = optionTitle(dictionaries.language_levels, record.level)
    if (key === 'education') record.level = optionTitle(dictionaries.education_levels, record.level)
    if (key === 'links') record.type = optionTitle(dictionaries.link_types, record.type)
    return record
  })
}

function presentValue(key: string, value: unknown, dictionaries: ProfileDictionaries): unknown {
  if (key === 'grade') return optionTitle(dictionaries.grades, value)
  if (key === 'job_search_status') return optionTitle(dictionaries.job_search_statuses, value)
  return presentNestedList(key, value, dictionaries)
}

export function buildResumeReview(
  draft: Record<string, unknown>,
  profile: ProfileResponse,
  dictionaries: ProfileDictionaries,
): ResumeReviewSection[] {
  const sections = new Map<string, ResumeReviewSection>()
  Object.entries(draft).forEach(([key, incoming]) => {
    const definition = fieldDefinitions[key]
    if (!definition) return
    const section = sections.get(definition.section) ?? {
      id: definition.section,
      title: definition.sectionTitle,
      fields: [],
    }
    const current = currentValue(profile, key)
    section.fields.push({
      key,
      label: definition.label,
      incoming: presentValue(key, incoming, dictionaries),
      current: presentValue(key, current, dictionaries),
      effect: effectFor(key, current, incoming),
    })
    sections.set(definition.section, section)
  })
  return [...sections.values()]
}

export function appliedFieldLabel(key: string): string {
  return fieldDefinitions[key]?.label ?? key
}
