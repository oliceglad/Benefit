import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import { ArrowRight, Check, Inbox, LockKeyhole, RefreshCw, X } from 'lucide-react'
import { useState } from 'react'

import { candidateContacts, invitationConversation, invitationKey, listInvitations, respondToInvitation } from '@/features/invitations/api/invitations'
import { invitationStatusLabels } from '@/features/invitations/model/invitation-form'
import { messagesSearchSchema } from '@/features/invitations/model/messages-search'
import type { InvitationResponse, InvitationStatus } from '@/shared/api/generated/applications/models'
import { RequestError } from '@/shared/api/ui/request-error'
import { useSession } from '@/shared/session/session'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/shared/ui/alert-dialog'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Label } from '@/shared/ui/label'
import { Spinner } from '@/shared/ui/spinner'

const money = new Intl.NumberFormat('ru-RU')
const date = (value: string) => new Date(value).toLocaleDateString('ru-RU')
const formatLabels: Record<string, string> = { remote: 'Удалённо', office: 'В офисе', hybrid: 'Гибрид' }

export function InvitationInbox() {
  const user = useSession().user
  const employer = user?.role === 'employer'
  const search = messagesSearchSchema.parse(useSearch({ strict: false }))
  const navigate = useNavigate()
  const [filter, setFilter] = useState<InvitationStatus | ''>('')
  const query = useQuery({ queryKey: invitationKey(user?.id), queryFn: ({ signal }) => listInvitations(employer, signal), enabled: Boolean(user), refetchInterval: 15_000 })
  const all = query.data ?? []
  const items = all.filter((item) => !filter || item.status === filter).sort((a, b) => b.created_at.localeCompare(a.created_at))
  const selected = all.find((item) => item.id === search.invitation)
  return <section aria-label={employer ? 'Отправленные приглашения' : 'Входящие приглашения'} className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold">{employer ? 'Ваши предложения кандидатам' : 'Предложения от работодателей'}</h2><p className="mt-1 text-sm text-muted-foreground">{employer ? 'Ответы на приглашения и открытые контакты.' : 'Посмотрите условия до решения. Вы сами выбираете, кому открыть контакты.'}</p></div><div className="flex items-center gap-2"><Label className="sr-only" htmlFor="invitation-status">Статус приглашения</Label><select id="invitation-status" value={filter} onChange={(event) => setFilter(event.target.value as InvitationStatus | '')} className="h-10 rounded-lg border bg-card px-3 text-sm"><option value="">Все статусы</option>{Object.entries(invitationStatusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><Button variant="outline" size="icon" aria-label="Обновить приглашения" disabled={query.isFetching} onClick={() => { void query.refetch() }}><RefreshCw size={16} aria-hidden="true" /></Button></div></div>
    {query.isPending ? <Spinner label="Загружаем приглашения…" /> : null}
    {query.isError ? <RequestError error={query.error} onRetry={() => { void query.refetch() }} /> : null}
    {query.isSuccess ? <div className="grid items-start gap-5 md:grid-cols-[280px_minmax(0,1fr)] lg:grid-cols-[320px_minmax(0,1fr)]">
      <div className="space-y-3">{items.map((item) => <button key={item.id} type="button" onClick={() => { void navigate({ to: '/messages', search: { section: 'invitations', invitation: item.id }, resetScroll: false }) }} aria-pressed={selected?.id === item.id} className={`w-full space-y-3 rounded-xl border bg-card p-4 text-left transition-colors hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${selected?.id === item.id ? 'border-primary/40 bg-primary/5' : ''}`}><div className="flex items-start justify-between gap-3"><span className="break-words text-sm font-semibold">{item.vacancy.title}</span><ArrowRight size={16} className="shrink-0 text-primary" aria-hidden="true" /></div><p className="text-sm text-muted-foreground">{item.vacancy.company_name}</p><div className="flex flex-wrap items-center justify-between gap-2"><Badge variant="secondary">{invitationStatusLabels[item.status]}</Badge><time className="text-xs text-muted-foreground" dateTime={item.created_at}>{date(item.created_at)}</time></div></button>)}{!items.length ? <div className="space-y-3 rounded-xl border border-dashed bg-card p-6"><Inbox className="size-6 text-primary" aria-hidden="true" /><p className="font-medium">{all.length ? 'Нет приглашений с этим статусом' : 'Приглашений пока нет'}</p><p className="text-sm leading-6 text-muted-foreground">{employer ? 'Откройте карточку кандидата в банке или подборке и отправьте предложение с условиями.' : 'Работодатели смогут пригласить вас после публикации профиля.'}</p>{employer ? <Button asChild variant="outline"><Link to="/talent" search={{ skills_mode: 'all', active_only: false, include_not_looking: false, sort: 'relevance', offset: 0, hide_contacted: false }}>В банк кандидатов</Link></Button> : null}</div> : null}</div>
      {selected ? <InvitationDetail key={selected.id} invitation={selected} employer={employer} userId={user!.id} /> : <div className="grid min-h-64 place-items-center rounded-xl border bg-card p-8 text-center text-sm text-muted-foreground">{search.invitation ? 'Приглашение недоступно. Оно могло быть удалено или относиться к другому аккаунту.' : 'Выберите приглашение, чтобы посмотреть условия и ответ.'}</div>}
    </div> : null}
  </section>
}

