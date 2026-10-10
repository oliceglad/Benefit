import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useBlocker } from '@tanstack/react-router'
import { Send } from 'lucide-react'
import { useId, useState } from 'react'
import { useForm } from 'react-hook-form'

import { getOfferOptions, invitationKey, sendInvitation } from '@/features/invitations/api/invitations'
import { invitationFormSchema, invitationPayload, type InvitationFormValues, type OfferDefaults } from '@/features/invitations/model/invitation-form'
import { RequestError } from '@/shared/api/ui/request-error'
import { useSession } from '@/shared/session/session'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/shared/ui/alert-dialog'
import { Button } from '@/shared/ui/button'
import { FormField, formSelectClass } from '@/shared/ui/form-field'
import { Input } from '@/shared/ui/input'
import { Spinner } from '@/shared/ui/spinner'
import { Textarea } from '@/shared/ui/textarea'

export function InvitationAction({ candidateId, name, defaults }: { candidateId: string; name: string; defaults?: OfferDefaults }) {
  const [open, setOpen] = useState(false)
  if (open) return <InvitationEditor candidateId={candidateId} name={name} defaults={defaults} onClose={() => setOpen(false)} />
  return <Button onClick={() => setOpen(true)}><Send size={16} aria-hidden="true" />Пригласить кандидата</Button>
}

function InvitationEditor({ candidateId, name, defaults, onClose }: { candidateId: string; name: string; defaults?: OfferDefaults; onClose: () => void }) {
  const userId = useSession().user?.id
  const options = useQuery({ queryKey: ['invitation-offer-options', userId], queryFn: ({ signal }) => getOfferOptions(signal) })
  if (options.isPending) return <Spinner label="Готовим предложение…" />
  if (options.isError) return <div className="space-y-3"><RequestError error={options.error} onRetry={() => { void options.refetch() }} /><Button variant="outline" onClick={onClose}>Отмена</Button></div>
  return <InvitationForm candidateId={candidateId} name={name} defaults={defaults} options={options.data} onClose={onClose} />
}

