import { z } from 'zod'

const text = z.string().trim().nullish().catch(null)
const skillSchema = z.object({ name: z.string().trim().min(1), level: text, years: z.number().nonnegative().nullish().catch(null) })
const achievementSchema = z.object({
  event: text, discipline: text, level: text, result: text,
  place: z.number().int().positive().nullish().catch(null),
  team: text, event_date: text, url: text,
})

export function candidateSkills(values: unknown[]) {
  return values.flatMap((value) => {
    const result = skillSchema.safeParse(value)
    return result.success ? [result.data] : []
  })
}

export function candidateAchievements(values: unknown[]) {
  return values.flatMap((value) => {
    const result = achievementSchema.safeParse(value)
    return result.success ? [result.data] : []
  })
}

export function publicAchievementUrl(value?: string | null): string | null {
  if (!value) return null
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null
  } catch { return null }
}

export function experienceLabel(months: number): string {
  if (months <= 0) return 'Опыт не указан'
  const years = Math.floor(months / 12)
  const rest = months % 12
  return [years ? `${years} г.` : '', rest ? `${rest} мес.` : ''].filter(Boolean).join(' ')
}

export function dateLabel(value?: string | null): string | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }).format(date)
}
