import { useQuery } from '@tanstack/react-query'
import { Link, useBlocker } from '@tanstack/react-router'
import { ArrowDown, ArrowUp, Check, Eye, GitBranch, Pencil, Plus, Save, Trash2 } from 'lucide-react'
import { useState } from 'react'

import {
  moveStage,
  newPipeline,
  newStage,
  pipelineDraftSchema,
  readPipelineDrafts,
  savePipelineDraft,
  stageCatalog,
  type PipelineDraft,
  type PipelineStage,
} from '@/features/pipelines/model/pipeline-draft'
import { attachVacancyPipelinePreview } from '@/features/pipelines/model/vacancy-pipeline-preview'
import { PipelineGraphPanel } from '@/features/pipelines/ui/pipeline-graph-panel'
import { listVacanciesApiV1VacanciesGet, myVacanciesApiV1EmployersVacanciesGet } from '@/shared/api/generated/employers/employers'
import { requestOptions } from '@/shared/lib/request-options'
import { useSession } from '@/shared/session/session'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/ui/alert-dialog'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Textarea } from '@/shared/ui/textarea'

function loadDrafts(accountId: string) {
  try {
    return { pipelines: readPipelineDrafts(accountId), error: '' }
  } catch {
    return {
      pipelines: [] as PipelineDraft[],
      error: 'Не удалось прочитать локальные черновики. Проверьте доступ браузера к хранилищу.',
    }
  }
}
export function PipelinesPage({ preview = false }: { preview?: boolean }) {
  const user = useSession().user
  const accountId = preview ? 'design-preview' : user?.id ?? 'anonymous'
  return <PipelineWorkspace key={accountId} accountId={accountId} preview={preview} />
}

