import { z } from 'zod'

const stageKind = z.enum(['intake', 'screening', 'hr_interview', 'tech_interview', 'assignment', 'team_meeting', 'final_interview', 'offer', 'paperwork', 'start'])
const stageSchema = z.object({ id: z.uuid(), kind: stageKind, title: z.string().trim().min(1).max(80), description: z.string().max(500) })
export const pipelineDraftSchema = z.object({
  id: z.uuid(), name: z.string().trim().min(1).max(120), vacancyId: z.string().optional(),
  stages: z.array(stageSchema).min(1).max(16).refine((stages) => new Set(stages.map((s) => s.id)).size === stages.length),
  savedAt: z.string().nullable(),
})
export type PipelineDraft = z.infer<typeof pipelineDraftSchema>
export type PipelineStage = PipelineDraft['stages'][number]
export type StageTemplate = Pick<PipelineStage, 'kind' | 'title' | 'description'>

// Proposed starting set, requested by the product owner. No automatic transitions.
export const stageCatalog: StageTemplate[] = [
  { kind: 'intake', title: 'Новый кандидат', description: 'Входящие кандидаты, ожидающие рассмотрения.' },
  { kind: 'screening', title: 'Первичный отбор', description: 'Опыт, навыки и ожидания по роли.' },
  { kind: 'hr_interview', title: 'HR-интервью', description: 'Знакомство, мотивация и условия работы.' },
  { kind: 'tech_interview', title: 'Техническое интервью', description: 'Профессиональные задачи и технические решения.' },
  { kind: 'assignment', title: 'Тестовое задание', description: 'Практическая задача в рамках отбора работодателя.' },
  { kind: 'team_meeting', title: 'Встреча с командой', description: 'Знакомство с будущими коллегами и процессами.' },
  { kind: 'final_interview', title: 'Финальное интервью', description: 'Обсуждение итогов отбора с руководителем.' },
  { kind: 'offer', title: 'Оффер', description: 'Предложение и согласование условий сотрудничества.' },
  { kind: 'paperwork', title: 'Оформление', description: 'Документы и согласование даты выхода.' },
  { kind: 'start', title: 'Выход на работу', description: 'Завершение отбора и начало работы.' },
]

export function newStage(template: StageTemplate): PipelineStage {
  return { ...template, id: crypto.randomUUID() }
}
export function newPipeline(): PipelineDraft {
  return { id: crypto.randomUUID(), name: 'Основной пайплайн', savedAt: null, stages: stageCatalog.filter((s) => ['intake', 'screening', 'tech_interview', 'offer', 'start'].includes(s.kind)).map(newStage) }
}
function storageKey(accountId: string) { return `benefit:pipeline-drafts:v1:${accountId}` }
export function readPipelineDrafts(accountId: string): PipelineDraft[] {
  const raw = localStorage.getItem(storageKey(accountId))
  return raw ? z.object({ version: z.literal(1), pipelines: z.array(pipelineDraftSchema).max(30) }).parse(JSON.parse(raw)).pipelines : []
}
export function savePipelineDraft(accountId: string, draft: PipelineDraft): PipelineDraft[] {
  const checked = pipelineDraftSchema.parse({ ...draft, savedAt: new Date().toISOString() })
  const previous = readPipelineDrafts(accountId)
  const next = [checked, ...previous.filter((p) => p.id !== checked.id)]
  if (next.length > 30) throw new Error('В этом браузере можно сохранить до 30 пайплайнов.')
  localStorage.setItem(storageKey(accountId), JSON.stringify({ version: 1, pipelines: next }))
  return next
}
export function moveStage(stages: PipelineStage[], index: number, direction: -1 | 1): PipelineStage[] {
  const next = [...stages]
  const target = index + direction
  if (target < 0 || target >= next.length) return next
  ;[next[index], next[target]] = [next[target], next[index]]
  return next
}
