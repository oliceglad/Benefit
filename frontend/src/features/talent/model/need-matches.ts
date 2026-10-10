import { z } from 'zod'

import { Grade, Industry, ITRole } from '@/shared/api/generated/talent/models'

const categorySchema = z.object({
  specialization: z.enum(ITRole).nullable(), grade: z.enum(Grade).nullable(), grade_status: z.string(),
})
const candidateSchema = z.object({
  user_id: z.uuid(), full_name: z.string(), headline: z.string().nullable(), city: z.string().nullable(),
  relocation_ready: z.boolean(), job_search_status: z.string(), roles: z.array(z.enum(ITRole)),
  category: categorySchema.extend({ industry: z.enum(Industry).nullable(), verified_percent: z.number().nullable(), test_title: z.string().nullable() }),
  skills: z.array(z.record(z.string(), z.unknown())), experience_months: z.number().nonnegative(),
  work_formats: z.array(z.string()), salary_from: z.number().nullable(), salary_currency: z.string().nullable(),
  fsp_count: z.number().int().nonnegative(), fsp_achievements: z.array(z.record(z.string(), z.unknown())),
  actuality: z.object({ status: z.string(), last_active_at: z.string(), days_since_active: z.number() }), has_photo: z.boolean(),
})

export const needMatchesSchema = z.object({
  need_id: z.uuid(), total: z.number().int().nonnegative(),
  categories: z.array(categorySchema.extend({
    count: z.number().int().nonnegative(), best_score: z.number().nullable().optional(),
    avg_score: z.number().nullable().optional(), hint: z.string().nullable().optional(),
  })),
  candidates: z.array(z.object({
    score: z.number().min(0).max(100), fit: z.enum(['excellent', 'good', 'partial']), reasons: z.array(z.string()), warnings: z.array(z.string()),
    breakdown: z.array(z.object({ component: z.string(), title: z.string(), points: z.number(), max_points: z.number() })),
    matched_skills: z.array(z.string()), related_skills: z.array(z.object({ required: z.string(), has: z.string() })), missing_skills: z.array(z.string()),
    contact_status: z.string().nullable(), feedback: z.enum(['like', 'dislike']).nullable(), candidate: candidateSchema,
  })),
  excluded: z.record(z.string(), z.number().int().nonnegative()).default({}),
  suggestions: z.array(z.object({ text: z.string(), extra_candidates: z.number().int().nonnegative() })).default([]), keywords: z.array(z.string()).default([]),
})

export type NeedMatches = z.infer<typeof needMatchesSchema>

export const exclusionLabels: Record<string, string> = {
  missing_required_skills: 'Нет обязательных навыков', grade_out_of_range: 'Грейд вне диапазона', unconfirmed_grade: 'Грейд не подтверждён',
  experience_too_low: 'Недостаточный опыт', over_budget: 'Ожидания выше бюджета', format_mismatch: 'Другой формат работы',
  city_mismatch: 'Другой город без готовности к переезду', disliked: 'Отмечен как неподходящий', declined: 'Отказался от приглашения',
  rejected: 'Отклик уже отклонён', contacted: 'Уже был контакт', insufficient_skills: 'Совпало меньше половины обязательного стека', low_score: 'Низкое соответствие',
}
