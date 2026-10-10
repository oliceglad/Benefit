import { z } from 'zod'
import { newStage, pipelineDraftSchema, type PipelineDraft, type StageTemplate } from '@/features/pipelines/model/pipeline-draft'

const previewChanged = 'benefit:vacancy-pipeline-preview-changed'
const previewSchema = z.object({ version: z.literal(1), pipeline: pipelineDraftSchema })
function previewKey(vacancyId: string) { return `benefit:vacancy-pipeline-preview:v1:${vacancyId}` }

// Explicit local design projection, never a server publication or cross-account draft lookup.
export function attachVacancyPipelinePreview(draft: PipelineDraft): void {
  if (!import.meta.env.DEV) throw new Error('Локальный предпросмотр доступен в режиме разработки.')
  const pipeline = pipelineDraftSchema.parse(draft)
  if (!pipeline.vacancyId) throw new Error('Сначала выберите вакансию.')
  localStorage.setItem(previewKey(pipeline.vacancyId), JSON.stringify({ version: 1, pipeline }))
  window.dispatchEvent(new Event(previewChanged))
}

export function vacancyPipelinePreviewSnapshot(vacancyId: string): string | null {
  if (!import.meta.env.DEV) return null
  try { return localStorage.getItem(previewKey(vacancyId)) }
  catch { return null }
}

export function parseVacancyPipelinePreview(raw: string | null, vacancyId: string): PipelineDraft | null {
  if (!raw) return null
  try {
    const { pipeline } = previewSchema.parse(JSON.parse(raw))
    return pipeline.vacancyId === vacancyId ? pipeline : null
  } catch { return null }
}

export function subscribeVacancyPipelinePreview(notify: () => void): () => void {
  window.addEventListener('storage', notify)
  window.addEventListener(previewChanged, notify)
  return () => {
    window.removeEventListener('storage', notify)
    window.removeEventListener(previewChanged, notify)
  }
}

const exampleStages: StageTemplate[] = [
  { kind: 'intake', title: 'Отклик на вакансию', description: 'Вы отправляете резюме и, если хотите, сопроводительное письмо. Компания знакомится с вашим опытом.' },
  { kind: 'hr_interview', title: 'Знакомство с рекрутером', description: 'Разговор о вашем опыте, ожиданиях и условиях работы. Можно задать первые вопросы о роли и компании.' },
  { kind: 'tech_interview', title: 'Техническое интервью', description: 'Обсуждение проектов, подходов к разработке и профессиональных задач со специалистом команды.' },
  { kind: 'assignment', title: 'Практическая задача', description: 'Пример этапа с практической задачей работодателя. Он не запускает и не заменяет тестирование платформы.' },
  { kind: 'team_meeting', title: 'Встреча с командой', description: 'Знакомство с будущими коллегами, рабочими процессами и задачами на первые месяцы.' },
  { kind: 'offer', title: 'Обсуждение оффера', description: 'Согласование роли, зарплаты, формата работы и даты выхода, если стороны готовы продолжить.' },
  { kind: 'start', title: 'Первый день в команде', description: 'Начало работы после согласования предложения и оформления документов.' },
]

export function exampleVacancyPipeline(): PipelineDraft {
  return { id: crypto.randomUUID(), name: 'Маршрут кандидата', savedAt: null, stages: exampleStages.map(newStage) }
}
