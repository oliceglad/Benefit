import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useBlocker, useNavigate, useParams } from '@tanstack/react-router'
import { ArrowLeft, Check, Eye, FileText, Pencil, Save } from 'lucide-react'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'

import { getVacancy, saveVacancy } from '@/features/vacancies/api/vacancies'
import { employmentLabels, specializationLabels, vacancyFormSchema, vacancyFormValues, vacancyPayload, type VacancyFormValues } from '@/features/vacancies/model/vacancy-form'
import { formatLabels, gradeLabels, vacancyStatusLabels } from '@/features/vacancies/model/vacancy-search'
import { VacancyCompanySetup } from '@/features/vacancies/ui/vacancy-company-setup'
import { VacancyFormField, vacancySelectClass } from '@/features/vacancies/ui/vacancy-form-field'
import { VacancyFormPreview } from '@/features/vacancies/ui/vacancy-form-preview'
import { getVacancyCompany } from '@/features/vacancies/api/vacancy-company'
import type { VacancyResponse } from '@/shared/api/generated/employers/models'
import { isApiError } from '@/shared/api/transport/api-error'
import { RequestError } from '@/shared/api/ui/request-error'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/shared/ui/alert-dialog'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Spinner } from '@/shared/ui/spinner'
import { Textarea } from '@/shared/ui/textarea'

export function VacancyEditorPage() {
  const { vacancyId } = useParams({ strict: false })
  const vacancy = useQuery({
    queryKey: ['vacancies', 'detail', vacancyId, true],
    queryFn: ({ signal }) => getVacancy(vacancyId!, true, signal),
    enabled: Boolean(vacancyId),
  })
  const company = useQuery({ queryKey: ['vacancy-company'], queryFn: ({ signal }) => getVacancyCompany(signal), enabled: !vacancyId })

  if (vacancyId && vacancy.isPending || !vacancyId && company.isPending) return <Spinner label="Готовим редактор…" />
  if (vacancyId && vacancy.isError) return <RequestError error={vacancy.error} onRetry={() => { void vacancy.refetch() }} />
  if (!vacancyId && company.isError) return <RequestError error={company.error} onRetry={() => { void company.refetch() }} />
  if (!vacancyId && company.data === null) return <VacancyCompanySetup />

  return <VacancyEditor key={vacancyId ?? 'new'} vacancy={vacancyId ? vacancy.data : undefined} companyName={vacancy.data?.company.name ?? company.data?.name ?? ''} />
}

