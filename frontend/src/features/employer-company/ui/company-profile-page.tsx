import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useBlocker } from '@tanstack/react-router'
import { AlertCircle, Building2, Check, RotateCcw, Save } from 'lucide-react'
import { useRef, useState, type ReactNode } from 'react'
import { useForm } from 'react-hook-form'

import {
  employerCompanyQueryKey,
  getEmployerCompany,
  saveEmployerCompany,
} from '@/features/employer-company/api/company'
import {
  companyDraft,
  useRegisterCompanyDraft,
} from '@/features/employer-company/model/company-draft'
import {
  companyIndustryLabels,
  companyProfileFormSchema,
  companyProfileFormValues,
  companyProfilePayload,
  companySizeLabels,
  type CompanyProfileFormValues,
} from '@/features/employer-company/model/company-profile-form'
import { CompanyUnsavedDialog } from '@/features/employer-company/ui/company-unsaved-dialog'
import { CompanySize, Industry, type CompanyResponse } from '@/shared/api/generated/employers/models'
import { isApiError } from '@/shared/api/transport/api-error'
import { useSession } from '@/shared/session/session'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Spinner } from '@/shared/ui/spinner'
import { Textarea } from '@/shared/ui/textarea'

const selectClassName = 'min-h-12 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/35 aria-invalid:border-destructive'

export function CompanyProfilePage() {
  const accountId = useSession().user?.id
  const company = useQuery({
    queryKey: employerCompanyQueryKey(accountId ?? 'unknown'),
    queryFn: ({ signal }) => getEmployerCompany(signal),
    enabled: Boolean(accountId),
  })

  if (company.isPending) {
    return <div className="grid min-h-80 place-items-center"><Spinner label="Загружаем компанию…" /></div>
  }

  if (company.isError) {
    const forbidden = isApiError(company.error) && company.error.status === 403
    return (
      <Alert variant="destructive">
        <AlertCircle className="size-4" aria-hidden="true" />
        <AlertTitle>{forbidden ? 'Недостаточно прав' : 'Профиль компании не загрузился'}</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>{forbidden
            ? 'Этот раздел доступен только аккаунту работодателя.'
            : isApiError(company.error) ? company.error.message : 'Проверьте подключение и повторите попытку.'}</p>
          {!forbidden ? (
            <Button type="button" size="sm" variant="outline" onClick={() => { void company.refetch() }}>
              <RotateCcw aria-hidden="true" />Повторить
            </Button>
          ) : null}
        </AlertDescription>
      </Alert>
    )
  }

  if (!accountId) return null

  return (
    <CompanyProfileEditor
      key={company.data?.updated_at ?? 'new-company'}
      accountId={accountId}
      company={company.data}
    />
  )
}

