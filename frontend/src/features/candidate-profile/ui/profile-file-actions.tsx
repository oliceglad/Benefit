import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Download, FileCheck2, FileText, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import {
  downloadCandidateResume,
  inspectCandidateResume,
} from '@/features/candidate-profile/api/files'
import { candidateProfileQueryKey, getCandidateProfile, updateCandidateProfile } from '@/features/candidate-profile/api/profile'
import type { ProfileDictionaries } from '@/features/candidate-profile/model/dictionaries'
import { validateResumeFile } from '@/features/candidate-profile/model/file-validation'
import { profileDraft, type DraftSnapshot } from '@/features/candidate-profile/model/profile-draft'
import { buildSelectedResumeUpdate } from '@/features/candidate-profile/model/resume-import-selection'
import {
  appliedFieldLabel,
  buildResumeReview,
  type ResumeFieldEffect,
} from '@/features/candidate-profile/model/resume-import-review'
import type { ProfileResponse, ResumeImportResponse } from '@/shared/api/generated/candidates/models'
import { isApiError } from '@/shared/api/transport/api-error'
import { createPrivateObjectUrl, revokePrivateObjectUrl } from '@/shared/lib/private-object-url'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/ui/alert-dialog'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Checkbox } from '@/shared/ui/checkbox'
import { Spinner } from '@/shared/ui/spinner'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/shared/ui/table'

type PendingIntent = 'import' | 'export' | null
type Confirmation = 'confirmed' | 'unconfirmed' | null

