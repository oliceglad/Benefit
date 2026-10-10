import { useState } from 'react'
import { Download, FileText } from 'lucide-react'
import { downloadAttachment } from '@/features/chat/api/chat'
import { fileSize } from '@/features/chat/model/chat-presentation'
import type { AttachmentResponse } from '@/shared/api/generated/chat/models'
import { RequestError } from '@/shared/api/ui/request-error'
import { Spinner } from '@/shared/ui/spinner'

export function ChatAttachment({ attachment }: { attachment: AttachmentResponse }) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<unknown>(null)
  async function download() {
    setPending(true)
    setError(null)
    try {
      const blob = await downloadAttachment(attachment.id)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = attachment.filename
      link.click()
      // Leave time for the browser to start reading the blob before releasing it.
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch (cause) { setError(cause) }
    finally { setPending(false) }
  }
  return <div className="space-y-2">
    <button type="button" className="chat-attachment" disabled={pending} onClick={() => void download()} aria-label={`Скачать ${attachment.filename}`}>
      <FileText className="size-5 shrink-0" aria-hidden="true" />
      <span className="min-w-0 flex-1 text-left"><span className="block break-all text-sm font-medium">{attachment.filename}</span><span className="text-xs opacity-75">{fileSize(attachment.size)}</span></span>
      {pending ? <Spinner label="Скачиваем файл…" /> : <Download className="size-4 shrink-0" aria-hidden="true" />}
    </button>
    {error ? <RequestError error={error} onRetry={() => void download()} /> : null}
  </div>
}