function InvitationForm({ candidateId, name, defaults, options, onClose }: {
  candidateId: string; name: string; defaults?: OfferDefaults; options: Awaited<ReturnType<typeof getOfferOptions>>; onClose: () => void
}) {
  const id = useId()
  const userId = useSession().user?.id
  const client = useQueryClient()
  const [discard, setDiscard] = useState(false)
  const form = useForm<InvitationFormValues>({ resolver: zodResolver(invitationFormSchema), defaultValues: {
    vacancyId: '', title: '', companyName: options.company?.name ?? '', salaryFrom: '', salaryTo: '', workFormat: '', city: '', message: '', ...defaults,
  } })
  const dirty = form.formState.isDirty
  const mutation = useMutation({
    mutationFn: (values: InvitationFormValues) => sendInvitation(invitationPayload(candidateId, values)),
    onSuccess: () => {
      form.reset(form.getValues())
      void client.invalidateQueries({ queryKey: invitationKey(userId) })
      void client.invalidateQueries({ queryKey: ['talent-matches', userId] })
      void client.invalidateQueries({ queryKey: ['chat', userId] })
    },
  })
  const blocker = useBlocker({ shouldBlockFn: () => mutation.isPending || dirty && !mutation.isSuccess, enableBeforeUnload: mutation.isPending || dirty && !mutation.isSuccess, withResolver: true })
  const errors = form.formState.errors

  if (mutation.isSuccess) return <div role="status" className="space-y-3 rounded-lg border border-primary/20 bg-primary/5 p-5"><h3 className="font-semibold">Приглашение отправлено</h3><p className="text-sm text-muted-foreground">{name} увидит условия и сможет принять или отклонить предложение.</p><div className="flex flex-wrap gap-2"><Button asChild><Link to="/messages" search={{ section: 'invitations', invitation: mutation.data.id }}>Посмотреть приглашение</Link></Button><Button variant="outline" onClick={onClose}>Готово</Button></div></div>

  function chooseVacancy(value: string) {
    form.setValue('vacancyId', value, { shouldDirty: true })
    const vacancy = options.vacancies.find((item) => item.id === value)
    if (!vacancy) return
    form.setValue('title', vacancy.title, { shouldDirty: true })
    form.setValue('companyName', vacancy.company.name, { shouldDirty: true })
    form.setValue('salaryFrom', vacancy.currency === 'RUB' ? vacancy.salary_from?.toString() ?? '' : '', { shouldDirty: true })
    form.setValue('salaryTo', vacancy.currency === 'RUB' ? vacancy.salary_to?.toString() ?? '' : '', { shouldDirty: true })
    form.setValue('workFormat', vacancy.work_format ?? '', { shouldDirty: true })
    form.setValue('city', vacancy.city ?? '', { shouldDirty: true })
  }

  return <div className="space-y-4 rounded-xl border bg-card p-5">
    <div className="space-y-1"><h3 className="font-semibold">Предложение для {name}</h3><p className="text-sm leading-6 text-muted-foreground">Условия доступны до начала общения. Контакты откроются после принятия приглашения.</p></div>
    <form noValidate className="space-y-4" onSubmit={(event) => { void form.handleSubmit((values) => mutation.mutate(values))(event) }}>
      <fieldset disabled={mutation.isPending} className="space-y-4">
        <FormField id={`${id}-vacancy`} label="Связать с вакансией" hint="Необязательно. Можно отправить персональное предложение.">{(props) => <select {...props} className={formSelectClass} {...form.register('vacancyId')} onChange={(event) => chooseVacancy(event.target.value)}><option value="">Персональное предложение</option>{options.vacancies.map((vacancy) => <option key={vacancy.id} value={vacancy.id}>{vacancy.title}{vacancy.status === 'draft' ? ' · черновик' : ''}</option>)}</select>}</FormField>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField id={`${id}-title`} label="Должность" required error={errors.title?.message}>{(props) => <Input {...props} maxLength={200} {...form.register('title')} />}</FormField>
          <FormField id={`${id}-company`} label="Компания" required error={errors.companyName?.message}>{(props) => <Input {...props} maxLength={200} {...form.register('companyName')} />}</FormField>
          <FormField id={`${id}-from`} label="Зарплата от, ₽" required error={errors.salaryFrom?.message}>{(props) => <Input {...props} inputMode="numeric" {...form.register('salaryFrom')} />}</FormField>
          <FormField id={`${id}-to`} label="Зарплата до, ₽" required error={errors.salaryTo?.message}>{(props) => <Input {...props} inputMode="numeric" {...form.register('salaryTo')} />}</FormField>
          <FormField id={`${id}-format`} label="Формат работы" error={errors.workFormat?.message}>{(props) => <select {...props} className={formSelectClass} {...form.register('workFormat')}><option value="">Не указан</option><option value="remote">Удалённо</option><option value="office">В офисе</option><option value="hybrid">Гибрид</option></select>}</FormField>
          <FormField id={`${id}-city`} label="Город" error={errors.city?.message}>{(props) => <Input {...props} maxLength={100} {...form.register('city')} />}</FormField>
        </div>
        <p className="text-xs text-muted-foreground">Ежемесячная вилка в рублях. Обе границы обязательны.</p>
        <FormField id={`${id}-message`} label="Почему вы приглашаете кандидата" error={errors.message?.message} hint="До 2000 символов. Необязательно.">{(props) => <Textarea {...props} rows={3} maxLength={2000} placeholder="Какие навыки и достижения пригодятся команде?" {...form.register('message')} />}</FormField>
        {mutation.isError ? <RequestError error={mutation.error} /> : null}
        <div className="flex flex-wrap gap-2"><Button type="submit">{mutation.isPending ? <Spinner label="Отправляем…" /> : <Send size={16} aria-hidden="true" />}Отправить приглашение</Button><Button type="button" variant="outline" onClick={() => dirty ? setDiscard(true) : onClose()}>Отмена</Button></div>
      </fieldset>
    </form>
    <AlertDialog open={discard || blocker.status === 'blocked'}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Оставить предложение?</AlertDialogTitle><AlertDialogDescription>{mutation.isPending ? 'Приглашение отправляется. Дождитесь ответа сервера.' : 'Несохранённые условия будут потеряны.'}</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel onClick={() => { setDiscard(false); blocker.reset?.() }}>Остаться</AlertDialogCancel><Button variant="outline" disabled={mutation.isPending} onClick={() => { if (discard) onClose(); else blocker.proceed?.() }}>Выйти</Button></AlertDialogFooter></AlertDialogContent></AlertDialog>
  </div>
}