function PipelineWorkspace({ accountId, preview }: { accountId: string; preview: boolean }) {
  const currentSession = useSession()
  const [initial] = useState(() => loadDrafts(accountId))
  const [saved, setSaved] = useState(initial.pipelines)
  const [draft, setDraft] = useState(() => initial.pipelines[0] ?? newPipeline())
  const [error, setError] = useState(initial.error)
  const [notice, setNotice] = useState('')
  const [previewMode, setPreviewMode] = useState(false)
  const original = saved.find((pipeline) => pipeline.id === draft.id)
  const dirty = JSON.stringify(original) !== JSON.stringify(draft)
  const blocker = useBlocker({
    shouldBlockFn: () => dirty,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  })
  const vacancies = useQuery({
    queryKey: ['vacancies', 'pipeline-options', preview ? 'catalog' : 'own'],
    queryFn: async ({ signal }) => {
      if (!preview) return (await myVacanciesApiV1EmployersVacanciesGet(requestOptions(signal))).data
      const response = await listVacanciesApiV1VacanciesGet({ limit: 100 }, requestOptions(signal))
      if (response.status !== 200) throw new Error('Не удалось загрузить вакансии для предпросмотра.')
      return response.data.items
    },
    enabled: !preview || currentSession.status === 'authenticated',
  })

  function edit(next: PipelineDraft) {
    setDraft(next)
    setNotice('')
  }

  function save(): boolean {
    if (!pipelineDraftSchema.safeParse(draft).success) {
      setError('Укажите название пайплайна и названия всех этапов. Допустимо от 1 до 16 этапов.')
      return false
    }
    try {
      const next = savePipelineDraft(accountId, draft)
      setSaved(next)
      setDraft(next[0])
      setError('')
      setNotice('Черновик сохранён в этом браузере.')
      return true
    } catch (cause) {
      setError(cause instanceof Error && cause.message.includes('30 пайплайнов')
        ? cause.message
        : 'Не удалось сохранить черновик. Проверьте свободное место и разрешения хранилища браузера.')
      return false
    }
  }

  function switchDraft(pipeline: PipelineDraft) {
    if (dirty || pipeline.id === draft.id) return
    setDraft(structuredClone(pipeline))
    setNotice('')
  }

  function showInVacancy() {
    if (!save()) return
    try {
      attachVacancyPipelinePreview(draft)
      setNotice('Предпросмотр прикреплён к вакансии в этом браузере.')
    } catch {
      setError('Не удалось прикрепить предпросмотр. Проверьте выбор вакансии и доступ к хранилищу браузера.')
    }
  }

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-xl space-y-2">
          <p className="text-sm font-medium text-primary">Ваш процесс найма</p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Пайплайны</h1>
          <p className="text-sm leading-6 text-muted-foreground">
            Соберите последовательность этапов под вашу команду. Добавляйте, переименовывайте и меняйте их порядок.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setPreviewMode(!previewMode)}>
            {previewMode ? <Pencil aria-hidden="true" /> : <Eye aria-hidden="true" />}
            {previewMode ? 'Редактировать' : 'Вид соискателя'}
          </Button>
          <Button onClick={() => save()} disabled={!dirty}>
            <Save aria-hidden="true" />Сохранить черновик
          </Button>
          {import.meta.env.DEV ? (
            <Button variant="outline" disabled={!draft.vacancyId} onClick={showInVacancy}>Показать в вакансии</Button>
          ) : null}
          {import.meta.env.DEV && draft.vacancyId ? (
            <Button asChild variant="ghost"><Link to="/vacancies/$vacancyId" params={{ vacancyId: draft.vacancyId }}>Открыть вакансию</Link></Button>
          ) : null}
        </div>
      </header>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary/15 bg-primary/5 px-4 py-3">
        <div className="flex items-center gap-2">
          <GitBranch className="size-4 text-primary" aria-hidden="true" />
          <span className="text-sm font-medium">Локальный черновик</span>
          <Badge variant="secondary">{draft.stages.length} этапов</Badge>
        </div>
        <p className="text-xs text-muted-foreground">Черновик доступен в этом браузере.</p>
      </div>
      {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
      {notice ? (
        <p role="status" className="flex items-center gap-2 text-sm text-success-foreground">
          <Check className="size-4" aria-hidden="true" />{notice}
        </p>
      ) : null}

      <div className="grid items-start gap-5 lg:grid-cols-[180px_minmax(0,1fr)]">
        <aside className="space-y-4 rounded-2xl border bg-card p-4 shadow-card">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">Мои черновики</h2>
            <span className="text-xs text-muted-foreground">{saved.length}</span>
          </div>
          <div className="space-y-2">
            {saved.map((pipeline) => (
              <button
                key={pipeline.id}
                disabled={dirty && pipeline.id !== draft.id}
                aria-current={pipeline.id === draft.id ? 'page' : undefined}
                onClick={() => switchDraft(pipeline)}
                className={`min-h-11 w-full break-words rounded-lg px-3 py-2 text-left text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 ${pipeline.id === draft.id ? 'bg-primary/10 font-medium text-primary' : 'hover:bg-muted'}`}
              >
                {pipeline.name}
              </button>
            ))}
            {saved.length === 0 ? (
              <p className="text-xs leading-5 text-muted-foreground">Сохраните первый пайплайн — он появится здесь.</p>
            ) : null}
          </div>
          <Button
            variant="outline"
            className="w-full"
            disabled={dirty || saved.length >= 30}
            onClick={() => { edit(newPipeline()); setPreviewMode(false) }}
          >
            <Plus aria-hidden="true" />Новый пайплайн
          </Button>
          {dirty ? (
            <p className="text-xs leading-5 text-muted-foreground">Сохраните текущие изменения перед переключением.</p>
          ) : null}
        </aside>

        <div className="min-w-0 space-y-5">
          <div className="grid gap-4 rounded-2xl border bg-card p-5 shadow-card sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="pipeline-name">Название пайплайна</Label>
              <Input
                id="pipeline-name"
                maxLength={120}
                value={draft.name}
                onChange={(event) => edit({ ...draft, name: event.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pipeline-vacancy">Вакансия</Label>
              <select
                id="pipeline-vacancy"
                className="min-h-12 w-full rounded-xl border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                disabled={vacancies.isPending || vacancies.isError}
                value={draft.vacancyId ?? ''}
                onChange={(event) => edit({ ...draft, vacancyId: event.target.value || undefined })}
              >
                <option value="">Без привязки к вакансии</option>
                {vacancies.data?.map((vacancy) => (
                  <option key={vacancy.id} value={vacancy.id}>{vacancy.title}</option>
                ))}
              </select>
              {vacancies.isError ? (
                <p className="text-xs text-muted-foreground">Список вакансий недоступен. Черновик можно сохранить без привязки.</p>
              ) : null}
              {import.meta.env.DEV ? <p className="text-xs leading-5 text-muted-foreground">«Показать в вакансии» прикрепит локальный предпросмотр для этого браузера.</p> : null}
              {preview && currentSession.status === 'anonymous' ? <p className="text-xs leading-5 text-muted-foreground">Войдите в аккаунт, чтобы выбрать вакансию для предпросмотра.</p> : null}
            </div>
          </div>

          {previewMode ? <PipelineGraphPanel pipeline={draft} label="Вид соискателя" note="Так маршрут будет выглядеть в вакансии. Ветки группируют типы этапов; порядок прохождения — сверху вниз." /> : (
            <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_260px]">
              <div className="min-w-0 space-y-3">
                <div className="flex items-center justify-between gap-2 px-1">
                  <h2 className="text-sm font-semibold">Этапы отбора</h2>
                  <span className="text-xs text-muted-foreground">Порядок сверху вниз</span>
                </div>
                {draft.stages.map((stage, index) => (
                  <StageEditor
                    key={stage.id}
                    stage={stage}
                    index={index}
                    count={draft.stages.length}
                    onChange={(next) => edit({ ...draft, stages: draft.stages.map((item) => item.id === next.id ? next : item) })}
                    onMove={(direction) => edit({ ...draft, stages: moveStage(draft.stages, index, direction) })}
                    onRemove={() => edit({ ...draft, stages: draft.stages.filter((item) => item.id !== stage.id) })}
                  />
                ))}
              </div>
              <StageLibrary
                count={draft.stages.length}
                onAdd={(stage) => edit({ ...draft, stages: [...draft.stages, stage] })}
              />
            </div>
          )}
        </div>
      </div>

      <AlertDialog
        open={blocker.status === 'blocked'}
        onOpenChange={(open) => { if (!open && blocker.status === 'blocked') blocker.reset() }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Сохранить изменения пайплайна?</AlertDialogTitle>
            <AlertDialogDescription>Несохранённые изменения будут потеряны при уходе со страницы.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Остаться</AlertDialogCancel>
            <Button variant="outline" onClick={() => { if (blocker.status === 'blocked') blocker.proceed() }}>
              Уйти без сохранения
            </Button>
            <Button onClick={() => { if (save() && blocker.status === 'blocked') blocker.proceed() }}>
              Сохранить и уйти
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}

function StageEditor({ stage, index, count, onChange, onMove, onRemove }: {
  stage: PipelineStage
  index: number
  count: number
  onChange: (stage: PipelineStage) => void
  onMove: (direction: -1 | 1) => void
  onRemove: () => void
}) {
  return (
    <article className="space-y-3 rounded-2xl border bg-card p-4 shadow-card">
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex size-7 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
          {index + 1}
        </span>
        <div className="flex gap-1">
          <Button size="icon" variant="ghost" aria-label={`Поднять этап ${index + 1}`} disabled={index === 0} onClick={() => onMove(-1)}>
            <ArrowUp aria-hidden="true" />
          </Button>
          <Button size="icon" variant="ghost" aria-label={`Опустить этап ${index + 1}`} disabled={index === count - 1} onClick={() => onMove(1)}>
            <ArrowDown aria-hidden="true" />
          </Button>
          <Button size="icon" variant="ghost" aria-label={`Убрать этап ${index + 1}`} disabled={count === 1} onClick={onRemove}>
            <Trash2 aria-hidden="true" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor={`title-${stage.id}`}>Название этапа {index + 1}</Label>
        <Input id={`title-${stage.id}`} maxLength={80} value={stage.title} onChange={(event) => onChange({ ...stage, title: event.target.value })} />
      </div>
      <div className="space-y-2">
        <Label htmlFor={`description-${stage.id}`}>Описание</Label>
        <Textarea id={`description-${stage.id}`} rows={2} maxLength={500} value={stage.description} onChange={(event) => onChange({ ...stage, description: event.target.value })} />
      </div>
    </article>
  )
}

function StageLibrary({ count, onAdd }: { count: number; onAdd: (stage: PipelineStage) => void }) {
  const [filter, setFilter] = useState('')
  const templates = stageCatalog.filter((stage) => (
    `${stage.title} ${stage.description}`.toLocaleLowerCase('ru').includes(filter.toLocaleLowerCase('ru'))
  ))
  return (
    <aside className="sticky top-5 space-y-4 rounded-2xl border bg-card p-4 shadow-card">
      <div>
        <h2 className="text-sm font-semibold">Библиотека этапов</h2>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">Выберите этап, чтобы добавить его в конец пайплайна.</p>
      </div>
      <Input aria-label="Найти этап" placeholder="Найти этап" value={filter} onChange={(event) => setFilter(event.target.value)} />
      <div className="max-h-[650px] space-y-2 overflow-y-auto">
        {templates.map((template) => (
          <button
            key={template.kind}
            disabled={count >= 16}
            onClick={() => onAdd(newStage(template))}
            className="group flex min-h-14 w-full items-start gap-2 rounded-xl border p-3 text-left outline-none transition-colors hover:border-primary/35 hover:bg-primary/5 focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-40"
          >
            <div className="min-w-0 flex-1">
              <span className="block text-sm font-medium">{template.title}</span>
              <span className="mt-1 block text-xs leading-5 text-muted-foreground">{template.description}</span>
            </div>
            <Plus className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
          </button>
        ))}
        {templates.length === 0 ? <p className="text-sm text-muted-foreground">Этапы не найдены.</p> : null}
      </div>
      {count >= 16 ? <p className="text-xs text-muted-foreground">Достигнут максимум: 16 этапов.</p> : null}
    </aside>
  )
}
