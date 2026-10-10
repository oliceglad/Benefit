import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useBlocker } from '@tanstack/react-router'
import { Save } from 'lucide-react'
import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'

import { matchesKey, needKey, needsKey, saveNeed } from '@/features/talent/api/needs'
import { needFormSchema, needFormValues, needPayload, type NeedFormValues } from '@/features/talent/model/need-form'
import { formatLabels, gradeLabels, roleLabels } from '@/features/talent/model/talent-search'
import { WorkFormat, type NeedResponse } from '@/shared/api/generated/employers/models'
import { isApiError } from '@/shared/api/transport/api-error'
import { RequestError } from '@/shared/api/ui/request-error'
import { useSession } from '@/shared/session/session'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/shared/ui/alert-dialog'
import { Button } from '@/shared/ui/button'
import { Checkbox } from '@/shared/ui/checkbox'
import { FormField, formSelectClass } from '@/shared/ui/form-field'
import { Input } from '@/shared/ui/input'
import { Spinner } from '@/shared/ui/spinner'
import { Textarea } from '@/shared/ui/textarea'

export function NeedEditor({ need, onSaved, onCancel }: { need?: NeedResponse; onSaved: (need: NeedResponse) => void; onCancel: () => void }) {
  const userId = useSession().user?.id
  const client = useQueryClient()
  const [cancelRequested, setCancelRequested] = useState(false)
  const form = useForm<NeedFormValues>({ resolver: zodResolver(needFormSchema), defaultValues: needFormValues(need) })
  const isDirty = form.formState.isDirty
  const mutation = useMutation({
    mutationFn: (values: NeedFormValues) => saveNeed(needPayload(values), need?.id),
    onSuccess: async (saved) => {
      await client.cancelQueries({ queryKey: needsKey(userId) })
      await client.cancelQueries({ queryKey: matchesKey(userId, saved.id) })
      client.setQueryData(needKey(userId, saved.id), saved)
      client.setQueryData<NeedResponse[]>(needsKey(userId), (current) => [saved, ...(current ?? []).filter((item) => item.id !== saved.id)])
      void client.invalidateQueries({ queryKey: needsKey(userId), exact: true })
      void client.invalidateQueries({ queryKey: matchesKey(userId, saved.id) })
      form.reset(needFormValues(saved))
      onSaved(saved)
    },
    onError: (error) => {
      if (!isApiError(error)) return
      for (const issue of error.fieldIssues) {
        const field = Object.keys(needFormSchema.shape).find((name) => issue.field.split('.').includes(name))
        if (field) form.setError(field as keyof NeedFormValues, { type: 'server', message: issue.message })
      }
    },
  })
  const blocker = useBlocker({
    shouldBlockFn: () => isDirty || mutation.isPending,
    enableBeforeUnload: () => isDirty || mutation.isPending,
    withResolver: true,
  })
  const errors = form.formState.errors
  const save = form.handleSubmit((values) => mutation.mutate(values))

  return (
    <section aria-label={need ? 'Редактирование потребности' : 'Создание потребности'} className="space-y-5 rounded-xl border bg-card p-6 shadow-card">
      <div className="space-y-2"><h2 className="text-xl font-semibold">{need ? 'Условия подбора' : 'Кто нужен вашей команде'}</h2><p className="text-sm leading-6 text-muted-foreground">Опишите роль и требования. После сохранения покажем подходящие категории и кандидатов с объяснением. Потребность не публикуется как вакансия.</p></div>
      <form noValidate onSubmit={(event) => { void save(event) }} className="space-y-6">
        <fieldset disabled={mutation.isPending} className="min-w-0 space-y-5">
          <legend className="sr-only">Требования команды</legend>
          <FormField id="need-title" label="Название потребности" required error={errors.title?.message}>{(props) => <Input {...props} maxLength={200} placeholder="Python-разработчик в команду платежей" {...form.register('title')} />}</FormField>
          <div className="grid gap-5 sm:grid-cols-2">
            <FormField id="need-specialization" label="Специализация" required error={errors.specialization?.message}>{(props) => <select {...props} className={formSelectClass} {...form.register('specialization')}>{Object.entries(roleLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>}</FormField>
            <FormField id="need-grade" label="Целевой грейд" required error={errors.grade?.message}>{(props) => <select {...props} className={formSelectClass} {...form.register('grade')}>{Object.entries(gradeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>}</FormField>
          </div>
          <FormField id="need-team" label="Задачи и команда" required error={errors.team_description?.message} hint="Чем занимается команда и над чем будет работать специалист.">{(props) => <Textarea {...props} rows={4} maxLength={8000} {...form.register('team_description')} />}</FormField>
          <div className="grid gap-5 sm:grid-cols-2">
            <FormField id="need-required" label="Обязательные навыки" required error={errors.required_skills?.message} hint="Через запятую; до 30 навыков.">{(props) => <Input {...props} placeholder="Python, PostgreSQL" {...form.register('required_skills')} />}</FormField>
            <FormField id="need-optional" label="Желательные навыки" error={errors.optional_skills?.message} hint="Усиливают соответствие, но не обязательны.">{(props) => <Input {...props} placeholder="Docker, Kafka" {...form.register('optional_skills')} />}</FormField>
          </div>
          <div className="grid gap-5 sm:grid-cols-3">
            <FormField id="need-salary-from" label="Бюджет от" error={errors.salary_from?.message}>{(props) => <Input {...props} inputMode="numeric" {...form.register('salary_from')} />}</FormField>
            <FormField id="need-salary-to" label="Бюджет до" error={errors.salary_to?.message}>{(props) => <Input {...props} inputMode="numeric" {...form.register('salary_to')} />}</FormField>
            <FormField id="need-currency" label="Валюта" error={errors.currency?.message}>{(props) => <Input {...props} readOnly {...form.register('currency')} />}</FormField>
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            <FormField id="need-city" label="Город" error={errors.city?.message}>{(props) => <Input {...props} maxLength={100} {...form.register('city')} />}</FormField>
            <FormField id="need-headcount" label="Количество сотрудников" required error={errors.headcount?.message}>{(props) => <Input {...props} type="number" min={1} max={100} {...form.register('headcount')} />}</FormField>
          </div>
          <fieldset className="space-y-2"><legend className="mb-2 text-sm font-medium">Форматы работы</legend><Controller control={form.control} name="work_formats" render={({ field }) => <div className="flex flex-wrap gap-5">{Object.values(WorkFormat).map((format) => <label key={format} className="flex items-center gap-2 text-sm"><Checkbox checked={field.value.includes(format)} onCheckedChange={(checked) => field.onChange(checked ? [...field.value, format] : field.value.filter((item) => item !== format))} />{formatLabels[format]}</label>)}</div>} />{errors.work_formats?.message ? <p role="alert" className="text-xs text-destructive">{errors.work_formats.message}</p> : null}</fieldset>
          <details className="rounded-lg border p-4" open={Boolean(errors.min_experience_months || errors.grade_tolerance || errors.work_formats)}>
            <summary className="cursor-pointer text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring">Точность подбора</summary>
            <div className="mt-5 space-y-5">
              <p className="text-xs leading-5 text-muted-foreground">Строгие условия исключают кандидатов. Остальные требования влияют на порядок рекомендаций.</p>
              <div className="grid gap-5 sm:grid-cols-2">
                <FormField id="need-tolerance" label="Допустимое отклонение грейда" error={errors.grade_tolerance?.message}>{(props) => <select {...props} className={formSelectClass} {...form.register('grade_tolerance', { valueAsNumber: true })}><option value={0}>Только целевой грейд</option><option value={1}>На одну ступень выше или ниже</option><option value={2}>На две ступени</option><option value={3}>На три ступени</option><option value={4}>Любой грейд</option></select>}</FormField>
                <FormField id="need-experience" label="Минимальный опыт, месяцев" error={errors.min_experience_months?.message} hint="12 месяцев = 1 год. Пустое поле — без ограничения.">{(props) => <Input {...props} type="number" min={0} max={600} {...form.register('min_experience_months')} />}</FormField>
              </div>
              {([
                ['require_confirmed_grade', 'Только с подтверждённым тестом грейдом'],
                ['strict_skills', 'Требовать все обязательные навыки; близкие технологии не заменяют их'],
                ['hard_budget', 'Исключать ожидания выше верхней границы бюджета'],
                ['strict_format', 'Исключать кандидатов с несовпадающим форматом работы'],
              ] as const).map(([name, label]) => <Controller key={name} control={form.control} name={name} render={({ field }) => <label className="flex items-start gap-3 text-sm leading-6"><Checkbox className="mt-1" checked={field.value} onCheckedChange={(checked) => field.onChange(checked === true)} />{label}</label>} />)}
            </div>
          </details>
        </fieldset>
        {mutation.isError ? <RequestError error={mutation.error} /> : null}
        <div className="flex flex-wrap gap-3"><Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? <Spinner label="Сохраняем…" /> : <Save size={16} aria-hidden="true" />}Сохранить и подобрать</Button><Button type="button" variant="outline" disabled={mutation.isPending} onClick={() => isDirty ? setCancelRequested(true) : onCancel()}>Отмена</Button></div>
      </form>
      <AlertDialog open={cancelRequested || blocker.status === 'blocked'}>
        <AlertDialogContent><AlertDialogHeader><AlertDialogTitle>{mutation.isPending ? 'Дождитесь сохранения' : 'Выйти без сохранения?'}</AlertDialogTitle><AlertDialogDescription>{mutation.isPending ? 'Запрос уже отправлен. Результат появится после ответа сервера.' : 'Изменения условий подбора будут потеряны.'}</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel onClick={() => { setCancelRequested(false); blocker.reset?.() }}>Остаться</AlertDialogCancel>{!mutation.isPending ? <Button variant="outline" onClick={() => { if (cancelRequested) { setCancelRequested(false); onCancel() } else blocker.proceed?.() }}>Выйти</Button> : null}</AlertDialogFooter></AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
