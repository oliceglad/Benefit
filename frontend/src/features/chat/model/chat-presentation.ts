import type { ConversationResponse, MessageResponse } from '@/shared/api/generated/chat/models'

const timeFormat = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' })
const dayFormat = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })

export function messageTime(value: string) { return timeFormat.format(new Date(value)) }
export function messageDay(value: string) { return dayFormat.format(new Date(value)) }

export function conversationName(conversation: ConversationResponse, employer: boolean) {
  // The chat contract exposes participant IDs, but no candidate/recruiter display names.
  return employer ? `Кандидат · ${conversation.candidate_id.slice(0, 6)}` : conversation.company_name
}

export function messagePreview(message: MessageResponse | null) {
  if (!message) return 'Начните разговор о вакансии'
  return message.text || (message.attachments.length ? `Вложений: ${message.attachments.length}` : 'Событие в диалоге')
}

export function fileSize(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} КБ` : `${(bytes / 1024 / 1024).toFixed(1)} МБ`
}

export const chatFileAccept = '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.odt,.txt,.md,.csv,.json,.png,.jpg,.jpeg,.gif,.webp,.zip,.py,.ipynb,.sql,.java,.kt,.go,.ts,.tsx,.jsx,.cs,.cpp,.c,.h,.rs,.yaml,.yml'

export function validateChatFiles(files: File[], existingCount: number): string | null {
  if (files.length + existingCount > 10) return 'К сообщению можно прикрепить не больше 10 файлов.'
  for (const file of files) {
    const extension = file.name.includes('.') ? `.${file.name.split('.').at(-1)?.toLowerCase()}` : ''
    if (!chatFileAccept.split(',').includes(extension)) return `Формат файла «${file.name}» не поддерживается.`
    if (file.size > 20 * 1024 * 1024) return `Файл «${file.name}» превышает 20 МБ.`
    if (file.size === 0) return `Файл «${file.name}» пуст.`
  }
  return null
}
