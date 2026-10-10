import { useMutation } from '@tanstack/react-query'
import { Paperclip, Send, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { sendMessage, uploadAttachment } from '@/features/chat/api/chat'
import { chatFileAccept, fileSize, validateChatFiles } from '@/features/chat/model/chat-presentation'
import { emptyChatDraft, type ChatDraft } from '@/features/chat/model/chat-draft'
import type { MessageCreate, MessageResponse } from '@/shared/api/generated/chat/models'
import { RequestError } from '@/shared/api/ui/request-error'
import { Button } from '@/shared/ui/button'
import { Spinner } from '@/shared/ui/spinner'

export function ChatComposer({ conversationId, draft, onChange, onSent }: {
  conversationId: string
  draft: ChatDraft
  onChange: (draft: ChatDraft) => void
  onSent: (message: MessageResponse) => void
}) {
  const fileInput = useRef<HTMLInputElement>(null)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const draftRef = useRef(draft)
  const uploadController = useRef<AbortController | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<unknown>(null)
  const [validation, setValidation] = useState<string | null>(null)
  useEffect(() => { draftRef.current = draft }, [draft])
  useEffect(() => () => uploadController.current?.abort(), [])

  const send = useMutation({
    mutationFn: (payload: MessageCreate) => sendMessage(conversationId, payload),
    onSuccess: (message) => {
      onChange(emptyChatDraft)
      onSent(message)
      textarea.current?.focus()
    },
  })
  const canSend = Boolean(draft.text.trim() || draft.attachments.length) && !uploading && !send.isPending

  function submit() {
    if (!canSend) return
    const payload = { text: draft.text.trim(), attachment_ids: draft.attachments.map((file) => file.id) }
    const fingerprint = JSON.stringify(payload)
    // An unchanged retry uses the same key, including when the server received a timed-out request.
    const attempt = draft.attempt?.fingerprint === fingerprint ? draft.attempt : { fingerprint, clientId: crypto.randomUUID() }
    onChange({ ...draft, attempt })
    send.mutate({ ...payload, client_id: attempt.clientId })
  }

  async function upload(files: File[]) {
    if (uploading || send.isPending || files.length === 0) return
    const problem = validateChatFiles(files, draft.attachments.length)
    setValidation(problem)
    if (problem) return
    setUploading(true)
    setUploadError(null)
    const controller = new AbortController()
    uploadController.current = controller
    try {
      for (const file of files) {
        const attachment = await uploadAttachment(conversationId, file, AbortSignal.any([controller.signal, AbortSignal.timeout(60_000)]))
        if (controller.signal.aborted) return
        const next = { ...draftRef.current, attachments: [...draftRef.current.attachments, attachment] }
        draftRef.current = next
        onChange(next)
      }
    } catch (error) {
      if (!controller.signal.aborted) setUploadError(error)
    } finally {
      if (!controller.signal.aborted) setUploading(false)
    }
  }

  return <form className="chat-composer" onSubmit={(event) => { event.preventDefault(); submit() }}>
    {send.error ? <div className="mb-3"><RequestError error={send.error} /><p className="mt-2 text-xs text-muted-foreground">Текст сохранён. Нажмите «Отправить» ещё раз, чтобы повторить отправку.</p></div> : null}
    {uploadError ? <div className="mb-3"><RequestError error={uploadError} /></div> : null}
    {validation ? <p role="alert" className="mb-3 text-sm text-destructive">{validation}</p> : null}
    {draft.attachments.length ? <ul aria-label="Прикреплённые файлы" className="mb-3 flex max-h-28 flex-wrap gap-2 overflow-auto">
      {draft.attachments.map((file) => <li key={file.id} className="flex max-w-full items-center gap-2 rounded-lg border bg-muted/40 py-1 pl-3 pr-1 text-xs"><span className="truncate">{file.filename} · {fileSize(file.size)}</span><Button type="button" size="icon" variant="ghost" className="size-8 min-h-8" aria-label={`Убрать ${file.filename}`} disabled={send.isPending || uploading} onClick={() => onChange({ ...draft, attachments: draft.attachments.filter((item) => item.id !== file.id) })}><X aria-hidden="true" /></Button></li>)}
    </ul> : null}
    <label htmlFor="chat-message" className="sr-only">Сообщение</label>
    <textarea id="chat-message" ref={textarea} rows={2} maxLength={4000} placeholder="Напишите сообщение…" className="chat-message-input" value={draft.text} disabled={send.isPending} onChange={(event) => { onChange({ ...draft, text: event.target.value }); send.reset() }} onKeyDown={(event) => {
      if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); submit() }
    }} />
    <div className="mt-2 flex items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2">
        <input ref={fileInput} type="file" multiple accept={chatFileAccept} className="sr-only" tabIndex={-1} aria-label="Выбрать вложения" onChange={(event) => { const files = Array.from(event.target.files ?? []); event.target.value = ''; void upload(files) }} />
        <Button type="button" variant="ghost" size="icon" disabled={uploading || send.isPending || draft.attachments.length >= 10} aria-label="Прикрепить файлы" onClick={() => fileInput.current?.click()}>{uploading ? <Spinner label="Загружаем файлы…" /> : <Paperclip aria-hidden="true" />}</Button>
        <span className="hidden text-[11px] text-muted-foreground sm:block">{uploading ? 'Загружаем файлы…' : 'Enter — отправить · Shift + Enter — новая строка'}</span>
      </div>
      <div className="flex items-center gap-3"><span className="text-[11px] tabular-nums text-muted-foreground">{draft.text.length} / 4000</span><Button type="submit" size="sm" disabled={!canSend}>{send.isPending ? <Spinner label="Отправляем…" /> : <Send aria-hidden="true" />}Отправить</Button></div>
    </div>
    <p className="mt-1 pl-3 text-[10px] text-muted-foreground">До 10 файлов, не больше 20 МБ каждый.</p>
  </form>
}
