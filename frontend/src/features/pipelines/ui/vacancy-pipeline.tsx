import { useMemo, useState, useSyncExternalStore } from 'react'
import {
  exampleVacancyPipeline,
  parseVacancyPipelinePreview,
  subscribeVacancyPipelinePreview,
  vacancyPipelinePreviewSnapshot,
} from '@/features/pipelines/model/vacancy-pipeline-preview'
import { PipelineGraphPanel } from '@/features/pipelines/ui/pipeline-graph-panel'

export function VacancyPipeline({ vacancyId }: { vacancyId: string }) {
  const raw = useSyncExternalStore(subscribeVacancyPipelinePreview, () => vacancyPipelinePreviewSnapshot(vacancyId), () => null)
  const localPreview = useMemo(() => parseVacancyPipelinePreview(raw, vacancyId), [raw, vacancyId])
  const [example] = useState(exampleVacancyPipeline)

  if (!localPreview && !import.meta.env.DEV) {
    return (
      <section className="rounded-xl border bg-card p-6">
        <h2 className="text-xl font-semibold">Этапы найма</h2>
        <p className="mt-2 text-sm text-muted-foreground">Компания пока не предоставила маршрут отбора по этой вакансии.</p>
      </section>
    )
  }

  return (
    <PipelineGraphPanel
      pipeline={localPreview ?? example}
      label={localPreview ? 'Локальный предпросмотр' : 'Пример маршрута'}
      note={localPreview
        ? 'Маршрут из конструктора для просмотра в этом браузере. Ветки группируют этапы; порядок прохождения — сверху вниз. Статусы вашего отбора здесь не показаны.'
        : 'Демонстрационный маршрут для оценки интерфейса. Компания ещё не предоставила свои этапы. Ветки группируют этапы; порядок — сверху вниз.'}
    />
  )
}