function VacancyEditor({ vacancy, companyName }: { vacancy?: VacancyResponse; companyName: string }) {
  const client = useQueryClient()
  const navigate = useNavigate()
  const [preview, setPreview] = useState(false)
  const form = useForm<VacancyFormValues>({ resolver: zodResolver(vacancyFormSchema), defaultValues: vacancyFormValues(vacancy) })
  const values = useWatch({ control: form.control }) as VacancyFormValues
  const blocker = useBlocker({ shouldBlockFn: () => form.formState.isDirty, enableBeforeUnload: () => form.formState.isDirty, withResolver: true })
  const mutation = useMutation({
    mutationFn: (input: VacancyFormValues) => saveVacancy(vacancyPayload(input, vacancy?.need_id), vacancy?.id),
    onSuccess: async (saved) => {
      client.setQueryData(['vacancies', 'detail', saved.id, true], saved)
      void client.invalidateQueries({ queryKey: ['vacancies'] })
      form.reset(vacancyFormValues(saved))
      await navigate({ to: '/vacancies/$vacancyId', params: { vacancyId: saved.id }, ignoreBlocker: true })
    },
    onError: (error) => {
      if (!isApiError(error)) return
      error.fieldIssues.forEach((issue) => {
        const field = Object.keys(vacancyFormSchema.shape).find((name) => issue.field.split('.').includes(name))
        if (field) form.setError(field as keyof VacancyFormValues, { type: 'server', message: issue.message })
      })
    },
  })
  const save = form.handleSubmit((input) => mutation.mutate(input), () => setPreview(false))
  const errors = form.formState.errors
  const descriptionCount = values.description?.length ?? 0
  const readiness = [Boolean(values.title?.trim()), Boolean(values.description?.trim()), Boolean(values.skills?.trim())]

  return (
    <section className="space-y-6">
      <Button asChild variant="ghost" className="-ml-3">
        {vacancy ? <Link to="/vacancies/$vacancyId" params={{ vacancyId: vacancy.id }}><ArrowLeft aria-hidden="true" />К вакансии</Link> : <Link to="/vacancies" search={{ offset: 0 }}><ArrowLeft aria-hidden="true" />Мои вакансии</Link>}
      </Button>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-2xl space-y-2">
          <p className="text-sm font-medium text-primary">{companyName}</p>
          <div className="flex flex-wrap items-center gap-3"><h1 className="text-3xl font-semibold tracking-tight">{vacancy ? 'Редактирование вакансии' : 'Новая вакансия'}</h1><Badge variant="secondary">{vacancyStatusLabels[vacancy?.status ?? 'draft']}</Badge></div>
          <p className="text-sm leading-6 text-muted-foreground">{vacancy?.status === 'published' ? 'Сохранённые изменения сразу появятся в опубликованной вакансии.' : 'Опишите роль и условия. После сохранения можно проверить вакансию и опубликовать её.'}</p>
        </div>
        <Button variant="outline" onClick={() => setPreview(!preview)}><Eye aria-hidden="true" />{preview ? 'Вернуться к форме' : 'Предпросмотр'}</Button>
      </header>

      <form noValidate onSubmit={(event) => { void save(event) }} className="space-y-6">
        <fieldset disabled={mutation.isPending} className="grid min-w-0 gap-6 border-0 p-0 lg:grid-cols-[minmax(0,1fr)_320px]">
          <legend className="sr-only">Данные вакансии</legend>
          <div className="min-w-0 space-y-5">
            {preview ? <VacancyFormPreview values={values} company={companyName} full /> : (
              <>
                <section className="space-y-5 rounded-xl border bg-card p-6 shadow-card">
                  <FormSectionTitle number="01" title="Роль в команде" description="Название и направление помогут соискателю найти вашу вакансию." />
                  <VacancyFormField id="job-title" label="Название вакансии" required error={errors.title?.message}>
                    {(props) => <Input {...props} className="rounded-md" maxLength={200} placeholder="Например, Middle Backend-разработчик" {...form.register('title')} />}
                  </VacancyFormField>
                  <div className="grid gap-5 sm:grid-cols-2">
                    <VacancyFormField id="job-specialization" label="Специализация" required error={errors.specialization?.message}>
                      {(props) => <select {...props} className={vacancySelectClass} {...form.register('specialization')}>{Object.entries(specializationLabels).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>}
                    </VacancyFormField>
                    <VacancyFormField id="job-grade" label="Грейд" required error={errors.grade?.message}>
                      {(props) => <select {...props} className={vacancySelectClass} {...form.register('grade')}>{Object.entries(gradeLabels).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>}
                    </VacancyFormField>
                  </div>
                </section>
                <section className="space-y-5 rounded-xl border bg-card p-6 shadow-card">
                  <FormSectionTitle number="02" title="Условия работы" description="Формат, занятость и зарплатная вилка — без лишних догадок." />
                  <div className="grid gap-5 sm:grid-cols-2">
                    <VacancyFormField id="job-format" label="Формат работы" error={errors.work_format?.message}>
                      {(props) => <select {...props} className={vacancySelectClass} {...form.register('work_format')}><option value="">Не указан</option>{Object.entries(formatLabels).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>}
                    </VacancyFormField>
                    <VacancyFormField id="job-employment" label="Занятость" error={errors.employment_type?.message}>
                      {(props) => <select {...props} className={vacancySelectClass} {...form.register('employment_type')}><option value="">Не указана</option>{Object.entries(employmentLabels).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>}
                    </VacancyFormField>
                  </div>
                  <VacancyFormField id="job-city" label="Город" error={errors.city?.message}>
                    {(props) => <Input {...props} className="rounded-md" maxLength={100} placeholder="Например, Самара" {...form.register('city')} />}
                  </VacancyFormField>
                  <div className="grid gap-5 sm:grid-cols-[1fr_1fr_100px]">
                    <VacancyFormField id="job-salary-from" label="Зарплата от" error={errors.salary_from?.message}>
                      {(props) => <Input {...props} className="rounded-md" type="number" min={0} max={100000000} step={1} placeholder="180000" {...form.register('salary_from')} />}
                    </VacancyFormField>
                    <VacancyFormField id="job-salary-to" label="Зарплата до" error={errors.salary_to?.message}>
                      {(props) => <Input {...props} className="rounded-md" type="number" min={0} max={100000000} step={1} placeholder="240000" {...form.register('salary_to')} />}
                    </VacancyFormField>
                    <VacancyFormField id="job-currency" label="Валюта" error={errors.currency?.message}>
                      {(props) => <Input {...props} className="rounded-md uppercase" maxLength={3} {...form.register('currency')} />}
                    </VacancyFormField>
                  </div>
                  <p className="text-xs text-muted-foreground">Если зарплата пока не определена, оставьте обе границы пустыми.</p>
                </section>
                <section className="space-y-5 rounded-xl border bg-card p-6 shadow-card">
                  <FormSectionTitle number="03" title="Задачи и ожидания" description="Расскажите о команде, задачах, требованиях и том, что предлагаете." />
                  <VacancyFormField id="job-description" label="Описание вакансии" required error={errors.description?.message} hint={`${descriptionCount} / 8000 символов`}>
                    {(props) => <Textarea {...props} className="min-h-64 rounded-md" rows={10} maxLength={8000} placeholder={'О команде\n\nЧто предстоит делать\n\nЧто ожидаем\n\nЧто предлагаем'} {...form.register('description')} />}
                  </VacancyFormField>
                  <VacancyFormField id="job-skills" label="Ключевые навыки" error={errors.skills?.message} hint="Через запятую или с новой строки. До 30 навыков, каждый — до 64 символов.">
                    {(props) => <Textarea {...props} className="rounded-md" rows={2} placeholder="Python, PostgreSQL, Docker" {...form.register('skills')} />}
                  </VacancyFormField>
                </section>
              </>
            )}
          </div>
          <aside className="h-fit space-y-5 lg:sticky lg:top-6">
            {!preview ? (
              <>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Карточка вакансии</p>
                <VacancyFormPreview values={values} company={companyName} />
              </>
            ) : null}
            <div className="space-y-4 rounded-xl border bg-card p-5">
              <h2 className="flex items-center gap-2 text-sm font-semibold"><FileText className="size-4 text-primary" aria-hidden="true" />Перед сохранением</h2>
              {['Название роли', 'Описание работы', 'Ключевые навыки (необязательно)'].map((label, index) => (
                <p key={label} className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span className={`grid size-5 shrink-0 place-items-center rounded-full ${readiness[index] ? 'bg-primary/10 text-primary' : 'border'}`}>
                    {readiness[index] ? <Check className="size-3" aria-hidden="true" /> : null}
                  </span>
                  {label}
                </p>
              ))}
              <div className="border-t pt-4 text-xs leading-5 text-muted-foreground">{vacancy?.status === 'published' ? 'Изменения будут видны соискателям после сохранения.' : 'Сохранение не публикует вакансию. Публикация доступна на следующем экране.'}</div>
            </div>
            <div className="rounded-xl border border-primary/15 bg-primary/5 p-5 text-sm leading-6"><p className="font-semibold">Процесс найма</p><p className="mt-1 text-muted-foreground">После сохранения выберите вакансию в конструкторе пайплайнов и настройте этапы отбора.</p></div>
          </aside>
        </fieldset>

        {mutation.isError ? <RequestError error={mutation.error} /> : null}
        {Object.keys(errors).length ? <p role="alert" className="text-sm text-destructive">Проверьте отмеченные поля формы.</p> : null}
        <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card/95 p-4 shadow-card backdrop-blur-sm">
          <p className="text-sm text-muted-foreground" role="status">{mutation.isPending ? 'Сохраняем вакансию…' : form.formState.isDirty ? 'Есть несохранённые изменения' : vacancy ? 'Все изменения сохранены' : 'Новый черновик'}</p>
          <div className="flex flex-wrap gap-2">
            {preview ? <Button type="button" variant="outline" onClick={() => setPreview(false)} disabled={mutation.isPending}><Pencil aria-hidden="true" />К форме</Button> : null}
            <Button type="submit" disabled={mutation.isPending || Boolean(vacancy && !form.formState.isDirty)}>{mutation.isPending ? <Spinner label="Сохраняем…" /> : <Save aria-hidden="true" />}{vacancy ? 'Сохранить изменения' : 'Сохранить черновик'}</Button>
          </div>
        </div>
      </form>
      <AlertDialog open={blocker.status === 'blocked'}>
        <AlertDialogContent>
          <AlertDialogHeader><AlertDialogTitle>Оставить изменения?</AlertDialogTitle><AlertDialogDescription>В форме есть несохранённые данные. При выходе они будут потеряны.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter><AlertDialogCancel onClick={() => blocker.reset?.()}>Остаться</AlertDialogCancel><Button variant="outline" disabled={mutation.isPending} onClick={() => blocker.proceed?.()}>Выйти без сохранения</Button></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}

function FormSectionTitle({ number, title, description }: { number: string; title: string; description: string }) {
  return (
    <div className="flex items-start gap-3 border-b pb-5">
      <span className="grid size-8 shrink-0 place-items-center rounded-md bg-primary/8 text-xs font-semibold text-primary">{number}</span>
      <div>
        <h2 className="font-semibold">{title}</h2>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>
      </div>
    </div>
  )
}