export function ProfileFileActions({
  profile,
  dictionaries,
  draft,
  onImportActiveChange,
}: {
  profile: ProfileResponse
  dictionaries: ProfileDictionaries
  draft: DraftSnapshot
  onImportActiveChange: (active: boolean) => void
}) {
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ResumeImportResponse | null>(null)
  const [selectedFields, setSelectedFields] = useState<Set<string>>(new Set())
  const [appliedFields, setAppliedFields] = useState<string[] | null>(null)
  const [confirmation, setConfirmation] = useState<Confirmation>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [pendingIntent, setPendingIntent] = useState<PendingIntent>(null)
  const [savingDraft, setSavingDraft] = useState(false)

  useEffect(() => () => onImportActiveChange(false), [onImportActiveChange])

  const inspect = useMutation({
    mutationFn: inspectCandidateResume,
    onSuccess: (result) => {
      setPreview(result)
      setSelectedFields(new Set())
    },
  })
  const apply = useMutation({
    mutationFn: async ({ draft, selected }: { draft: Record<string, unknown>; selected: ReadonlySet<string> }) => {
      const update = buildSelectedResumeUpdate(draft, profile, selected)
      await updateCandidateProfile(update)
      const fields = Object.keys(update)
      try {
        const fresh = await getCandidateProfile()
        return { fields, fresh, confirmation: 'confirmed' as const }
      } catch {
        return { fields, fresh: null, confirmation: 'unconfirmed' as const }
      }
    },
    onSuccess: ({ fields, fresh, confirmation: resultConfirmation }) => {
      if (fresh) queryClient.setQueryData(candidateProfileQueryKey, fresh)
      setAppliedFields(fields)
      setConfirmation(resultConfirmation)
    },
  })
  const download = useMutation({
    mutationFn: () => downloadCandidateResume(),
    onSuccess: ({ blob, filename }) => {
      const url = createPrivateObjectUrl(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      anchor.click()
      window.setTimeout(() => revokePrivateObjectUrl(url), 0)
    },
  })

  function requestImport(): void {
    if (draft.isDirty) setPendingIntent('import')
    else inputRef.current?.click()
  }

  function requestExport(): void {
    if (draft.isDirty) setPendingIntent('export')
    else download.mutate()
  }

  function selectResume(next: File | undefined): void {
    if (!next) return
    const validation = validateResumeFile(next)
    setFileError(validation)
    if (validation) return
    setFile(next)
    setPreview(null)
    setAppliedFields(null)
    setSelectedFields(new Set())
    setConfirmation(null)
    onImportActiveChange(true)
    inspect.mutate(next)
  }

  function closeImport(): void {
    inspect.reset()
    apply.reset()
    setFile(null)
    setPreview(null)
    setAppliedFields(null)
    setSelectedFields(new Set())
    setConfirmation(null)
    if (inputRef.current) inputRef.current.value = ''
    onImportActiveChange(false)
  }

  async function saveBeforeIntent(): Promise<void> {
    const intent = pendingIntent
    if (!intent) return
    setSavingDraft(true)
    const saved = await profileDraft.save()
    setSavingDraft(false)
    if (!saved) return
    profileDraft.forceClean()
    setPendingIntent(null)
    if (intent === 'import') inputRef.current?.click()
    else download.mutate()
  }

  function discardBeforeImport(): void {
    profileDraft.discard()
    profileDraft.forceClean()
    setPendingIntent(null)
    inputRef.current?.click()
  }

  function exportSavedVersion(): void {
    setPendingIntent(null)
    download.mutate()
  }

  return (
    <div className="space-y-4">
      <input ref={inputRef} className="sr-only" type="file" accept="application/pdf,.pdf" aria-label="Выбрать PDF-резюме" onChange={(event) => selectResume(event.target.files?.[0])} />
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        <Button type="button" variant="outline" disabled={file !== null || inspect.isPending || apply.isPending} onClick={requestImport}><Upload aria-hidden="true" />Загрузить резюме</Button>
        <Button type="button" variant="outline" disabled={download.isPending || apply.isPending} onClick={requestExport}>{download.isPending ? <Spinner label="Готовим PDF…" /> : <><Download aria-hidden="true" />Скачать резюме PDF</>}</Button>
      </div>

      {fileError ? <Alert variant="destructive"><AlertCircle className="size-4" aria-hidden="true" /><AlertTitle>Файл не подходит</AlertTitle><AlertDescription>{fileError}</AlertDescription></Alert> : null}
      {download.error ? <Alert variant="destructive"><AlertCircle className="size-4" aria-hidden="true" /><AlertTitle>Не удалось скачать резюме</AlertTitle><AlertDescription>{download.error.message}</AlertDescription></Alert> : null}

      {file ? (
        <ResumeImportPanel
          file={file}
          profile={profile}
          dictionaries={dictionaries}
          preview={preview}
          selectedFields={selectedFields}
          appliedFields={appliedFields}
          confirmation={confirmation}
          inspecting={inspect.isPending}
          inspectError={inspect.error}
          applying={apply.isPending}
          applyError={apply.error}
          onRetry={() => inspect.mutate(file)}
          onToggleField={(key, checked) => setSelectedFields((current) => {
            const next = new Set(current)
            if (checked) next.add(key)
            else next.delete(key)
            return next
          })}
          onSelectFields={(keys) => setSelectedFields(new Set(keys))}
          onApply={() => { if (preview) apply.mutate({ draft: preview.draft, selected: selectedFields }) }}
          onClose={closeImport}
        />
      ) : null}

      <AlertDialog open={pendingIntent !== null} onOpenChange={(open) => { if (!open && !savingDraft) setPendingIntent(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Есть несохранённые изменения</AlertDialogTitle>
            <AlertDialogDescription>{pendingIntent === 'import' ? 'Перед импортом сохраните текущий раздел или откажитесь от его изменений.' : 'PDF формируется из сохранённого профиля. Можно сохранить раздел или скачать последнюю сохранённую версию.'}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={savingDraft}>Остаться</AlertDialogCancel>
            {pendingIntent === 'import' ? <Button type="button" variant="outline" disabled={savingDraft} onClick={discardBeforeImport}>Не сохранять</Button> : <Button type="button" variant="outline" disabled={savingDraft} onClick={exportSavedVersion}>Скачать сохранённую версию</Button>}
            <Button type="button" disabled={savingDraft} onClick={() => void saveBeforeIntent()}>{savingDraft ? <Spinner label="Сохраняем…" /> : pendingIntent === 'import' ? 'Сохранить и выбрать PDF' : 'Сохранить и скачать'}</Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function ResumeImportPanel({
  file,
  profile,
  dictionaries,
  preview,
  selectedFields,
  appliedFields,
  confirmation,
  inspecting,
  inspectError,
  applying,
  applyError,
  onRetry,
  onToggleField,
  onSelectFields,
  onApply,
  onClose,
}: {
  file: File
  profile: ProfileResponse
  dictionaries: ProfileDictionaries
  preview: ResumeImportResponse | null
  selectedFields: ReadonlySet<string>
  appliedFields: string[] | null
  confirmation: Confirmation
  inspecting: boolean
  inspectError: Error | null
  applying: boolean
  applyError: Error | null
  onRetry: () => void
  onToggleField: (key: string, checked: boolean) => void
  onSelectFields: (keys: string[]) => void
  onApply: () => void
  onClose: () => void
}) {
  const sections = preview ? buildResumeReview(preview.draft, profile, dictionaries) : []
  const selectableKeys = sections.flatMap((section) => section.fields).filter((field) => field.effect !== 'keep').map((field) => field.key)
  if (appliedFields) {
    const labels = appliedFields.map(appliedFieldLabel)
    return (
      <Card>
        <CardContent className="space-y-4 p-5">
          <Alert variant={confirmation === 'unconfirmed' ? 'warning' : 'success'}><FileCheck2 className="size-4" aria-hidden="true" /><AlertTitle>Выбранные данные применены</AlertTitle><AlertDescription>{confirmation === 'unconfirmed' ? 'Изменения сохранены, но получить актуальный профиль пока не удалось.' : `Обновлено: ${labels.join(', ')}.`}</AlertDescription></Alert>
          <div className="flex justify-end"><Button type="button" onClick={onClose}>Вернуться к профилю</Button></div>
        </CardContent>
      </Card>
    )
  }
  return (
    <Card>
      <CardHeader><CardTitle>Проверка данных резюме</CardTitle><p className="break-all text-sm text-muted-foreground">{file.name}</p></CardHeader>
      <CardContent className="space-y-5">
        {inspecting ? <div className="grid min-h-36 place-items-center"><Spinner label="Обрабатываем резюме…" /></div> : null}
        {inspectError ? <Alert variant="destructive"><AlertCircle className="size-4" aria-hidden="true" /><AlertTitle>Не удалось обработать PDF</AlertTitle><AlertDescription className="space-y-3"><p>{isApiError(inspectError) ? inspectError.message : inspectError.message}</p><Button type="button" size="sm" variant="outline" onClick={onRetry}>Повторить</Button></AlertDescription></Alert> : null}
        {preview ? (
          <>
            <Alert><FileText className="size-4" aria-hidden="true" /><AlertTitle>Выберите данные для импорта</AlertTitle><AlertDescription>Отметьте только те поля, которые хотите применить. Новые навыки, роли, языки и ссылки добавятся к текущим; выбранные текстовые поля и записи опыта заменят текущие значения.</AlertDescription></Alert>
            {preview.warnings.length > 0 ? <Alert variant="warning"><AlertCircle className="size-4" aria-hidden="true" /><AlertTitle>Не всё удалось распознать</AlertTitle><AlertDescription><ul className="list-disc space-y-1 pl-5">{preview.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></AlertDescription></Alert> : null}
            {selectableKeys.length > 0 ? <div className="flex flex-wrap gap-2"><Button type="button" size="sm" variant="outline" onClick={() => onSelectFields(selectableKeys)}>Выбрать все изменения</Button><Button type="button" size="sm" variant="ghost" onClick={() => onSelectFields([])}>Снять выбор</Button></div> : null}
            {sections.length > 0 ? <div className="space-y-5">{sections.map((section) => <section key={section.id} className="overflow-hidden rounded-xl border"><h3 className="border-b bg-muted/30 px-4 py-3 font-semibold">{section.title}</h3><Table className="table-fixed"><TableHeader className="hidden md:table-header-group"><TableRow className="hover:bg-transparent"><TableHead className="w-[28%]">Поле</TableHead><TableHead className="w-[36%]">Из резюме</TableHead><TableHead className="w-[36%]">Сейчас в профиле</TableHead></TableRow></TableHeader><TableBody>{section.fields.map((field) => { const selectable = field.effect !== 'keep'; const checked = selectedFields.has(field.key); return <TableRow key={field.key} data-state={checked ? 'selected' : undefined} className="block px-4 py-4 md:table-row md:px-0 md:py-0"><TableCell className="block p-0 md:table-cell md:p-4"><label className={`flex items-start gap-3 ${selectable ? 'cursor-pointer' : 'text-muted-foreground'}`}><Checkbox className="mt-0.5" checked={checked} disabled={!selectable || applying} onCheckedChange={(value) => onToggleField(field.key, value === true)} aria-label={`Импортировать: ${field.label}`} /><span className="min-w-0"><span className="block font-medium text-foreground">{field.label}</span><EffectLabel effect={field.effect} /></span></label></TableCell><TableCell className="mt-4 block border-l-2 border-primary/25 p-0 pl-3 md:mt-0 md:table-cell md:border-l-0 md:p-4"><ReviewColumn title="Из резюме" value={field.incoming} /></TableCell><TableCell className="mt-3 block border-l-2 border-border p-0 pl-3 md:mt-0 md:table-cell md:border-l-0 md:p-4"><ReviewColumn title="Сейчас в профиле" value={field.current} empty="Не заполнено" /></TableCell></TableRow>})}</TableBody></Table></section>)}</div> : <p className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">Подходящих данных в PDF не найдено.</p>}
            <p className="text-xs leading-5 text-muted-foreground">Согласия, публикация, подтверждённый грейд и результаты проверки навыков не импортируются.</p>
          </>
        ) : null}
        {applyError ? <Alert variant="destructive"><AlertCircle className="size-4" aria-hidden="true" /><AlertTitle>Данные не применены</AlertTitle><AlertDescription>{isApiError(applyError) ? applyError.message : applyError.message}</AlertDescription></Alert> : null}
        <div className="flex flex-col-reverse gap-2 border-t pt-5 sm:flex-row sm:justify-end"><Button type="button" variant="outline" disabled={applying} onClick={onClose}>Отмена</Button>{preview && selectableKeys.length > 0 ? <Button type="button" disabled={applying || selectedFields.size === 0} onClick={onApply}>{applying ? <Spinner label="Применяем…" /> : selectedFields.size > 0 ? `Применить выбранное (${selectedFields.size})` : 'Выберите данные'}</Button> : null}</div>
      </CardContent>
    </Card>
  )
}

function EffectLabel({ effect }: { effect: ResumeFieldEffect }) {
  const content = effect === 'fill' ? 'Заполнит пустое поле' : effect === 'merge' ? 'Добавит новые значения' : effect === 'replace' ? 'Заменит текущее' : 'Совпадает с текущим'
  const tone = effect === 'replace' ? 'text-warning-foreground' : effect === 'keep' ? 'text-muted-foreground' : 'text-success-foreground'
  return <span className={`mt-1 block text-xs font-medium ${tone}`}>{content}</span>
}

function ReviewColumn({ title, value, empty = 'Не найдено' }: { title: string; value: unknown; empty?: string }) {
  return <div className="min-w-0"><p className="mb-1 text-xs font-medium text-muted-foreground md:hidden">{title}</p><ReviewValue value={value} empty={empty} /></div>
}

function ReviewValue({ value, empty }: { value: unknown; empty: string }) {
  if (value === null || value === undefined || value === '' || (Array.isArray(value) && value.length === 0)) return <p className="mt-1 text-sm text-muted-foreground">{empty}</p>
  if (typeof value === 'boolean') return <p className="mt-1 break-words text-sm">{value ? 'Да' : 'Нет'}</p>
  if (typeof value === 'string' || typeof value === 'number') return <p className="mt-1 whitespace-pre-wrap break-words text-sm">{String(value)}</p>
  if (Array.isArray(value)) {
    const items: unknown[] = value
    return <div className="divide-y divide-border/70">{items.map((item, index) => <div key={index} className="py-2 first:pt-0 last:pb-0"><ReviewValue value={item} empty={empty} /></div>)}</div>
  }
  if (isRecord(value)) return <dl className="mt-2 space-y-1.5">{Object.entries(value).filter(([, item]) => item !== null && item !== '' && !(Array.isArray(item) && item.length === 0)).map(([key, item]) => <div key={key} className="grid gap-0.5"><dt className="text-xs text-muted-foreground">{nestedLabel(key)}</dt><dd><ReviewValue value={item} empty={empty} /></dd></div>)}</dl>
  return <p className="mt-1 text-sm text-muted-foreground">{empty}</p>
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function nestedLabel(key: string): string {
  const labels: Record<string, string> = { name: 'Название', level: 'Уровень', years: 'Лет опыта', language: 'Язык', company: 'Компания', position: 'Должность', start_date: 'Начало', end_date: 'Окончание', city: 'Город', description: 'Описание', achievements: 'Достижения', technologies: 'Технологии', institution: 'Учебное заведение', faculty: 'Факультет', degree: 'Уровень образования', graduation_year: 'Год окончания', organization: 'Организация', year: 'Год', role: 'Роль', url: 'Ссылка', type: 'Тип' }
  return labels[key] ?? key
}
