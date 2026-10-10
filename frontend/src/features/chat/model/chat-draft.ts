import type { AttachmentResponse } from '@/shared/api/generated/chat/models'

export type ChatDraft = {
  text: string
  attachments: AttachmentResponse[]
  attempt?: { fingerprint: string; clientId: string }
}
export const emptyChatDraft: ChatDraft = { text: '', attachments: [] }
