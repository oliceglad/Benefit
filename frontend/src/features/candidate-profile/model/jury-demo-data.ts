import type { ProfileSectionId } from '@/features/candidate-profile/model/profile-sections'
import type { ProfileUpdate } from '@/shared/api/generated/candidates/models'

type DataSection = Exclude<ProfileSectionId, 'consents'>

// Fictional fixtures for the opt-in jury tools. These URLs are sample profile data.
const demoSteps = {
  personal: {
    last_name: 'Тестов', first_name: 'Алексей', middle_name: 'Демонстрационный',
    birth_date: '1998-04-15', city: 'Самара', relocation_ready: true,
  },
  contacts: {
    contact_email: 'candidate@example.com', phone: '+70000000000',
    telegram: '@benefit_demo_jury',
  },
  specialization: {
    headline: 'Python-разработчик · демонстрационный профиль',
    about: 'Вымышленный кандидат для демонстрации Benefit. Все сведения в этом профиле синтетические.',
    grade: 'middle', roles: ['backend'],
  },
  skills: {
    skills: [
      { name: 'Python', level: 'advanced', years: 3 },
      { name: 'PostgreSQL', level: 'intermediate', years: 2 },
      { name: 'Docker', level: 'intermediate', years: 2 },
    ],
    soft_skills: ['Работа в команде', 'Ответственность'],
    languages: [{ language: 'Русский', level: 'native' }, { language: 'Английский', level: 'B2' }],
  },
  experience: {
    experience: [{
      company: 'Демонстрационная компания', position: 'Python-разработчик',
      start_date: '2023-04-01', end_date: null, city: 'Самара',
      description: 'Синтетическая запись: разработка API и сервисов обработки данных.',
      technologies: ['Python', 'PostgreSQL', 'Docker'],
      achievements: ['Подготовил API учебного сервиса', 'Добавил проверки качества данных'],
    }],
    education: [{
      institution: 'Демонстрационный университет', level: 'bachelor',
      faculty: 'Информационные технологии', specialization: 'Программная инженерия',
      graduation_year: 2020,
    }],
    courses: [{
      name: 'Разработка API на Python', organization: 'Тестовая академия',
      year: 2023, url: 'https://example.com/course',
    }],
    projects: [{
      name: 'Учебная платформа', role: 'Backend-разработчик',
      description: 'Вымышленный проект для показа портфолио кандидата.',
      technologies: ['Python', 'PostgreSQL'], url: 'https://example.com/project',
    }],
  },
  preferences: {
    salary_from: 180000, salary_currency: 'RUB', employment_types: ['full_time'],
    work_formats: ['remote', 'hybrid'], job_search_status: 'open',
  },
} satisfies Record<DataSection, ProfileUpdate>

export function buildJuryStepUpdate(section: ProfileSectionId): ProfileUpdate | null {
  return section === 'consents' ? null : structuredClone(demoSteps[section])
}

export function juryToolsEnabled(): boolean {
  return import.meta.env.DEV || import.meta.env.VITE_ENABLE_JURY_TOOLS === 'true'
}
