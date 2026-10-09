import type { ProfileDictionaries } from '@/features/candidate-profile/model/dictionaries'
import type { ProfileSectionId } from '@/features/candidate-profile/model/profile-sections'
import type { ConsentStatus, ProfileResponse } from '@/shared/api/generated/candidates/models'

export type ProfileOverviewSummary = Record<ProfileSectionId, string>

function optionTitle(options: { id: string; title: string }[], value: string | null | undefined): string | null {
  if (!value) return null
  return options.find((option) => option.id === value)?.title ?? value
}

function listTitles(options: { id: string; title: string }[], values: string[]): string[] {
  return values.map((value) => optionTitle(options, value) ?? value)
}

function compactList(values: string[], limit = 2): string {
  const visible = values.slice(0, limit)
  const remaining = values.length - visible.length
  return `${visible.join(', ')}${remaining > 0 ? ` · ещё ${remaining}` : ''}`
}

function plural(value: number, one: string, few: string, many: string): string {
  const mod100 = value % 100
  const mod10 = value % 10
  if (mod100 >= 11 && mod100 <= 14) return many
  if (mod10 === 1) return one
  if (mod10 >= 2 && mod10 <= 4) return few
  return many
}

function personalSummary(profile: ProfileResponse): string {
  const values = [
    profile.first_name || profile.last_name ? 'имя' : null,
    profile.birth_date ? 'дата рождения' : null,
    profile.city ? 'город' : null,
  ].filter((value): value is string => value !== null)
  if (values.length === 0) return 'Не заполнено'
  if (values.length === 3) return 'Имя, дата рождения и город указаны'
  return `Указано: ${values.join(', ')}`
}

function contactsSummary(profile: ProfileResponse): string {
  if (profile.phone && profile.contact_email) return profile.telegram ? 'Телефон, почта и Telegram указаны' : 'Телефон и почта указаны'
  const values = [profile.phone ? 'телефон' : null, profile.contact_email ? 'почта' : null, profile.telegram ? 'Telegram' : null]
    .filter((value): value is string => value !== null)
  return values.length > 0 ? `Указано: ${values.join(', ')}` : 'Не заполнено'
}

function specializationSummary(profile: ProfileResponse, dictionaries: ProfileDictionaries): string {
  const grade = optionTitle(dictionaries.grades, profile.grade)
  const parts = [profile.headline, grade ? `грейд ${grade}` : null].filter((value): value is string => Boolean(value))
  if (parts.length > 0) return parts.join(' · ')
  const roles = listTitles(dictionaries.roles, profile.roles)
  return roles.length > 0 ? compactList(roles) : 'Не заполнено'
}

function skillsSummary(profile: ProfileResponse): string {
  if (profile.skills.length > 0) {
    const skillNames = profile.skills.map((skill) => skill.name)
    const languages = profile.languages.length
    return `${compactList(skillNames)}${languages > 0 ? ` · ${languages} ${plural(languages, 'язык', 'языка', 'языков')}` : ''}`
  }
  if (profile.languages.length > 0) return `${profile.languages.length} ${plural(profile.languages.length, 'язык', 'языка', 'языков')}`
  if (profile.soft_skills.length > 0) return `${profile.soft_skills.length} ${plural(profile.soft_skills.length, 'гибкий навык', 'гибких навыка', 'гибких навыков')}`
  return 'Не заполнено'
}

function experienceSummary(profile: ProfileResponse): string {
  const parts = []
  if (profile.experience.length > 0) parts.push(`${profile.experience.length} ${plural(profile.experience.length, 'место работы', 'места работы', 'мест работы')}`)
  if (profile.projects.length > 0) parts.push(`${profile.projects.length} ${plural(profile.projects.length, 'проект', 'проекта', 'проектов')}`)
  if (profile.education.length > 0 && parts.length === 0) parts.push(`${profile.education.length} ${plural(profile.education.length, 'запись об образовании', 'записи об образовании', 'записей об образовании')}`)
  return parts.length > 0 ? parts.join(' · ') : 'Не заполнено'
}

function preferencesSummary(profile: ProfileResponse, dictionaries: ProfileDictionaries): string {
  const formats = listTitles(dictionaries.work_formats, profile.work_formats)
  const salary = profile.salary_from == null ? null : `${new Intl.NumberFormat('ru-RU').format(profile.salary_from)} ₽`
  const main = [formats.length > 0 ? compactList(formats) : null, salary].filter((value): value is string => Boolean(value))
  if (main.length > 0) return main.join(' · ')
  const employment = listTitles(dictionaries.employment_types, profile.employment_types)
  if (employment.length > 0) return compactList(employment)
  return optionTitle(dictionaries.job_search_statuses, profile.job_search_status) ?? 'Не заполнено'
}

export function consentsSummary(profile: ProfileResponse, consents: ConsentStatus[] | undefined, failed = false): string {
  if (failed) return 'Не удалось получить состояние согласий'
  if (!consents) return 'Загружаем состояние согласий…'
  const granted = consents.filter((consent) => consent.granted).length
  const consentState = consents.length === 0
    ? 'Согласия недоступны'
    : granted === consents.length
      ? 'Все согласия приняты'
      : granted === 0
        ? 'Согласия не приняты'
        : `Принято ${granted} из ${consents.length}`
  return `${consentState} · ${profile.status === 'published' ? 'профиль опубликован' : 'профиль не опубликован'}`
}

export function buildProfileOverviewSummary(
  profile: ProfileResponse,
  dictionaries: ProfileDictionaries,
  consents?: ConsentStatus[],
  consentsFailed = false,
): ProfileOverviewSummary {
  return {
    personal: personalSummary(profile),
    contacts: contactsSummary(profile),
    specialization: specializationSummary(profile, dictionaries),
    skills: skillsSummary(profile),
    experience: experienceSummary(profile),
    preferences: preferencesSummary(profile, dictionaries),
    consents: consentsSummary(profile, consents, consentsFailed),
  }
}
