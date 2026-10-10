import { Check, CheckCheck } from 'lucide-react'
import { messageTime } from '@/features/chat/model/chat-presentation'
import { ChatAttachment } from '@/features/chat/ui/chat-attachment'
import type { MessageResponse } from '@/shared/api/generated/chat/models'

const kindLabels = { text: '', system: 'Событие', task: 'Задание', task_submission: 'Решение задания', assessment: 'Результат оценки' }

export function ChatMessage({ message, own, read }: { message: MessageResponse; own: boolean; read: boolean }) {
  if (message.kind === 'system') return <div className="chat-system-message"><p>{message.text}</p><time dateTime={message.created_at}>{messageTime(message.created_at)}</time></div>
  return <article className={`chat-bubble ${own ? 'chat-bubble-own' : 'chat-bubble-incoming'}`} aria-label={own ? 'Ваше сообщение' : 'Сообщение собеседника'}>
    {message.kind !== 'text' ? <p className="mb-2 text-xs font-semibold opacity-80">{kindLabels[message.kind]}</p> : null}
    {message.text ? <p className="whitespace-pre-wrap break-words text-sm leading-6 [overflow-wrap:anywhere]">{message.text}</p> : null}
    {message.attachments.length ? <div className={message.text ? 'mt-3 space-y-2' : 'space-y-2'}>{message.attachments.map((attachment) => <ChatAttachment key={attachment.id} attachment={attachment} />)}</div> : null}
    <div className="chat-message-meta"><time dateTime={message.created_at}>{messageTime(message.created_at)}</time>{own ? <span title={read ? 'Прочитано' : 'Отправлено'}><span className="sr-only">{read ? 'Прочитано' : 'Отправлено'}</span>{read ? <CheckCheck size={14} aria-hidden="true" /> : <Check size={14} aria-hidden="true" />}</span> : null}</div>
  </article>
}
