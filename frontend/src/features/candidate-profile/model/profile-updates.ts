import type { ProfileUpdate } from '@/shared/api/generated/candidates/models'

import { parseLocalizedNumber } from './form-values'
import type { ExperienceValues, SkillsValues } from './profile-schemas'

function splitList(value: string): string[] {
  return value.split(/[\n,]/).map((item) => item.trim()).filter(Boolean)
}

export function buildSkillsUpdate(values: SkillsValues): ProfileUpdate {
  return {
    skills: values.skills.map((skill) => ({
      name: skill.name,
      level: skill.level || null,
      years: skill.years === '' ? null : parseLocalizedNumber(skill.years),
    })),
    soft_skills: values.softSkills,
    languages: values.languages,
  }
}

export function withoutSelectedSkills(results: string[], selected: string[]): string[] {
  const normalized = new Set(selected.map((name) => name.toLocaleLowerCase('ru-RU')))
  return results.filter((name) => !normalized.has(name.toLocaleLowerCase('ru-RU')))
}

export function buildExperienceUpdate(values: ExperienceValues): ProfileUpdate {
  return {
    experience: values.experience.map((item) => ({
      company: item.company,
      position: item.position,
      start_date: `${item.startDate}-01`,
      end_date: item.current || !item.endDate ? null : `${item.endDate}-01`,
      city: item.city || null,
      description: item.description || null,
      achievements: splitList(item.achievements),
      technologies: splitList(item.technologies),
    })),
    education: values.education.map((item) => ({
      institution: item.institution,
      level: item.level || null,
      faculty: item.faculty || null,
      specialization: item.specialization || null,
      graduation_year: item.graduationYear === '' ? null : Number(item.graduationYear),
    })),
    courses: values.courses.map((item) => ({
      name: item.name,
      organization: item.organization || null,
      year: item.year === '' ? null : Number(item.year),
      url: item.url || null,
    })),
    projects: values.projects.map((item) => ({
      name: item.name,
      role: item.role || null,
      description: item.description || null,
      url: item.url || null,
      technologies: splitList(item.technologies),
    })),
  }
}