function CompanyProfileEditor({
  accountId,
  company,
}: {
  accountId: string
  company: CompanyResponse | null
}) {
  const queryClient = useQueryClient()
  const submissionRef = useRef(false)
  const [savingForNavigation, setSavingForNavigation] = useState(false)
  const form = useForm<CompanyProfileFormValues>({
    resolver: zodResolver(companyProfileFormSchema),
    defaultValues: companyProfileFormValues(company),
  })
  const blocker = useBlocker({
    shouldBlockFn: () => form.formState.isDirty,
    enableBeforeUnload: () => form.formState.isDirty,
    withResolver: true,
  })
  const mutation = useMutation({
    mutationFn: (values: CompanyProfileFormValues) =>
      saveEmployerCompany(companyProfilePayload(values)),
    onSuccess: (saved) => {
      queryClient.setQueryData(employerCompanyQueryKey(accountId), saved)
      form.reset(companyProfileFormValues(saved))
    },
    onError: (error) => {
      if (!isApiError(error)) return
      error.fieldIssues.forEach((issue) => {
        const field = Object.keys(companyProfileFormSchema.shape).find((name) =>
          issue.field.split('.').includes(name),
        )
        if (field) {
          form.setError(field as keyof CompanyProfileFormValues, {
            type: 'server',
            message: issue.message,
          })
        }
      })
    },
  })

  async function save(): Promise<boolean> {
    if (submissionRef.current) return false
    let saved = false
    await form.handleSubmit(async (values) => {
      if (submissionRef.current) return
      submissionRef.current = true
      try {
        await mutation.mutateAsync(values)
        saved = true
      } catch {
        saved = false
      } finally {
        submissionRef.current = false
      }
    })()
    return saved
  }

  function discard(): void {
    form.reset(companyProfileFormValues(company))
  }

  useRegisterCompanyDraft(form.formState.isDirty, save, discard)

  async function saveAndProceed(): Promise<void> {
    setSavingForNavigation(true)
    const saved = await save()
    setSavingForNavigation(false)
    if (saved && blocker.status === 'blocked') blocker.proceed()
  }

  function discardAndProceed(): void {
    discard()
    companyDraft.setDirty(false)
    if (blocker.status === 'blocked') blocker.proceed()
  }

  const errors = form.formState.errors
  const forbidden = isApiError(mutation.error) && mutation.error.status === 403
  const validationFailed = isApiError(mutation.error) && mutation.error.status === 422

  return (
    <section className="min-w-0 space-y-6">
      <header className="max-w-3xl space-y-2">
        <p className="text-sm font-medium text-primary">Профиль работодателя</p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          {company ? 'Компания' : 'Создайте компанию'}
        </h1>
        <p className="text-sm leading-6 text-muted-foreground">
          Эти сведения используются в ваших вакансиях. Контакты компании и представителя хранятся отдельно от аккаунта пользователя.
        </p>
      </header>

      {!company ? (
        <Alert>
          <Building2 className="size-4" aria-hidden="true" />
          <AlertTitle>Профиль компании ещё не заполнен</AlertTitle>
          <AlertDescription>Заполните обязательные поля, чтобы создать компанию и продолжить работу с вакансиями.</AlertDescription>
        </Alert>
      ) : null}

      <form
        noValidate
        className="space-y-6"
        onSubmit={(event) => { event.preventDefault(); void save() }}
      >
        <fieldset disabled={mutation.isPending} className="grid min-w-0 gap-6 border-0 p-0 lg:grid-cols-2 lg:items-start">
          <legend className="sr-only">Профиль компании</legend>

          <div className="min-w-0 space-y-6">
            <FormSection number="01" title="О компании" description="Основные сведения, которые помогают кандидату понять ваш бизнес.">
              <CompanyField id="company-name" label="Название компании" required error={errors.name?.message}>
                {(props) => <Input {...props} autoComplete="organization" maxLength={200} {...form.register('name')} />}
              </CompanyField>
              <CompanyField id="company-legal-name" label="Юридическое наименование" error={errors.legal_name?.message} hint="После проверки компании сервер может уточнить это поле по данным реестра.">
                {(props) => <Input {...props} maxLength={300} {...form.register('legal_name')} />}
              </CompanyField>
              <div className="grid gap-5 sm:grid-cols-2">
                <CompanyField id="company-inn" label="ИНН" error={errors.inn?.message}>
                  {(props) => <Input {...props} inputMode="numeric" maxLength={12} {...form.register('inn')} />}
                </CompanyField>
                <CompanyField id="company-industry" label="Отрасль" required error={errors.industry?.message}>
                  {(props) => (
                    <select {...props} className={selectClassName} {...form.register('industry')}>
                      {Object.values(Industry).map((value) => <option key={value} value={value}>{companyIndustryLabels[value]}</option>)}
                    </select>
                  )}
                </CompanyField>
              </div>
              <CompanyField id="company-description" label="Описание" required error={errors.description?.message} hint="До 8000 символов.">
                {(props) => <Textarea {...props} className="min-h-44" maxLength={8000} {...form.register('description')} />}
              </CompanyField>
            </FormSection>

            <FormSection number="02" title="Расположение и команда" description="Размер, город и технологии компании.">
              <div className="grid gap-5 sm:grid-cols-2">
                <CompanyField id="company-city" label="Город" error={errors.city?.message}>
                  {(props) => <Input {...props} autoComplete="address-level2" maxLength={100} {...form.register('city')} />}
                </CompanyField>
                <CompanyField id="company-size" label="Размер компании" error={errors.size?.message}>
                  {(props) => (
                    <select {...props} className={selectClassName} {...form.register('size')}>
                      <option value="">Не указан</option>
                      {Object.values(CompanySize).map((value) => <option key={value} value={value}>{companySizeLabels[value]}</option>)}
                    </select>
                  )}
                </CompanyField>
              </div>
              <CompanyField id="company-tech-stack" label="Технологии" error={errors.tech_stack?.message} hint="Через запятую или с новой строки. До 50 значений.">
                {(props) => <Textarea {...props} rows={3} placeholder="TypeScript, Python, PostgreSQL" {...form.register('tech_stack')} />}
              </CompanyField>
            </FormSection>
          </div>

          <div className="min-w-0 space-y-6 lg:sticky lg:top-6">
            <FormSection number="03" title="Сайт и контакты" description="Каналы связи для рабочих вопросов.">
              <CompanyField id="company-website" label="Сайт" error={errors.website?.message}>
                {(props) => <Input {...props} type="url" inputMode="url" autoComplete="url" maxLength={300} placeholder="https://company.ru" {...form.register('website')} />}
              </CompanyField>
              <CompanyField id="company-contact-name" label="Контактное лицо" error={errors.contact_name?.message}>
                {(props) => <Input {...props} autoComplete="name" maxLength={200} {...form.register('contact_name')} />}
              </CompanyField>
              <CompanyField id="company-contact-email" label="Рабочая почта" error={errors.contact_email?.message}>
                {(props) => <Input {...props} type="email" inputMode="email" autoComplete="email" {...form.register('contact_email')} />}
              </CompanyField>
              <CompanyField id="company-contact-phone" label="Телефон" error={errors.contact_phone?.message}>
                {(props) => <Input {...props} type="tel" inputMode="tel" autoComplete="tel" maxLength={32} {...form.register('contact_phone')} />}
              </CompanyField>
              <CompanyField id="company-telegram" label="Telegram" error={errors.telegram?.message}>
                {(props) => <Input {...props} maxLength={64} placeholder="@company_hr" {...form.register('telegram')} />}
              </CompanyField>
            </FormSection>

            <div className="rounded-xl border bg-card p-5 text-sm leading-6 shadow-card">
              <p className="flex items-center gap-2 font-semibold"><Check className="size-4 text-primary" aria-hidden="true" />Что сохранится</p>
              <p className="mt-2 text-muted-foreground">Форма отправляет полный профиль компании. Пустые необязательные поля сохраняются как пустые значения.</p>
              <p className="mt-2 text-muted-foreground">Логотип, сотрудники и статус проверки здесь не показываются: для них нет согласованного frontend-контракта.</p>
            </div>
          </div>
        </fieldset>

        {mutation.isError ? (
          <Alert variant="destructive">
            <AlertCircle className="size-4" aria-hidden="true" />
            <AlertTitle>{forbidden ? 'Недостаточно прав' : validationFailed ? 'Проверьте поля формы' : 'Компания не сохранена'}</AlertTitle>
            <AlertDescription>{forbidden
              ? 'Сохранять компанию может только аккаунт работодателя.'
              : isApiError(mutation.error) ? mutation.error.message : 'Введённые данные сохранены в форме. Повторите попытку.'}</AlertDescription>
          </Alert>
        ) : null}

        <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card/95 p-4 shadow-card backdrop-blur-sm">
          <p className="text-sm text-muted-foreground" role="status">
            {mutation.isPending ? 'Сохраняем компанию…' : form.formState.isDirty ? 'Есть несохранённые изменения' : company ? 'Все изменения сохранены' : 'Заполните обязательные поля'}
          </p>
          <Button type="submit" disabled={mutation.isPending || Boolean(company && !form.formState.isDirty)}>
            {mutation.isPending ? <Spinner label="Сохраняем…" /> : <Save aria-hidden="true" />}
            {company ? 'Сохранить изменения' : 'Создать компанию'}
          </Button>
        </div>
      </form>

      <CompanyUnsavedDialog
        open={blocker.status === 'blocked'}
        saving={savingForNavigation}
        onSave={() => { void saveAndProceed() }}
        onDiscard={discardAndProceed}
        onStay={() => { if (blocker.status === 'blocked') blocker.reset() }}
      />
    </section>
  )
}

