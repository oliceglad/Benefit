import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useBlocker } from '@tanstack/react-router'
import { Building2 } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { createVacancyCompany } from '@/features/vacancies/api/vacancy-company'
import { VacancyFormField, vacancySelectClass } from '@/features/vacancies/ui/vacancy-form-field'
import { Industry } from '@/shared/api/generated/employers/models'
import { RequestError } from '@/shared/api/ui/request-error'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/shared/ui/alert-dialog'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Spinner } from '@/shared/ui/spinner'
import { Textarea } from '@/shared/ui/textarea'

const companySchema = z.object({
  name: z.string().trim().min(1, 'Укажите название компании').max(200, 'Не более 200 символов'),
  industry: z.enum(Industry),
  description: z.string().trim().min(1, 'Расскажите о компании').max(8000, 'Не более 8000 символов'),
})
const industries: Record<Industry, string> = {
  fintech: 'Финансовые технологии', ecommerce: 'Электронная коммерция', govtech: 'Государственные технологии',
  telecom: 'Телекоммуникации', healthtech: 'Медицина и здоровье', edtech: 'Образование', gamedev: 'Разработка игр',
  media: 'Медиа', logistics: 'Логистика', industry: 'Промышленность', energy: 'Энергетика',
  cybersecurity: 'Кибербезопасность', ai: 'Искусственный интеллект', travel: 'Путешествия',
  real_estate: 'Недвижимость', outsource: 'Аутсорсинг', other: 'Другая отрасль',
}

export function VacancyCompanySetup() {
  const client = useQueryClient()
  const form = useForm<z.infer<typeof companySchema>>({ resolver: zodResolver(companySchema), defaultValues: { name: '', industry: 'other', description: '' } })
  const blocker = useBlocker({ shouldBlockFn: () => form.formState.isDirty, enableBeforeUnload: () => form.formState.isDirty, withResolver: true })
  const mutation = useMutation({
    mutationFn: createVacancyCompany,
    onSuccess: (company) => { form.reset(); client.setQueryData(['vacancy-company'], company) },
  })
  return (
    <section className="mx-auto max-w-2xl space-y-6">
      <Button asChild variant="ghost"><Link to="/vacancies" search={{ offset: 0 }}>К вакансиям</Link></Button>
      <div className="space-y-3"><Building2 className="size-7 text-primary" aria-hidden="true" /><h1 className="text-3xl font-semibold">Сначала — ваша компания</h1><p className="text-sm leading-6 text-muted-foreground">Чтобы создать первую вакансию, добавьте компанию. Эти сведения будут связаны с вакансиями вашего аккаунта.</p></div>
      <form noValidate onSubmit={(event) => { void form.handleSubmit((values) => mutation.mutate(values))(event) }} className="space-y-5 rounded-xl border bg-card p-6 shadow-card">
        <fieldset disabled={mutation.isPending} className="space-y-5">
          <legend className="sr-only">Данные компании</legend>
          <VacancyFormField id="company-name" label="Название компании" required error={form.formState.errors.name?.message}>{(props) => <Input {...props} maxLength={200} {...form.register('name')} />}</VacancyFormField>
          <VacancyFormField id="company-industry" label="Отрасль" required error={form.formState.errors.industry?.message}>{(props) => <select {...props} className={vacancySelectClass} {...form.register('industry')}>{Object.entries(industries).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>}</VacancyFormField>
          <VacancyFormField id="company-description" label="О компании" required error={form.formState.errors.description?.message}>{(props) => <Textarea {...props} rows={5} maxLength={8000} {...form.register('description')} />}</VacancyFormField>
        </fieldset>
        {mutation.isError ? <RequestError error={mutation.error} /> : null}
        <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? <Spinner label="Сохраняем компанию…" /> : 'Сохранить и создать вакансию'}</Button>
      </form>
      <AlertDialog open={blocker.status === 'blocked'}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Выйти без сохранения?</AlertDialogTitle>
            <AlertDialogDescription>Введённые сведения о компании не будут сохранены.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => blocker.reset?.()}>Остаться</AlertDialogCancel>
            <Button variant="outline" onClick={() => blocker.proceed?.()}>Выйти</Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
