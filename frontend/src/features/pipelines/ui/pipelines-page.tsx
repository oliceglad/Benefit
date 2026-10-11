import { useQuery } from '@tanstack/react-query'
import { Link, useBlocker } from '@tanstack/react-router'
import { ArrowDown, ArrowUp, Check, ChevronDown, ChevronRight, Eye, GitBranch, Pencil, Plus, Save, Trash2 } from 'lucide-react'
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
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/shared/ui/collapsible'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from '@/shared/ui/dropdown-menu'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'
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
  const [openStageId, setOpenStageId] = useState<string | null>(() => draft.stages[0]?.id ?? null)
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
      if (!preview) {
        const response = await myVacanciesApiV1EmployersVacanciesGet({}, requestOptions(signal))
        if (response.status !== 200) throw new Error('Не удалось загрузить вакансии для предпросмотра.')
        return response.data
      }
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
    setOpenStageId(pipeline.stages[0]?.id ?? null)
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
    <section className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-xl space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">Пайплайны</h1>
          <p className="text-sm leading-6 text-muted-foreground">
            Соберите последовательность этапов под вашу команду. Добавляйте, переименовывайте и меняйте их порядок.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setPreviewMode(!previewMode)}>
            {previewMode ? <Pencil aria-hidden="true" /> : <Eye aria-hidden="true" />}
            {previewMode ? 'Редактировать' : 'Предпросмотр'}
          </Button>
          <Button onClick={() => save()} disabled={!dirty}>
            <Save aria-hidden="true" />Сохранить черновик
          </Button>
          {import.meta.env.DEV ? (
            <Button variant="outline" disabled={!draft.vacancyId} onClick={showInVacancy}>Предпросмотр в вакансии</Button>
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
        <p className="text-xs text-muted-foreground">Черновик сохранён в этом браузере. На других устройствах он недоступен.</p>
      </div>
      {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
      {notice ? (
        <p role="status" className="flex items-center gap-2 text-sm text-success-foreground">
          <Check className="size-4" aria-hidden="true" />{notice}
        </p>
      ) : null}

      <div className="grid items-start gap-5 lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="hidden space-y-4 rounded-xl border bg-card p-4 lg:block">
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
            className="w-full whitespace-nowrap"
            disabled={dirty || saved.length >= 30}
            onClick={() => { const next = newPipeline(); edit(next); setOpenStageId(next.stages[0]?.id ?? null); setPreviewMode(false) }}
          >
            <Plus aria-hidden="true" />Новый пайплайн
          </Button>
          {dirty ? (
            <p className="text-xs leading-5 text-muted-foreground">Сохраните текущие изменения перед переключением.</p>
          ) : null}
        </aside>

        <div className="min-w-0 space-y-5">
          <div className="flex min-w-0 flex-col gap-3 rounded-xl border bg-card p-4 lg:hidden">
            <div className="flex items-center justify-between gap-3">
              <Label htmlFor="pipeline-draft-mobile">Мои черновики</Label>
              <span className="text-xs text-muted-foreground">{saved.length}</span>
            </div>
            {saved.length ? (
              <Select
                value={saved.some((pipeline) => pipeline.id === draft.id) ? draft.id : 'current-unsaved'}
                disabled={dirty}
                onValueChange={(value) => {
                  const selected = saved.find((pipeline) => pipeline.id === value)
                  if (selected) switchDraft(selected)
                }}
              >
                <SelectTrigger id="pipeline-draft-mobile"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {!saved.some((pipeline) => pipeline.id === draft.id) ? <SelectItem value="current-unsaved">{draft.name}</SelectItem> : null}
                  {saved.map((pipeline) => <SelectItem key={pipeline.id} value={pipeline.id}>{pipeline.name}</SelectItem>)}
                </SelectContent>
              </Select>
            ) : <p className="text-xs leading-5 text-muted-foreground">Сохраните первый пайплайн — он появится здесь.</p>}
            <Button
              variant="outline"
              className="w-full"
              disabled={dirty || saved.length >= 30}
              onClick={() => { const next = newPipeline(); edit(next); setOpenStageId(next.stages[0]?.id ?? null); setPreviewMode(false) }}
            >
              <Plus aria-hidden="true" />Новый пайплайн
            </Button>
            {dirty ? <p className="text-xs leading-5 text-muted-foreground">Сохраните текущие изменения перед переключением.</p> : null}
          </div>

          <div className="grid gap-4 rounded-xl border bg-card p-5 sm:grid-cols-2">
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
              <Select value={draft.vacancyId ?? 'not-linked'} disabled={vacancies.isPending || vacancies.isError} onValueChange={(value) => edit({ ...draft, vacancyId: value === 'not-linked' ? undefined : value })}>
                <SelectTrigger id="pipeline-vacancy"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="not-linked">Без привязки к вакансии</SelectItem>
                  {vacancies.data?.map((vacancy) => <SelectItem key={vacancy.id} value={vacancy.id}>{vacancy.title}</SelectItem>)}
                </SelectContent>
              </Select>
              {vacancies.isError ? (
                <p className="text-xs text-muted-foreground">Список вакансий недоступен. Черновик можно сохранить без привязки.</p>
              ) : null}
              {import.meta.env.DEV ? <p className="text-xs leading-5 text-muted-foreground">«Предпросмотр в вакансии» создаёт только локальный просмотр. Кандидатам он не публикуется.</p> : null}
              {preview && currentSession.status === 'anonymous' ? <p className="text-xs leading-5 text-muted-foreground">Войдите в аккаунт, чтобы выбрать вакансию для предпросмотра.</p> : null}
            </div>
          </div>

          {previewMode ? <PipelineGraphPanel pipeline={draft} label="Предпросмотр" note="Так маршрут будет выглядеть в вакансии. Ветки группируют типы этапов; порядок прохождения — сверху вниз." /> : (
              <div className="min-w-0 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2 px-1">
                  <h2 className="text-sm font-semibold">Этапы отбора</h2>
                  <StageLibrary count={draft.stages.length} onAdd={(stage) => { edit({ ...draft, stages: [...draft.stages, stage] }); setOpenStageId(stage.id) }} />
                </div>
                <div className="relative space-y-2 before:absolute before:bottom-6 before:left-[1.65rem] before:top-6 before:w-px before:bg-border">
                  {draft.stages.map((stage, index) => (
                  <StageEditor
                    key={stage.id}
                    stage={stage}
                    index={index}
                    count={draft.stages.length}
                    open={openStageId === stage.id}
                    onOpenChange={(open) => setOpenStageId(open ? stage.id : null)}
                    onChange={(next) => edit({ ...draft, stages: draft.stages.map((item) => item.id === next.id ? next : item) })}
                    onMove={(direction) => edit({ ...draft, stages: moveStage(draft.stages, index, direction) })}
                    onRemove={() => { const next = draft.stages.filter((item) => item.id !== stage.id); edit({ ...draft, stages: next }); setOpenStageId(next[Math.min(index, next.length - 1)]?.id ?? null) }}
                  />))}
                </div>
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

function StageEditor({ stage, index, count, open, onOpenChange, onChange, onMove, onRemove }: {
  stage: PipelineStage
  index: number
  count: number
  open: boolean
  onOpenChange: (open: boolean) => void
  onChange: (stage: PipelineStage) => void
  onMove: (direction: -1 | 1) => void
  onRemove: () => void
}) {
  const [confirmRemove, setConfirmRemove] = useState(false)
  return (
    <Collapsible open={open} onOpenChange={onOpenChange} asChild>
    <article className="relative rounded-xl border bg-card p-3 sm:p-4">
      <div className="flex min-w-0 flex-wrap items-start gap-3">
        <span className="relative z-10 inline-flex size-8 shrink-0 items-center justify-center rounded-full border bg-card text-xs font-semibold text-primary">{index + 1}</span>
        <CollapsibleTrigger asChild>
          <button type="button" className="flex min-h-11 min-w-0 flex-1 items-center gap-2 rounded-lg px-2 text-left outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring" aria-label={`${open ? 'Свернуть' : 'Редактировать'} этап ${index + 1}: ${stage.title}`}>
            {open ? <ChevronDown className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" /> : <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />}
            <span className="min-w-0"><span className="block break-words text-sm font-semibold">{stage.title}</span>{!open && stage.description ? <span className="mt-1 block line-clamp-1 break-words text-xs text-muted-foreground">{stage.description}</span> : null}</span>
          </button>
        </CollapsibleTrigger>
        <div className="ml-11 flex w-full shrink-0 justify-end gap-1 sm:ml-0 sm:w-auto">
          <Button size="icon" variant="ghost" aria-label={`Поднять этап ${index + 1}`} disabled={index === 0} onClick={() => onMove(-1)}>
            <ArrowUp aria-hidden="true" />
          </Button>
          <Button size="icon" variant="ghost" aria-label={`Опустить этап ${index + 1}`} disabled={index === count - 1} onClick={() => onMove(1)}>
            <ArrowDown aria-hidden="true" />
          </Button>
          <Button size="icon" variant="ghost" aria-label={`Удалить этап ${index + 1}`} disabled={count === 1} onClick={() => setConfirmRemove(true)}>
            <Trash2 aria-hidden="true" />
          </Button>
        </div>
      </div>
      <CollapsibleContent className="space-y-4 pt-4 sm:pl-11">
      <div className="space-y-2">
        <Label htmlFor={`title-${stage.id}`}>Название этапа {index + 1}</Label>
        <Input id={`title-${stage.id}`} maxLength={80} value={stage.title} onChange={(event) => onChange({ ...stage, title: event.target.value })} />
      </div>
      <div className="space-y-2">
        <Label htmlFor={`description-${stage.id}`}>Описание</Label>
        <Textarea id={`description-${stage.id}`} rows={2} maxLength={500} value={stage.description} onChange={(event) => onChange({ ...stage, description: event.target.value })} />
      </div>
      {confirmRemove ? <div className="flex flex-wrap items-center justify-end gap-2 rounded-lg bg-destructive/5 p-2"><span className="mr-auto text-xs text-destructive">Удалить этот этап?</span><Button size="sm" variant="ghost" onClick={() => setConfirmRemove(false)}>Отмена</Button><Button size="sm" variant="destructive" onClick={onRemove}>Удалить</Button></div> : null}
      </CollapsibleContent>
    </article>
    </Collapsible>
  )
}

function StageLibrary({ count, onAdd }: { count: number; onAdd: (stage: PipelineStage) => void }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild><Button size="sm" variant="outline" disabled={count >= 16}><Plus aria-hidden="true" />Добавить этап</Button></DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[min(22rem,calc(100vw-2rem))]">
        <DropdownMenuLabel><span className="block">Готовые этапы</span><span className="mt-1 block text-xs font-normal text-muted-foreground">Этап добавится в конец последовательности.</span></DropdownMenuLabel>
        {stageCatalog.map((template) => <DropdownMenuItem key={template.kind} className="items-start" onSelect={() => onAdd(newStage(template))}><Plus className="mt-0.5" aria-hidden="true" /><span><span className="block font-medium">{template.title}</span><span className="mt-1 block text-xs leading-5 text-muted-foreground">{template.description}</span></span></DropdownMenuItem>)}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
