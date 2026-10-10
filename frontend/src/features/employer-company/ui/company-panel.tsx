import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useBlocker } from '@tanstack/react-router'
import { Building2, ChevronDown, Pencil } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { getCompany, saveCompany } from '@/features/employer-company/api/company'
import { companyIndustryOptions } from '@/features/employer-company/model/company-form'
import { CompanySize, Industry, type CompanyResponse } from '@/shared/api/generated/employers/models'
import { RequestError } from '@/shared/api/ui/request-error'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/shared/ui/alert-dialog'
import { Button } from '@/shared/ui/button'
import { FormField, formSelectClass } from '@/shared/ui/form-field'
import { Input } from '@/shared/ui/input'
import { Spinner } from '@/shared/ui/spinner'
import { Textarea } from '@/shared/ui/textarea'

const optionalText = (max: number) => z.string().trim().max(max, `Не более ${max} символов`)
const schema = z.object({
  name: z.string().trim().min(1, 'Укажите компанию').max(200), industry: z.enum(Industry),
  description: z.string().trim().min(1, 'Расскажите о компании').max(8000),
  city: optionalText(100), website: optionalText(300).refine((value) => !value || z.url({ protocol: /^https?$/ }).safeParse(value).success, 'Укажите адрес сайта с https:// или http://'),
  legal_name: optionalText(300), inn: z.string().trim().refine((value) => !value || /^(\d{10}|\d{12})$/.test(value), 'ИНН — 10 или 12 цифр'),
  size: z.union([z.enum(CompanySize), z.literal('')]),
  tech_stack: z.string().refine((value) => skills(value).length <= 50 && skills(value).every((skill) => skill.length <= 64), 'До 50 навыков, каждый до 64 символов'),
  contact_name: optionalText(200), contact_email: z.string().trim().refine((value) => !value || z.email().safeParse(value).success, 'Введите корректную почту'),
  contact_phone: optionalText(32), telegram: optionalText(64),
})
type Values = z.infer<typeof schema>
function skills(value: string) { return [...new Set(value.split(/[,;\n]/).map((item) => item.trim()).filter(Boolean))] }
function defaults(company?: CompanyResponse | null): Values {
  return { name: company?.name ?? '', industry: company?.industry ?? 'other', description: company?.description ?? '', city: company?.city ?? '', website: company?.website ?? '', legal_name: company?.legal_name ?? '', inn: company?.inn ?? '', size: company?.size ?? '', tech_stack: company?.tech_stack?.join(', ') ?? '', contact_name: company?.contact_name ?? '', contact_email: company?.contact_email ?? '', contact_phone: company?.contact_phone ?? '', telegram: company?.telegram ?? '' }
}

export function CompanyPanel() {
  const [open, setOpen] = useState(false)
  return <section className="rounded-xl border bg-card shadow-card"><button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="company-panel-content" className="flex w-full items-center gap-3 rounded-xl p-5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><Building2 className="size-5 text-primary" aria-hidden="true" /><span className="flex-1"><span className="block font-semibold">Профиль компании</span><span className="mt-1 block text-xs text-muted-foreground">Описание, реквизиты и контакты команды</span></span><ChevronDown className={`size-4 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden="true" /></button><div hidden={!open} id="company-panel-content" className="border-t p-5"><CompanyWorkspace onClose={() => setOpen(false)} /></div></section>
}

