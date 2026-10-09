import { z } from 'zod'

import type { ProfileResponse, ProfileUpdate } from '@/shared/api/generated/candidates/models'
import {
  educationLevelSchema,
  employmentTypeSchema,
  gradeSchema,
  jobSearchStatusSchema,
  languageLevelSchema,
  roleSchema,
  skillLevelSchema,
  workFormatSchema,
} from './profile-schemas'

const nullableText = z.string().nullable()
const skillSchema = z.object({ name: z.string(), level: skillLevelSchema.nullable().optional(), years: z.number().nullable().optional() })
const languageSchema = z.object({ language: z.string(), level: languageLevelSchema })
const linkTypeSchema = z.enum(['github', 'gitlab', 'linkedin', 'habr', 'portfolio', 'other'])
const industrySchema = z.enum(['fintech', 'ecommerce', 'govtech', 'telecom', 'healthtech', 'edtech', 'gamedev', 'media', 'logistics', 'industry', 'energy', 'cybersecurity', 'ai', 'travel', 'real_estate', 'outsource', 'other'])
const linkSchema = z.object({ type: linkTypeSchema, url: z.string() })
const experienceSchema = z.object({
  company: z.string(), position: z.string(), start_date: z.string(), end_date: nullableText.optional(),
  city: nullableText.optional(), description: nullableText.optional(), achievements: z.array(z.string()).optional(), technologies: z.array(z.string()).optional(),
})
const educationSchema = z.object({
  institution: z.string(), level: educationLevelSchema.nullable().optional(), faculty: nullableText.optional(),
  specialization: nullableText.optional(), graduation_year: z.number().int().nullable().optional(),
})
const courseSchema = z.object({ name: z.string(), organization: nullableText.optional(), year: z.number().int().nullable().optional(), url: nullableText.optional() })
const projectSchema = z.object({ name: z.string(), role: nullableText.optional(), description: nullableText.optional(), url: nullableText.optional(), technologies: z.array(z.string()).optional() })

const selectableResumeDraftSchema = z.object({
  last_name: nullableText.optional(),
  first_name: nullableText.optional(),
  middle_name: nullableText.optional(),
  birth_date: nullableText.optional(),
  city: nullableText.optional(),
  relocation_ready: z.boolean().optional(),
  phone: nullableText.optional(),
  contact_email: nullableText.optional(),
  telegram: nullableText.optional(),
  links: z.array(linkSchema).optional(),
  headline: nullableText.optional(),
  about: nullableText.optional(),
  grade: gradeSchema.nullable().optional(),
  industry: industrySchema.nullable().optional(),
  roles: z.array(roleSchema).optional(),
  skills: z.array(skillSchema).optional(),
  soft_skills: z.array(z.string()).optional(),
  languages: z.array(languageSchema).optional(),
  experience: z.array(experienceSchema).optional(),
  education: z.array(educationSchema).optional(),
  courses: z.array(courseSchema).optional(),
  projects: z.array(projectSchema).optional(),
  salary_from: z.number().nullable().optional(),
  salary_currency: z.string().optional(),
  employment_types: z.array(employmentTypeSchema).optional(),
  work_formats: z.array(workFormatSchema).optional(),
  job_search_status: jobSearchStatusSchema.optional(),
})

export type ResumeSelectableField = keyof z.infer<typeof selectableResumeDraftSchema>

const mergeableFields = new Set<ResumeSelectableField>(['skills', 'soft_skills', 'roles', 'languages', 'links'])

function identity(field: ResumeSelectableField, value: unknown): string {
  if (typeof value === 'string') return value.toLocaleLowerCase('ru-RU')
  if (!value || typeof value !== 'object') return JSON.stringify(value) ?? `${typeof value}:${value === null ? 'null' : ''}`
  if (field === 'skills' && 'name' in value && typeof value.name === 'string') return value.name.toLocaleLowerCase('ru-RU')
  if (field === 'languages' && 'language' in value && typeof value.language === 'string') return value.language.toLocaleLowerCase('ru-RU')
  if (field === 'links' && 'url' in value && typeof value.url === 'string') return value.url.toLocaleLowerCase('ru-RU')
  return JSON.stringify(value) ?? 'object'
}

function currentList(profile: ProfileResponse, field: ResumeSelectableField): unknown[] {
  if (field === 'skills') return profile.skills
  if (field === 'soft_skills') return profile.soft_skills
  if (field === 'roles') return profile.roles
  if (field === 'languages') return profile.languages
  if (field === 'links') return profile.links
  return []
}

function mergeList(profile: ProfileResponse, field: ResumeSelectableField, incoming: unknown): unknown {
  if (!mergeableFields.has(field) || !Array.isArray(incoming)) return incoming
  const current = currentList(profile, field)
  const incomingItems: unknown[] = incoming
  const seen = new Set(current.map((item) => identity(field, item)))
  return [...current, ...incomingItems.filter((item) => {
    const key = identity(field, item)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })]
}

export function selectableResumeFields(draft: Record<string, unknown>): ResumeSelectableField[] {
  return Object.keys(selectableResumeDraftSchema.parse(draft)) as ResumeSelectableField[]
}

export function buildSelectedResumeUpdate(
  draft: Record<string, unknown>,
  profile: ProfileResponse,
  selected: ReadonlySet<string>,
): ProfileUpdate {
  const parsed = selectableResumeDraftSchema.parse(draft)
  const entries = Object.entries(parsed)
    .filter(([key]) => selected.has(key))
    .map(([key, value]) => [key, mergeList(profile, key as ResumeSelectableField, value)])
  return selectableResumeDraftSchema.parse(Object.fromEntries(entries))
}