function InvitationDetail({ invitation, employer, userId }: { invitation: InvitationResponse; employer: boolean; userId: string }) {
  const offer = invitation.vacancy
  const candidate = useQuery({ queryKey: ['invitation-contacts', userId, invitation.candidate_id], queryFn: ({ signal }) => candidateContacts(invitation.candidate_id, signal), enabled: employer })
  const candidateName = candidate.data ? [candidate.data.last_name, candidate.data.first_name, candidate.data.middle_name].filter(Boolean).join(' ') : ''
  return <article className="space-y-6 rounded-xl border bg-card p-6 shadow-card">
    <header className="space-y-3"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="mb-2 text-sm text-primary">{offer.company_name}</p><h3 className="break-words text-2xl font-semibold tracking-tight">{offer.title}</h3></div><Badge variant="secondary">{invitationStatusLabels[invitation.status]}</Badge></div><p className="text-xl font-semibold">{offer.salary_from != null && offer.salary_to != null ? `${money.format(offer.salary_from)} – ${money.format(offer.salary_to)}` : offer.salary_from != null ? `от ${money.format(offer.salary_from)}` : offer.salary_to != null ? `до ${money.format(offer.salary_to)}` : 'Зарплата не указана'}{offer.salary_from != null || offer.salary_to != null ? ` ${offer.currency === 'RUB' ? '₽' : offer.currency ?? ''}` : ''}</p><div className="flex flex-wrap gap-2">{offer.work_format ? <Badge variant="secondary">{formatLabels[offer.work_format] ?? offer.work_format}</Badge> : null}{offer.city ? <Badge variant="secondary">{offer.city}</Badge> : null}</div><p className="text-xs text-muted-foreground">Отправлено {date(invitation.created_at)}{invitation.status === 'pending' ? ` · Ответ до ${date(invitation.expires_at)}` : invitation.responded_at ? ` · Решение ${date(invitation.responded_at)}` : ''}</p></header>

    {employer ? <p className="text-sm text-muted-foreground">Кандидат: {candidateName || (candidate.isPending ? 'Загружаем имя…' : 'Профиль недоступен')}</p> : null}
    {invitation.message ? <section className="space-y-2 border-t pt-5"><h4 className="text-sm font-semibold">{employer ? 'Ваше сообщение' : 'Почему вас пригласили'}</h4><p className="whitespace-pre-wrap break-words text-sm leading-6 text-muted-foreground">{invitation.message}</p></section> : null}
    {invitation.response_message ? <section className="space-y-2 border-t pt-5"><h4 className="text-sm font-semibold">Ответ кандидата</h4><p className="whitespace-pre-wrap break-words text-sm leading-6 text-muted-foreground">{invitation.response_message}</p></section> : null}
    {invitation.status === 'pending' ? <InvitationDecision invitation={invitation} employer={employer} userId={userId} /> : null}
    {invitation.status === 'accepted' ? <InvitationConnection invitation={invitation} employer={employer} userId={userId} /> : <p className="flex gap-2 border-t pt-5 text-xs leading-5 text-muted-foreground"><LockKeyhole size={16} className="shrink-0" aria-hidden="true" />Контакты по этому приглашению открываются после его принятия кандидатом.</p>}
  </article>
}

