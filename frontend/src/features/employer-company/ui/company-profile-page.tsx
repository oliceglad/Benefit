import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useBlocker } from '@tanstack/react-router'
import { AlertCircle, ArrowLeft, CircleCheck, Mail, MapPin, Pencil, Phone, RotateCcw, Save, X } from 'lucide-react'
import { useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { Controller, useForm } from 'react-hook-form'

import { employerCompanyQueryKey, getEmployerCompany, saveEmployerCompany } from '@/features/employer-company/api/company'
import { companyDraft, useRegisterCompanyDraft } from '@/features/employer-company/model/company-draft'
import {
  companyIndustryLabels,
  companyProfileFormSchema,
  companyProfileFormValues,
  companyProfilePayload,
  companySizeLabels,
  splitTechStack,
  type CompanyProfileFormValues,
} from '@/features/employer-company/model/company-profile-form'
import { CompanyLogo, CompanyLogoManager } from '@/features/employer-company/ui/company-logo'
import { CompanyUnsavedDialog } from '@/features/employer-company/ui/company-unsaved-dialog'
import { CompanySize, Industry, type CompanyResponse } from '@/shared/api/generated/employers/models'
import { isApiError } from '@/shared/api/transport/api-error'
import { useSession } from '@/shared/session/session'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'
import { Spinner } from '@/shared/ui/spinner'
import { Textarea } from '@/shared/ui/textarea'

const sections = [
  { id: 'company-about', label: 'О компании' },
  { id: 'company-details', label: 'Реквизиты' },
  { id: 'company-location', label: 'Расположение и технологии' },
  { id: 'company-contacts', label: 'Контакты' },
] as const

export function CompanyProfilePage() {
  const accountId = useSession().user?.id
  const [editing, setEditing] = useState(false)
  const [savedMessage, setSavedMessage] = useState(false)
  const company = useQuery({
    queryKey: employerCompanyQueryKey(accountId ?? 'unknown'),
    queryFn: ({ signal }) => getEmployerCompany(signal),
    enabled: Boolean(accountId),
  })

  if (company.isPending) return <div className="grid min-h-80 place-items-center"><Spinner label="Загружаем компанию…" /></div>
  if (company.isError) {
    const forbidden = isApiError(company.error) && company.error.status === 403
    return (
      <Alert variant="destructive">
        <AlertCircle className="size-4" aria-hidden="true" />
        <AlertTitle>{forbidden ? 'Недостаточно прав' : 'Профиль компании не загрузился'}</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>{forbidden ? 'Этот раздел доступен только аккаунту работодателя.' : 'Проверьте подключение и повторите попытку.'}</p>
          {!forbidden ? <Button type="button" size="sm" variant="outline" onClick={() => { void company.refetch() }}><RotateCcw aria-hidden="true" />Повторить</Button> : null}
        </AlertDescription>
      </Alert>
    )
  }
  if (!accountId) return null

  if (company.data && !editing) {
    return <CompanyOverview company={company.data} savedMessage={savedMessage} onEdit={() => { setSavedMessage(false); setEditing(true) }} />
  }

  return (
    <CompanyProfileEditor
      key={company.data?.updated_at ?? 'new-company'}
      accountId={accountId}
      company={company.data}
      onCancel={() => setEditing(false)}
      onSaved={() => { setSavedMessage(true); setEditing(false) }}
    />
  )
}

function CompanyOverview({ company, savedMessage, onEdit }: { company: CompanyResponse; savedMessage: boolean; onEdit: () => void }) {
  const contacts = [company.contact_name, company.contact_email, company.contact_phone, company.telegram, company.website].filter(Boolean)
  return (
    <section className="mx-auto min-w-0 max-w-5xl space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Профиль компании</h1>
          <p className="mt-1 text-sm text-muted-foreground">Актуальные сведения о компании и рабочие контакты.</p>
        </div>
        <Button type="button" onClick={onEdit}><Pencil aria-hidden="true" />Редактировать</Button>
      </header>

      {savedMessage ? <div role="status" className="flex items-center gap-2 rounded-xl border border-success/30 bg-success/10 px-4 py-3 text-sm text-success-foreground"><CircleCheck className="size-4" aria-hidden="true" />Изменения сохранены</div> : null}

      <div className="overflow-hidden rounded-2xl border bg-card">
        <div className="flex min-w-0 flex-col gap-4 border-b p-5 sm:flex-row sm:items-center sm:p-6">
          <CompanyLogo company={company} />
          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <h2 className="min-w-0 break-words text-2xl font-semibold leading-tight">{company.name}</h2>
              {company.verification ? <Badge variant={company.verification.is_verified ? 'success' : 'secondary'}>{company.verification.title}</Badge> : null}
            </div>
            <p className="mt-2 text-sm text-muted-foreground">{companyIndustryLabels[company.industry]}</p>
            {(company.city || company.size) ? <p className="mt-2 flex flex-wrap items-center gap-x-2 text-sm text-muted-foreground"><MapPin className="size-4" aria-hidden="true" />{[company.city, company.size ? companySizeLabels[company.size] : null].filter(Boolean).join(' · ')}</p> : null}
          </div>
        </div>

        <OverviewSection title="О компании"><p className="whitespace-pre-wrap break-words text-sm leading-7 text-foreground/90">{company.description}</p></OverviewSection>
        <OverviewSection title="Технологии">{company.tech_stack?.length ? <div className="flex flex-wrap gap-2">{company.tech_stack.map((technology) => <Badge key={technology} variant="secondary">{technology}</Badge>)}</div> : <EmptyValue />}</OverviewSection>
        <OverviewSection title="Контакты">
          {contacts.length ? <dl className="grid min-w-0 gap-x-8 gap-y-4 sm:grid-cols-2">
            {company.contact_name ? <OverviewValue label="Контактное лицо" value={company.contact_name} /> : null}
            {company.contact_email ? <OverviewLink label="Рабочая почта" href={`mailto:${company.contact_email}`} icon={<Mail aria-hidden="true" />} value={company.contact_email} /> : null}
            {company.contact_phone ? <OverviewLink label="Телефон" href={`tel:${company.contact_phone}`} icon={<Phone aria-hidden="true" />} value={company.contact_phone} /> : null}
            {company.telegram ? <OverviewLink label="Telegram" href={`https://t.me/${company.telegram.replace(/^@/, '')}`} value={company.telegram} external /> : null}
            {company.website ? <OverviewLink label="Сайт" href={company.website} value={company.website} external /> : null}
          </dl> : <EmptyValue />}
        </OverviewSection>
        <OverviewSection title="Реквизиты" last>{(company.legal_name || company.inn) ? <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2"><OverviewValue label="Юридическое наименование" value={company.legal_name || 'Не указано'} /><OverviewValue label="ИНН" value={company.inn || 'Не указан'} /></dl> : <EmptyValue />}</OverviewSection>
      </div>
    </section>
  )
}

function CompanyProfileEditor({ accountId, company, onCancel, onSaved }: { accountId: string; company: CompanyResponse | null; onCancel: () => void; onSaved: () => void }) {
  const queryClient = useQueryClient()
  const submissionRef = useRef(false)
  const [savingForNavigation, setSavingForNavigation] = useState(false)
  const form = useForm<CompanyProfileFormValues>({ resolver: zodResolver(companyProfileFormSchema), defaultValues: companyProfileFormValues(company) })
  const blocker = useBlocker({ shouldBlockFn: () => form.formState.isDirty, enableBeforeUnload: () => form.formState.isDirty, withResolver: true })
  const mutation = useMutation({
    mutationFn: (values: CompanyProfileFormValues) => saveEmployerCompany(companyProfilePayload(values)),
    onSuccess: (saved) => {
      queryClient.setQueryData(employerCompanyQueryKey(accountId), saved)
      form.reset(companyProfileFormValues(saved))
      onSaved()
    },
    onError: (error) => {
      if (!isApiError(error)) return
      error.fieldIssues.forEach((issue) => {
        const field = Object.keys(companyProfileFormSchema.shape).find((name) => issue.field.split('.').includes(name))
        if (field) form.setError(field as keyof CompanyProfileFormValues, { type: 'server', message: issue.message })
      })
    },
  })

  async function save(): Promise<boolean> {
    if (submissionRef.current) return false
    let saved = false
    await form.handleSubmit(async (values) => {
      if (submissionRef.current) return
      submissionRef.current = true
      try { await mutation.mutateAsync(values); saved = true } catch { saved = false } finally { submissionRef.current = false }
    })()
    return saved
  }
  function discard(): void { form.reset(companyProfileFormValues(company)) }
  function cancelEditing(): void { discard(); if (company) onCancel() }
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
  function goToSection(id: string): void { document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }

  const errors = form.formState.errors
  const forbidden = isApiError(mutation.error) && mutation.error.status === 403
  const validationFailed = isApiError(mutation.error) && mutation.error.status === 422

  return (
    <section className="mx-auto min-w-0 max-w-5xl space-y-5">
      <header className="max-w-2xl">
        {company ? <Button type="button" size="sm" variant="ghost" className="mb-2 -ml-3" onClick={cancelEditing}><ArrowLeft aria-hidden="true" />К обзору</Button> : null}
        <h1 className="text-3xl font-semibold tracking-tight">{company ? 'Редактирование компании' : 'Создайте компанию'}</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">Заполните сведения, которые нужны для вакансий и общения с кандидатами.</p>
      </header>

      <div className="lg:grid lg:grid-cols-[200px_minmax(0,1fr)] lg:items-start lg:gap-6">
        <aside className="hidden lg:sticky lg:top-24 lg:block">
          <nav aria-label="Разделы формы" className="space-y-1 border-l pl-3">{sections.map((section) => <button key={section.id} type="button" className="flex min-h-10 w-full items-center rounded-lg px-3 text-left text-sm text-muted-foreground transition-colors hover:bg-card hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/35" onClick={() => goToSection(section.id)}>{section.label}</button>)}</nav>
        </aside>

        <div className="min-w-0 space-y-4">
          <div className="lg:hidden"><Select onValueChange={goToSection}><SelectTrigger aria-label="Перейти к разделу"><SelectValue placeholder="Раздел формы" /></SelectTrigger><SelectContent>{sections.map((section) => <SelectItem key={section.id} value={section.id}>{section.label}</SelectItem>)}</SelectContent></Select></div>

          <form noValidate className="min-w-0 space-y-4 scroll-pb-28" onSubmit={(event) => { event.preventDefault(); void save() }}>
            {form.formState.isDirty ? <div className="sticky top-20 z-20 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary/20 bg-card/95 px-4 py-3 shadow-sm backdrop-blur-sm"><p className="text-sm font-medium" role="status">{mutation.isPending ? 'Сохраняем изменения…' : 'Есть несохранённые изменения'}</p><div className="flex gap-2"><Button type="button" size="sm" variant="outline" disabled={mutation.isPending} onClick={cancelEditing}>Отменить</Button><Button type="submit" size="sm" disabled={mutation.isPending}>{mutation.isPending ? <Spinner label="Сохраняем…" /> : <Save aria-hidden="true" />}{company ? 'Сохранить' : 'Создать компанию'}</Button></div></div> : null}

            <fieldset disabled={mutation.isPending} className="min-w-0 overflow-hidden rounded-2xl border bg-card">
              <legend className="sr-only">Профиль компании</legend>
              <FormSection id="company-about" title="О компании" description="Название, направление и краткое описание бизнеса.">
                {company && typeof company.has_logo === 'boolean' ? <CompanyLogoManager company={company} accountId={accountId} /> : <p className="rounded-xl bg-muted px-4 py-3 text-sm text-muted-foreground">Здесь сохраняются сведения о компании и контакты для кандидатов.</p>}
                <CompanyField id="company-name" label="Название компании" required error={errors.name?.message} className="max-w-2xl">{(props) => <Input {...props} autoComplete="organization" maxLength={200} {...form.register('name')} />}</CompanyField>
                <CompanyField id="company-industry" label="Отрасль" required error={errors.industry?.message} className="max-w-md">{(props) => <Controller name="industry" control={form.control} render={({ field }) => <Select value={field.value} onValueChange={field.onChange} disabled={mutation.isPending}><SelectTrigger {...props} ref={field.ref} onBlur={field.onBlur}><SelectValue /></SelectTrigger><SelectContent>{Object.values(Industry).map((value) => <SelectItem key={value} value={value}>{companyIndustryLabels[value]}</SelectItem>)}</SelectContent></Select>} />}</CompanyField>
                <CompanyField id="company-description" label="Описание" required error={errors.description?.message} hint="До 8000 символов.">{(props) => <Textarea {...props} className="max-h-80 min-h-36 overflow-y-auto" maxLength={8000} {...form.register('description')} />}</CompanyField>
              </FormSection>

              <FormSection id="company-details" title="Реквизиты" description="Юридические данные компании.">
                <CompanyField id="company-legal-name" label="Юридическое наименование" error={errors.legal_name?.message} hint="После проверки название может быть уточнено по данным реестра." className="max-w-2xl">{(props) => <Input {...props} maxLength={300} {...form.register('legal_name')} />}</CompanyField>
                <CompanyField id="company-inn" label="ИНН" error={errors.inn?.message} className="max-w-60">{(props) => <Input {...props} inputMode="numeric" maxLength={12} {...form.register('inn')} />}</CompanyField>
              </FormSection>

              <FormSection id="company-location" title="Расположение и технологии" description="Где находится команда и с каким стеком работает.">
                <div className="grid gap-5 sm:grid-cols-2">
                  <CompanyField id="company-city" label="Город" error={errors.city?.message}>{(props) => <Input {...props} autoComplete="address-level2" maxLength={100} {...form.register('city')} />}</CompanyField>
                  <CompanyField id="company-size" label="Размер компании" error={errors.size?.message}>{(props) => <Controller name="size" control={form.control} render={({ field }) => <Select value={field.value || 'not-specified'} onValueChange={(value) => field.onChange(value === 'not-specified' ? '' : value)} disabled={mutation.isPending}><SelectTrigger {...props} ref={field.ref} onBlur={field.onBlur}><SelectValue /></SelectTrigger><SelectContent><SelectItem value="not-specified">Не указан</SelectItem>{Object.values(CompanySize).map((value) => <SelectItem key={value} value={value}>{companySizeLabels[value]}</SelectItem>)}</SelectContent></Select>} />}</CompanyField>
                </div>
                <Controller name="tech_stack" control={form.control} render={({ field }) => <TechnologyTags value={field.value} onChange={field.onChange} error={errors.tech_stack?.message} disabled={mutation.isPending} />} />
              </FormSection>

              <FormSection id="company-contacts" title="Контакты" description="Каналы связи для рабочих вопросов."><div className="grid gap-5 sm:grid-cols-2">
                <CompanyField id="company-website" label="Сайт" error={errors.website?.message}>{(props) => <Input {...props} type="url" inputMode="url" autoComplete="url" maxLength={300} placeholder="https://company.ru" {...form.register('website')} />}</CompanyField>
                <CompanyField id="company-contact-name" label="Контактное лицо" error={errors.contact_name?.message}>{(props) => <Input {...props} autoComplete="name" maxLength={200} {...form.register('contact_name')} />}</CompanyField>
                <CompanyField id="company-contact-email" label="Рабочая почта" error={errors.contact_email?.message}>{(props) => <Input {...props} type="email" inputMode="email" autoComplete="email" {...form.register('contact_email')} />}</CompanyField>
                <CompanyField id="company-contact-phone" label="Телефон" error={errors.contact_phone?.message}>{(props) => <Input {...props} type="tel" inputMode="tel" autoComplete="tel" maxLength={32} {...form.register('contact_phone')} />}</CompanyField>
                <CompanyField id="company-telegram" label="Telegram" error={errors.telegram?.message}>{(props) => <Input {...props} maxLength={64} placeholder="@company_hr" {...form.register('telegram')} />}</CompanyField>
              </div></FormSection>
            </fieldset>

            {mutation.isError ? <Alert variant="destructive"><AlertCircle className="size-4" aria-hidden="true" /><AlertTitle>{forbidden ? 'Недостаточно прав' : validationFailed ? 'Проверьте поля формы' : 'Компания не сохранена'}</AlertTitle><AlertDescription>{forbidden ? 'Сохранять компанию может только аккаунт работодателя.' : isApiError(mutation.error) ? mutation.error.message : 'Введённые данные остались в форме. Повторите попытку.'}</AlertDescription></Alert> : null}
            {!form.formState.isDirty && !company ? <div className="flex justify-end"><Button type="submit" disabled={mutation.isPending}>Создать компанию</Button></div> : null}
          </form>
        </div>
      </div>

      <CompanyUnsavedDialog open={blocker.status === 'blocked'} saving={savingForNavigation} onSave={() => { void saveAndProceed() }} onDiscard={discardAndProceed} onStay={() => { if (blocker.status === 'blocked') blocker.reset() }} />
    </section>
  )
}

function TechnologyTags({ value, onChange, error, disabled }: { value: string[]; onChange: (value: string[]) => void; error?: string; disabled: boolean }) {
  const [draft, setDraft] = useState('')
  function add(raw: string): void {
    const additions = splitTechStack(raw).filter((item) => !value.some((existing) => existing.toLocaleLowerCase('ru-RU') === item.toLocaleLowerCase('ru-RU')))
    if (additions.length) onChange([...value, ...additions].slice(0, 50))
    setDraft('')
  }
  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === 'Enter' || event.key === ',') { event.preventDefault(); add(draft) }
    if (event.key === 'Backspace' && !draft && value.length) onChange(value.slice(0, -1))
  }
  return <div className="space-y-2"><Label htmlFor="company-tech-stack">Технологии</Label><div className="flex min-h-11 flex-wrap items-center gap-2 rounded-xl border border-input bg-background px-2.5 py-2 focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/35" aria-invalid={Boolean(error)}>{value.map((technology) => <Badge key={technology} variant="secondary" className="gap-1 pr-1"><span>{technology}</span><button type="button" className="grid size-6 place-items-center rounded-full hover:bg-background focus-visible:ring-2 focus-visible:ring-ring" aria-label={`Удалить ${technology}`} disabled={disabled} onClick={() => onChange(value.filter((item) => item !== technology))}><X className="size-3.5" aria-hidden="true" /></button></Badge>)}<input id="company-tech-stack" className="h-7 min-w-32 flex-1 bg-transparent px-1 text-sm outline-none placeholder:text-muted-foreground" value={draft} disabled={disabled} maxLength={64} placeholder={value.length ? 'Добавить' : 'Например, TypeScript'} onChange={(event) => setDraft(event.target.value)} onKeyDown={handleKeyDown} onBlur={() => { if (draft.trim()) add(draft) }} onPaste={(event) => { const text = event.clipboardData.getData('text'); if (/[,\n]/.test(text)) { event.preventDefault(); add(text) } }} aria-describedby="company-tech-stack-help" aria-invalid={Boolean(error)} /></div><p id="company-tech-stack-help" role={error ? 'alert' : undefined} className={`text-xs leading-5 ${error ? 'text-destructive' : 'text-muted-foreground'}`}>{error || 'Введите значение и нажмите Enter. Можно вставить список через запятую.'}</p></div>
}