function CompanyWorkspace({ onClose }: { onClose: () => void }) {
  const query = useQuery({ queryKey: ['vacancy-company'], queryFn: ({ signal }) => getCompany(signal) })
  const [editing, setEditing] = useState(false)
  if (query.isPending) return <Spinner label="Загружаем компанию…" />
  if (query.isError) return <RequestError error={query.error} onRetry={() => { void query.refetch() }} />
  const company = query.data
  if (editing || !company) return <CompanyEditor company={company} onClose={company ? () => setEditing(false) : onClose} />
  return <div className="space-y-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-semibold">{company.name}</h2><p className="mt-1 text-sm text-muted-foreground">{companyIndustryOptions.find((item) => item.value === company.industry)?.label}{company.city ? ` · ${company.city}` : ''}</p></div><Button variant="outline" onClick={() => setEditing(true)}><Pencil size={16} aria-hidden="true" />Редактировать компанию</Button></div><p className="whitespace-pre-wrap break-words text-sm leading-6 text-muted-foreground">{company.description}</p><dl className="grid gap-4 text-sm sm:grid-cols-2">{[['Сайт', company.website], ['Юридическое название', company.legal_name], ['ИНН', company.inn], ['Размер команды', company.size], ['Стек', company.tech_stack?.join(', ')], ['Контактное лицо', company.contact_name], ['Почта', company.contact_email], ['Телефон', company.contact_phone], ['Telegram', company.telegram]].map(([label, value]) => <div key={label}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 break-words">{value || 'Не указано'}</dd></div>)}</dl></div>
}

function CompanyEditor({ company, onClose }: { company: CompanyResponse | null; onClose: () => void }) {
  const client = useQueryClient()
  const [discard, setDiscard] = useState(false)
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: defaults(company) })
  const dirty = form.formState.isDirty
  const mutation = useMutation({ mutationFn: (values: Values) => saveCompany({ ...values, legal_name: values.legal_name || null, inn: values.inn || null, city: values.city || null, website: values.website || null, size: values.size || null, tech_stack: skills(values.tech_stack), contact_name: values.contact_name || null, contact_email: values.contact_email || null, contact_phone: values.contact_phone || null, telegram: values.telegram || null }), onSuccess: (saved) => {
    form.reset(defaults(saved)); client.setQueryData(['vacancy-company'], saved)
    void client.invalidateQueries({ queryKey: ['vacancies'] }); void client.invalidateQueries({ queryKey: ['invitation-offer-options'] })
    onClose()
  } })
  const blocker = useBlocker({ shouldBlockFn: () => dirty || mutation.isPending, enableBeforeUnload: dirty || mutation.isPending, withResolver: true })
  const errors = form.formState.errors
  const textFields = [ ['city', 'Город'], ['website', 'Сайт'], ['legal_name', 'Юридическое название'], ['inn', 'ИНН'], ['contact_name', 'Контактное лицо'], ['contact_email', 'Почта для связи'], ['contact_phone', 'Телефон'], ['telegram', 'Telegram'] ] as const
  return <><form noValidate className="space-y-5" onSubmit={(event) => { void form.handleSubmit((values) => mutation.mutate(values))(event) }}><h2 className="text-xl font-semibold">{company ? 'Редактирование компании' : 'Ваша компания'}</h2><fieldset disabled={mutation.isPending} className="space-y-5">
    <div className="grid gap-4 sm:grid-cols-2"><FormField id="employer-company-name" label="Название компании" required error={errors.name?.message}>{(props) => <Input {...props} maxLength={200} {...form.register('name')} />}</FormField><FormField id="employer-company-industry" label="Отрасль" required error={errors.industry?.message}>{(props) => <select {...props} className={formSelectClass} {...form.register('industry')}>{companyIndustryOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>}</FormField></div>
    <FormField id="employer-company-about" label="О компании" required error={errors.description?.message}>{(props) => <Textarea {...props} rows={5} maxLength={8000} {...form.register('description')} />}</FormField>
    <div className="grid gap-4 sm:grid-cols-2">{textFields.map(([field, label]) => <FormField key={field} id={`employer-company-${field}`} label={label} error={errors[field]?.message}>{(props) => <Input {...props} type={field === 'contact_email' ? 'email' : field === 'contact_phone' ? 'tel' : 'text'} {...form.register(field)} />}</FormField>)}<FormField id="employer-company-size" label="Размер команды" error={errors.size?.message}>{(props) => <select {...props} className={formSelectClass} {...form.register('size')}><option value="">Не указан</option>{Object.values(CompanySize).map((value) => <option key={value} value={value}>{value.replaceAll('_', '–')} сотрудников</option>)}</select>}</FormField><FormField id="employer-company-stack" label="Технологический стек" hint="Через запятую, до 50 навыков" error={errors.tech_stack?.message}>{(props) => <Input {...props} {...form.register('tech_stack')} />}</FormField></div>
    {mutation.isError ? <RequestError error={mutation.error} /> : null}<div className="flex flex-wrap gap-2"><Button type="submit" disabled={Boolean(company && !dirty)}>{mutation.isPending ? <Spinner label="Сохраняем…" /> : null}Сохранить компанию</Button><Button type="button" variant="outline" onClick={() => dirty ? setDiscard(true) : onClose()}>Отмена</Button></div>
  </fieldset></form><AlertDialog open={discard || blocker.status === 'blocked'}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Оставить изменения компании?</AlertDialogTitle><AlertDialogDescription>Несохранённые данные будут потеряны.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel onClick={() => { setDiscard(false); blocker.reset?.() }}>Остаться</AlertDialogCancel><Button variant="outline" disabled={mutation.isPending} onClick={() => { if (discard) { form.reset(defaults(company)); setDiscard(false); onClose() } else blocker.proceed?.() }}>Выйти без сохранения</Button></AlertDialogFooter></AlertDialogContent></AlertDialog></>
}