function InvitationDecision({ invitation, employer, userId }: { invitation: InvitationResponse; employer: boolean; userId: string }) {
  const [action, setAction] = useState<'accept' | 'decline' | 'withdraw' | null>(null)
  const client = useQueryClient()
  const mutation = useMutation({
    mutationFn: (target: 'accept' | 'decline' | 'withdraw') => respondToInvitation(invitation.id, target, ''),
    onSuccess: (saved) => {
      client.setQueryData<InvitationResponse[]>(invitationKey(userId), (items) => items?.map((item) => item.id === saved.id ? saved : item))
      setAction(null)
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: invitationKey(userId) })
      void client.invalidateQueries({ queryKey: ['chat', userId] })
      void client.invalidateQueries({ queryKey: ['talent-matches', userId] })
    },
  })
  const label = action === 'accept' ? 'Принять приглашение' : action === 'decline' ? 'Отклонить приглашение' : 'Отозвать приглашение'
  return <div className="flex flex-wrap gap-2 border-t pt-5">
    {employer ? <Button variant="outline" onClick={() => { mutation.reset(); setAction('withdraw') }}>Отозвать приглашение</Button> : <><Button onClick={() => { mutation.reset(); setAction('accept') }}><Check size={16} aria-hidden="true" />Принять приглашение</Button><Button variant="outline" onClick={() => { mutation.reset(); setAction('decline') }}><X size={16} aria-hidden="true" />Отклонить</Button></>}
    <AlertDialog open={Boolean(action)} onOpenChange={(open) => { if (!open && !mutation.isPending) setAction(null) }}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>{label}?</AlertDialogTitle><AlertDialogDescription>{action === 'accept' ? 'Работодатель получит ваши контакты. Можно будет перейти к обсуждению следующего шага в чате.' : action === 'decline' ? 'Работодатель увидит отказ. Контакты по этому приглашению останутся закрыты.' : 'Кандидат больше не сможет принять это предложение.'}</AlertDialogDescription></AlertDialogHeader><p className="text-sm font-medium">{invitation.vacancy.title}</p>{mutation.isError ? <RequestError error={mutation.error} /> : null}<AlertDialogFooter><AlertDialogCancel disabled={mutation.isPending}>Отмена</AlertDialogCancel><Button disabled={mutation.isPending} onClick={() => { if (action) mutation.mutate(action) }}>{mutation.isPending ? <Spinner label="Сохраняем решение…" /> : label}</Button></AlertDialogFooter></AlertDialogContent></AlertDialog>
  </div>
}

function InvitationConnection({ invitation, employer, userId }: { invitation: InvitationResponse; employer: boolean; userId: string }) {
  const conversation = useQuery({ queryKey: ['invitation-conversation', userId, invitation.id], queryFn: ({ signal }) => invitationConversation(invitation.id, signal), refetchInterval: (query) => query.state.data == null && query.state.dataUpdateCount < 10 ? 3000 : false })
  const contacts = useQuery({ queryKey: ['invitation-contacts', userId, invitation.candidate_id], queryFn: ({ signal }) => candidateContacts(invitation.candidate_id, signal), enabled: employer, refetchInterval: (query) => query.state.data?.contact_access === 'hidden' && query.state.dataUpdateCount < 10 ? 5000 : false })
  return <section className="space-y-4 border-t pt-5"><h4 className="text-sm font-semibold">Приглашение принято</h4>
    {employer && contacts.isPending ? <Spinner label="Проверяем доступ к контактам…" /> : null}
    {employer && contacts.isError ? <RequestError error={contacts.error} onRetry={() => { void contacts.refetch() }} /> : null}
    {employer && contacts.data ? contacts.data.contact_access === 'granted' ? <div className="space-y-2 rounded-lg bg-muted/40 p-4 text-sm"><p className="font-medium">{[contacts.data.last_name, contacts.data.first_name, contacts.data.middle_name].filter(Boolean).join(' ') || 'Контакты кандидата'}</p><p>Почта: {contacts.data.contact_email || 'не указана'}</p><p>Телефон: {contacts.data.phone || 'не указан'}</p><p>Telegram: {contacts.data.telegram || 'не указан'}</p></div> : <p role="status" className="text-sm text-muted-foreground">Сервер ещё открывает доступ к контактам. Проверяем автоматически.</p> : null}
    {conversation.isPending ? <Spinner label="Ищем диалог…" /> : conversation.isError ? <RequestError error={conversation.error} onRetry={() => { void conversation.refetch() }} /> : conversation.data ? <Button asChild><Link to="/messages/$conversationId" params={{ conversationId: conversation.data.id }} search={{ section: undefined, invitation: undefined }}>Перейти к чату<ArrowRight size={16} aria-hidden="true" /></Link></Button> : <div className="space-y-2"><p role="status" className="text-sm text-muted-foreground">Приглашение принято. Диалог появится после обработки сервером.</p><Button variant="outline" size="sm" onClick={() => { void conversation.refetch() }}>Проверить диалог</Button></div>}
  </section>
}
