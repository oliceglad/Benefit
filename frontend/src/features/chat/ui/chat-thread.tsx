import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ArrowDown, ArrowLeft, BriefcaseBusiness, LockKeyhole, MessageSquare } from 'lucide-react'
import { Fragment, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { chatKeys, getConversation, getMessages, markRead } from '@/features/chat/api/chat'
import { conversationName, messageDay } from '@/features/chat/model/chat-presentation'
import type { ChatDraft } from '@/features/chat/model/chat-draft'
import { ChatComposer } from '@/features/chat/ui/chat-composer'
import { ChatMessage } from '@/features/chat/ui/chat-message'
import type { MessageResponse } from '@/shared/api/generated/chat/models'
import { isApiError } from '@/shared/api/transport/api-error'
import { RequestError } from '@/shared/api/ui/request-error'
import { Button } from '@/shared/ui/button'
import { Spinner } from '@/shared/ui/spinner'

export function ChatThread({ id, userId, employer, live, draft, onDraftChange }: {
  id: string; userId: string; employer: boolean; live: boolean
  draft: ChatDraft; onDraftChange: (draft: ChatDraft) => void
}) {
  const client = useQueryClient()
  const conversation = useQuery({ queryKey: chatKeys.conversation(userId, id), queryFn: ({ signal }) => getConversation(id, signal), refetchInterval: live ? false : 10_000 })
  const history = useInfiniteQuery({
    queryKey: chatKeys.messages(userId, id),
    queryFn: ({ pageParam, signal }) => getMessages(id, pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.length >= 50 ? page[0].id : undefined,
    enabled: conversation.isSuccess,
    refetchInterval: live ? false : 5000,
  })
  const seen = new Set<string>()
  const messages = [...(history.data?.pages ?? [])].reverse().flat().filter((message) => {
    if (seen.has(message.id)) return false
    seen.add(message.id)
    return true
  })
  const latestId = messages.at(-1)?.id
  const firstId = messages[0]?.id
  const scroll = useRef<HTMLDivElement>(null)
  const nearBottom = useRef(true)
  const initialScroll = useRef(true)
  const olderAnchor = useRef<{ height: number; top: number; firstId: string | undefined } | null>(null)
  const attemptedRead = useRef<string | null>(null)
  const [atBottom, setAtBottom] = useState(true)
  const [focused, setFocused] = useState(() => document.visibilityState === 'visible' && document.hasFocus())

  useEffect(() => {
    const update = () => setFocused(document.visibilityState === 'visible' && document.hasFocus())
    window.addEventListener('focus', update)
    window.addEventListener('blur', update)
    document.addEventListener('visibilitychange', update)
    return () => {
      window.removeEventListener('focus', update)
      window.removeEventListener('blur', update)
      document.removeEventListener('visibilitychange', update)
    }
  }, [])

  useLayoutEffect(() => {
    const element = scroll.current
    if (!element || history.isPending) return
    const anchor = olderAnchor.current
    if (anchor && anchor.firstId !== firstId) {
      element.scrollTop = anchor.top + element.scrollHeight - anchor.height
      olderAnchor.current = null
    } else if (initialScroll.current || nearBottom.current) {
      element.scrollTop = element.scrollHeight
      initialScroll.current = false
    }
    nearBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 64
    setAtBottom(nearBottom.current)
  }, [latestId, firstId, messages.length, history.isPending])

  const read = useMutation({
    mutationFn: (messageId: string) => markRead(id, messageId),
    onSuccess: () => { void client.invalidateQueries({ queryKey: chatKeys.conversations(userId) }) },
  })
  const mark = read.mutate
  useEffect(() => {
    if (!focused || !atBottom || !latestId || attemptedRead.current === latestId) return
    attemptedRead.current = latestId
    mark(latestId)
  }, [focused, atBottom, latestId, mark])

  function jumpToLatest() {
    if (scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight
    nearBottom.current = true
    setAtBottom(true)
  }

  function sent(message: MessageResponse) {
    jumpToLatest()
    client.setQueryData<typeof history.data>(chatKeys.messages(userId, id), (current) => {
      if (!current) return current
      if (current.pages.some((page) => page.some((item) => item.id === message.id))) return current
      // Append only server-confirmed messages, keeping the older-page cursor intact.
      return { ...current, pages: [[...current.pages[0], message], ...current.pages.slice(1)] }
    })
    void client.invalidateQueries({ queryKey: chatKeys.messages(userId, id) })
    void client.invalidateQueries({ queryKey: chatKeys.conversations(userId) })
  }

  if (conversation.isPending) return <div className="chat-empty"><Spinner label="Открываем диалог…" /></div>
  if (!conversation.data) return <div className="p-6">{isApiError(conversation.error) && conversation.error.status === 404 ? <div className="chat-empty"><LockKeyhole aria-hidden="true" /><h2>Диалог недоступен</h2><p>Он не найден или у вашего аккаунта нет к нему доступа.</p><Button variant="outline" asChild><Link to="/messages">К сообщениям</Link></Button></div> : <RequestError error={conversation.error} onRetry={() => void conversation.refetch()} />}</div>
  const value = conversation.data
  const closed = value.status === 'closed'
  const name = conversationName(value, employer)

  return <section className="chat-thread" aria-label={`Диалог: ${value.vacancy_title}`}>
    <header className="chat-thread-header">
      <Button asChild variant="ghost" size="icon" className="md:hidden" aria-label="К списку диалогов"><Link to="/messages"><ArrowLeft aria-hidden="true" /></Link></Button>
      <span className="chat-avatar" aria-hidden="true">{employer ? 'К' : value.company_name.slice(0, 1).toUpperCase()}</span>
      <div className="min-w-0 flex-1"><h2 className="truncate text-sm font-semibold">{name}</h2><p className="mt-1 truncate text-xs text-muted-foreground">{employer ? value.company_name : 'Работодатель'}</p></div>
      <span className={`chat-state ${closed ? 'chat-state-closed' : ''}`}>{closed ? 'Завершён' : 'Диалог открыт'}</span>
    </header>
    <div className="chat-vacancy-context"><BriefcaseBusiness className="size-4 shrink-0 text-primary" aria-hidden="true" /><span className="min-w-0 break-words">{value.vacancy_title}</span><span className="ml-auto shrink-0 text-[11px] text-muted-foreground">{value.source === 'application' ? 'По отклику' : 'По приглашению'}</span></div>
    {conversation.isRefetchError ? <div className="p-3"><RequestError error={conversation.error} onRetry={() => void conversation.refetch()} /></div> : null}
    <div className="chat-history-wrap">
      <div ref={scroll} className="chat-history" role="log" aria-label="История переписки" aria-live="off" tabIndex={0} onScroll={() => {
        const element = scroll.current
        if (!element) return
        nearBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 64
        setAtBottom(nearBottom.current)
      }}>
        {history.hasNextPage ? <div className="mb-5 text-center"><Button size="sm" variant="outline" disabled={history.isFetchingNextPage} onClick={() => {
          if (scroll.current) olderAnchor.current = { height: scroll.current.scrollHeight, top: scroll.current.scrollTop, firstId }
          void history.fetchNextPage()
        }}>{history.isFetchingNextPage ? <Spinner label="Загружаем историю…" /> : null}Предыдущие сообщения</Button></div> : null}
        {history.isError ? <RequestError error={history.error} onRetry={() => { if (history.isFetchNextPageError) void history.fetchNextPage(); else void history.refetch() }} /> : null}
        {history.isPending ? <div className="chat-empty"><Spinner label="Загружаем сообщения…" /></div> : null}
        {history.isSuccess && messages.length === 0 ? <div className="chat-empty"><MessageSquare aria-hidden="true" /><h3>Начните разговор</h3><p>Здесь можно обсудить вакансию и договориться о следующих шагах.</p></div> : null}
        {messages.map((message, index) => {
          const previous = messages[index - 1]
          const newDay = !previous || messageDay(previous.created_at) !== messageDay(message.created_at)
          const grouped = !newDay && previous.sender_id === message.sender_id && previous.kind !== 'system' && message.kind !== 'system'
          const own = message.sender_id === userId
          const receivedReadAt = value.other_party_last_read_at ? new Date(value.other_party_last_read_at).getTime() : 0
          return <Fragment key={message.id}>
            {newDay ? <p className="chat-day">{messageDay(message.created_at)}</p> : null}
            <div className={`chat-message-row ${own ? 'chat-message-row-own' : ''} ${grouped ? 'chat-message-row-grouped' : ''}`}><ChatMessage message={message} own={own} read={own && new Date(message.created_at).getTime() <= receivedReadAt} /></div>
          </Fragment>
        })}
      </div>
      {!atBottom && messages.length ? <Button type="button" variant="outline" size="sm" className="chat-jump" onClick={jumpToLatest}><ArrowDown aria-hidden="true" />К последним сообщениям</Button> : null}
    </div>
    {read.error ? <div className="px-5 py-2"><p className="text-xs text-muted-foreground">Не удалось отметить сообщения прочитанными.</p><Button size="sm" variant="ghost" onClick={() => { if (latestId) read.mutate(latestId) }}>Повторить</Button></div> : null}
    {closed ? <div className="chat-closed-notice"><LockKeyhole className="size-4 shrink-0" aria-hidden="true" /><p>Диалог завершён. История доступна для просмотра, новые сообщения отправить нельзя.</p></div> : <ChatComposer conversationId={id} draft={draft} onChange={onDraftChange} onSent={sent} />}
  </section>
}
