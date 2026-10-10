import { useQuery } from '@tanstack/react-query'
import { Link, useBlocker, useParams, useSearch } from '@tanstack/react-router'
import { MessageSquare, RefreshCw, Search } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { chatKeys, getConversations } from '@/features/chat/api/chat'
import { conversationName, messagePreview, messageTime } from '@/features/chat/model/chat-presentation'
import { useChatConnection } from '@/features/chat/model/use-chat-connection'
import { emptyChatDraft, type ChatDraft } from '@/features/chat/model/chat-draft'
import { ChatThread } from '@/features/chat/ui/chat-thread'
import { RequestError } from '@/shared/api/ui/request-error'
import { useSession } from '@/shared/session/session'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/shared/ui/alert-dialog'
import { BrandMark } from '@/shared/ui/brand-logo'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Spinner } from '@/shared/ui/spinner'
import './chat.css'

export function MessagesPage({ invitationsPanel }: { invitationsPanel?: ReactNode }) {
  const user = useSession().user
  if (!user) return null
  return <MessagesWorkspace key={user.id} userId={user.id} employer={user.role === 'employer'} invitationsPanel={invitationsPanel} />
}

function MessagesWorkspace({ userId, employer, invitationsPanel }: { userId: string; employer: boolean; invitationsPanel?: ReactNode }) {
  const { conversationId } = useParams({ strict: false })
  const routeSearch = useSearch({ strict: false })
  const showInvitations = routeSearch.section === 'invitations' && Boolean(invitationsPanel)
  const connection = useChatConnection(userId)
  const [search, setSearch] = useState('')
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [drafts, setDrafts] = useState<Record<string, ChatDraft>>({})
  const hasDrafts = Object.values(drafts).some((draft) => draft.text.trim() || draft.attachments.length)
  const blocker = useBlocker({ shouldBlockFn: ({ next }) => hasDrafts && !next.pathname.startsWith('/messages'), enableBeforeUnload: hasDrafts, withResolver: true })
  const conversations = useQuery({ queryKey: chatKeys.conversations(userId), queryFn: ({ signal }) => getConversations(signal), refetchInterval: connection.status === 'live' ? false : 10_000 })
  const all = conversations.data ?? []
  const unreadCount = all.reduce((sum, item) => sum + item.unread_count, 0)
  const filtered = all.filter((item) => (!unreadOnly || item.unread_count > 0) && [conversationName(item, employer), item.vacancy_title, item.company_name, item.last_message?.text].join(' ').toLocaleLowerCase('ru-RU').includes(search.trim().toLocaleLowerCase('ru-RU')))
    .sort((a, b) => new Date(b.last_message_at ?? b.created_at).getTime() - new Date(a.last_message_at ?? a.created_at).getTime())
  return <section className="space-y-5">
    <header className="flex flex-wrap items-center justify-between gap-4"><div><p className="mb-2 text-xs font-medium text-primary">НА СВЯЗИ С КОМАНДОЙ</p><h1 className="text-3xl font-semibold tracking-tight">Сообщения<span className="text-primary">.</span></h1><p className="mt-2 text-sm text-muted-foreground">{employer ? 'Обсуждайте вакансии и следующие шаги с кандидатами.' : 'Всё общение с работодателями — в одном месте.'}</p></div><div className="chat-connection" role="status">{connection.status === 'live' ? <><span className="chat-connection-dot" />Обновляется в реальном времени</> : <><RefreshCw className="size-3.5" aria-hidden="true" />Периодическое обновление<Button type="button" size="sm" variant="ghost" onClick={connection.reconnect} aria-label="Переподключить чат"><RefreshCw aria-hidden="true" /></Button></>}</div></header>
    {invitationsPanel ? <nav aria-label="Разделы сообщений" className="flex gap-2 border-b pb-3"><Button asChild variant={showInvitations ? 'ghost' : 'outline'}><Link to="/messages" search={{ section: undefined, invitation: undefined }} aria-current={!showInvitations ? 'page' : undefined}>Диалоги</Link></Button><Button asChild variant={showInvitations ? 'outline' : 'ghost'}><Link to="/messages" search={{ section: 'invitations', invitation: undefined }} aria-current={showInvitations ? 'page' : undefined}>Приглашения</Link></Button></nav> : null}
    {showInvitations ? invitationsPanel : <div className={`chat-workspace ${conversationId ? 'chat-workspace-selected' : ''}`}>
      <aside className="chat-sidebar" aria-label="Диалоги">
        <div className="chat-sidebar-tools"><div className="mb-4 flex items-center justify-between"><h2 className="text-sm font-semibold">Диалоги <span className="ml-1 text-muted-foreground">{all.length}</span></h2>{unreadCount ? <span className="chat-unread-count" aria-label={`Непрочитанных сообщений: ${unreadCount}`}>{unreadCount}</span> : null}</div><div className="relative"><Search className="pointer-events-none absolute left-3 top-3.5 size-4 text-muted-foreground" aria-hidden="true" /><Input aria-label="Поиск по диалогам" placeholder="Компания или вакансия" className="rounded-lg pl-9 text-sm" value={search} onChange={(event) => setSearch(event.target.value)} /></div><div className="mt-3 flex gap-2"><Button type="button" size="sm" variant={unreadOnly ? 'ghost' : 'outline'} className="min-h-8 text-xs" aria-pressed={!unreadOnly} onClick={() => setUnreadOnly(false)}>Все</Button><Button type="button" size="sm" variant={unreadOnly ? 'outline' : 'ghost'} className="min-h-8 text-xs" aria-pressed={unreadOnly} onClick={() => setUnreadOnly(true)}>Непрочитанные</Button></div></div>
        <div className="chat-conversation-list">
          {conversations.isPending ? <div className="p-5"><Spinner label="Загружаем диалоги…" /></div> : null}
          {conversations.isError ? <div className="p-4"><RequestError error={conversations.error} onRetry={() => void conversations.refetch()} /></div> : null}
          {conversations.isSuccess && filtered.length === 0 ? <div className="px-5 py-8 text-sm leading-6 text-muted-foreground">{all.length === 0 ? 'Диалог появится после отклика на вакансию или приглашения кандидата.' : 'Подходящих диалогов нет. Попробуйте изменить фильтры.'}</div> : null}
          {filtered.map((item) => <Link key={item.id} to="/messages/$conversationId" params={{ conversationId: item.id }} className={`chat-conversation ${conversationId === item.id ? 'chat-conversation-active' : ''}`} aria-current={conversationId === item.id ? 'page' : undefined}>
            <span className="chat-list-avatar" aria-hidden="true">{employer ? 'К' : item.company_name.slice(0, 1).toUpperCase()}</span><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><span className="truncate text-sm font-semibold">{conversationName(item, employer)}</span><time className="ml-auto shrink-0 text-[10px] text-muted-foreground" dateTime={item.last_message_at ?? item.created_at}>{messageTime(item.last_message_at ?? item.created_at)}</time></div><p className="mt-1 truncate text-xs text-muted-foreground">{item.vacancy_title}</p><div className="mt-2 flex items-center gap-2"><p className="line-clamp-1 flex-1 break-all text-xs text-muted-foreground">{item.last_message?.sender_id === userId ? 'Вы: ' : ''}{messagePreview(item.last_message)}</p>{item.unread_count ? <span className="chat-unread-count">{item.unread_count}</span> : null}{item.status === 'closed' ? <span className="text-[10px] text-muted-foreground">Завершён</span> : null}</div></div>
          </Link>)}
        </div>
        <div className="chat-sidebar-footer"><MessageSquare className="size-4" aria-hidden="true" /><span>Диалог по отклику или приглашению</span></div>
      </aside>
      {conversationId ? <ChatThread key={conversationId} id={conversationId} userId={userId} employer={employer} live={connection.status === 'live'} draft={drafts[conversationId] ?? emptyChatDraft} onDraftChange={(draft) => setDrafts((current) => ({ ...current, [conversationId]: draft }))} /> : <div className="chat-empty chat-start"><div className="chat-brand-shape"><BrandMark className="size-16" /></div><h2>Разговор начинается здесь</h2><p>Выберите диалог, чтобы обсудить условия<br className="hidden sm:block" /> и следующий шаг к новой команде.</p></div>}
    </div>}
    <AlertDialog open={blocker.status === 'blocked'}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Выйти из сообщений?</AlertDialogTitle><AlertDialogDescription>В диалогах есть неотправленные сообщения. При выходе их текст и вложения будут удалены из черновиков.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel onClick={() => blocker.reset?.()}>Остаться</AlertDialogCancel><Button variant="outline" onClick={() => blocker.proceed?.()}>Выйти</Button></AlertDialogFooter></AlertDialogContent></AlertDialog>
  </section>
}
