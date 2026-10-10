import { z } from 'zod'

import { Grade, ITRole, WorkFormat } from '@/shared/api/generated/talent/models'
import type { SearchCandidatesApiV1TalentCandidatesGetParams } from '@/shared/api/generated/talent/models'

const optionalText = (max: number) => z.string().trim().max(max).catch('').optional()
const optionalNumber = (max: number) => z.preprocess(
  (value) => value === '' || value == null ? undefined : value,
  z.coerce.number().min(0).max(max).optional().catch(undefined),
)

export const talentSearchSchema = z.object({
  q: optionalText(200),
  specialization: z.enum(ITRole).optional().catch(undefined),
  grade: z.preprocess((value) => typeof value === 'string' ? [value] : value, z.array(z.enum(Grade)).max(5).optional().catch(undefined)),
  grade_status: z.enum(['confirmed', 'not_confirmed']).optional().catch(undefined),
  skills: optionalText(500),
  skills_mode: z.enum(['all', 'any']).catch('all').default('all'),
  fsp: z.enum(['with', 'without']).optional().catch(undefined),
  city: optionalText(100),
  work_format: z.enum(WorkFormat).optional().catch(undefined),
  experience_min: optionalNumber(50),
  active_only: z.preprocess((value) => value === true || value === 'true', z.boolean()).default(false),
  include_not_looking: z.preprocess((value) => value === true || value === 'true', z.boolean()).default(false),
  sort: z.enum(['relevance', 'skills', 'actuality', 'experience', 'fsp']).catch('relevance').default('relevance'),
  offset: z.coerce.number().int().min(0).max(1_000_000).catch(0).default(0),
  candidate: z.uuid().optional().catch(undefined),
})

export type TalentSearch = z.infer<typeof talentSearchSchema>
export const talentPageSize = 12

export function talentRequest(search: TalentSearch): SearchCandidatesApiV1TalentCandidatesGetParams {
  const { fsp, skills, candidate: _candidate, ...params } = search
  void _candidate
  return {
    ...params,
    skills: [...new Set((skills ?? '').split(/[,;\n]/).map((skill) => skill.trim()).filter(Boolean))],
    has_fsp: fsp === 'with' ? true : fsp === 'without' ? false : undefined,
    limit: talentPageSize,
  }
}

export const talentDefaults: TalentSearch = talentSearchSchema.parse({})

export const gradeLabels: Record<Grade, string> = { intern: 'Стажёр', junior: 'Junior', middle: 'Middle', senior: 'Senior', lead: 'Lead' }
export const formatLabels: Record<WorkFormat, string> = { office: 'Офис', remote: 'Удалённо', hybrid: 'Гибрид' }
export const roleLabels: Record<ITRole, string> = {
  backend: 'Backend-разработчик', frontend: 'Frontend-разработчик', fullstack: 'Fullstack-разработчик',
  mobile: 'Мобильный разработчик', devops: 'DevOps / SRE', qa: 'Тестировщик (QA)', qa_automation: 'Автоматизатор тестирования',
  data_scientist: 'Data Scientist', ml_engineer: 'ML-инженер', data_engineer: 'Data Engineer', data_analyst: 'Аналитик данных',
  system_analyst: 'Системный аналитик', business_analyst: 'Бизнес-аналитик', product_manager: 'Продакт-менеджер',
  project_manager: 'Проджект-менеджер', designer: 'UI/UX-дизайнер', gamedev: 'Разработчик игр',
  security: 'Информационная безопасность', embedded: 'Embedded-разработчик', dba: 'Администратор БД', team_lead: 'Тимлид', architect: 'Архитектор',
}

export const sortLabels: Record<TalentSearch['sort'], string> = {
  relevance: 'По релевантности', skills: 'По совпадению навыков', actuality: 'По активности',
  experience: 'По опыту', fsp: 'По числу достижений ФСП',
}