function FormSection({
  number,
  title,
  description,
  children,
}: {
  number: string
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <section className="space-y-5 rounded-xl border bg-card p-5 shadow-card sm:p-6">
      <div className="flex items-start gap-3 border-b pb-5">
        <span className="grid size-8 shrink-0 place-items-center rounded-md bg-primary/8 text-xs font-semibold text-primary" aria-hidden="true">{number}</span>
        <div className="min-w-0">
          <h2 className="font-semibold">{title}</h2>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>
        </div>
      </div>
      {children}
    </section>
  )
}

function CompanyField({
  id,
  label,
  error,
  hint,
  required = false,
  children,
}: {
  id: string
  label: string
  error?: string
  hint?: string
  required?: boolean
  children: (props: {
    id: string
    'aria-invalid': boolean
    'aria-describedby': string | undefined
    'aria-required': boolean
  }) => ReactNode
}) {
  const helpId = error || hint ? `${id}-help` : undefined
  return (
    <div className="min-w-0 space-y-2">
      <Label htmlFor={id}>{label}{required ? <span className="text-destructive" aria-hidden="true"> *</span> : null}</Label>
      {children({
        id,
        'aria-invalid': Boolean(error),
        'aria-describedby': helpId,
        'aria-required': required,
      })}
      {helpId ? <p id={helpId} className={`text-xs leading-5 ${error ? 'text-destructive' : 'text-muted-foreground'}`} role={error ? 'alert' : undefined}>{error || hint}</p> : null}
    </div>
  )
}