function FormSection({ id, title, description, children }: { id: string; title: string; description: string; children: ReactNode }) {
  return <section id={id} className="scroll-mt-28 space-y-5 border-b p-5 last:border-b-0 sm:p-6"><div><h2 className="text-lg font-semibold">{title}</h2><p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p></div>{children}</section>
}

function CompanyField({ id, label, error, hint, required = false, className, children }: { id: string; label: string; error?: string; hint?: string; required?: boolean; className?: string; children: (props: { id: string; 'aria-invalid': boolean; 'aria-describedby': string | undefined; 'aria-required': boolean }) => ReactNode }) {
  const helpId = error || hint ? `${id}-help` : undefined
  return <div className={`min-w-0 space-y-2 ${className ?? ''}`}><Label htmlFor={id}>{label}{required ? <span className="text-destructive" aria-hidden="true"> *</span> : null}</Label>{children({ id, 'aria-invalid': Boolean(error), 'aria-describedby': helpId, 'aria-required': required })}{helpId ? <p id={helpId} className={`text-xs leading-5 ${error ? 'text-destructive' : 'text-muted-foreground'}`} role={error ? 'alert' : undefined}>{error || hint}</p> : null}</div>
}

function OverviewSection({ title, children, last = false }: { title: string; children: ReactNode; last?: boolean }) {
  return <section className={`grid gap-4 p-5 sm:grid-cols-[180px_minmax(0,1fr)] sm:p-6 ${last ? '' : 'border-b'}`}><h3 className="text-base font-semibold">{title}</h3><div className="min-w-0">{children}</div></section>
}

function OverviewValue({ label, value }: { label: string; value: string }) {
  return <div className="min-w-0"><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 break-words text-sm">{value}</dd></div>
}

function OverviewLink({ label, value, href, icon, external = false }: { label: string; value: string; href: string; icon?: ReactNode; external?: boolean }) {
  return <div className="min-w-0"><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 min-w-0"><a href={href} target={external ? '_blank' : undefined} rel={external ? 'noreferrer' : undefined} className="inline-flex min-w-0 items-center gap-1.5 break-all text-sm font-medium text-primary underline-offset-4 hover:underline">{icon}{value}</a></dd></div>
}

function EmptyValue() { return <p className="text-sm text-muted-foreground">Не указано</p> }
