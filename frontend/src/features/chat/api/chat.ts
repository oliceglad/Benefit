import {
  getConversationApiV1ChatConversationsConversationIdGet,
  getDownloadAttachmentApiV1ChatAttachmentsAttachmentIdGetUrl,
  listConversationsApiV1ChatConversationsGet,
  listMessagesApiV1ChatConversationsConversationIdMessagesGet,
  markReadApiV1ChatConversationsConversationIdReadPost,
  sendMessageApiV1ChatConversationsConversationIdMessagesPost,
  uploadAttachmentApiV1ChatConversationsConversationIdAttachmentsPost,
} from '@/shared/api/generated/chat/chat'
import type { MessageCreate } from '@/shared/api/generated/chat/models'
import { orvalFetch } from '@/shared/api/transport/orval-fetch'
import { requestOptions } from '@/shared/lib/request-options'

export const chatKeys = {
  all: (userId: string) => ['chat', userId] as const,
  conversations: (userId: string) => ['chat', userId, 'conversations'] as const,
  conversation: (userId: string, id: string) => ['chat', userId, 'conversation', id] as const,
  messages: (userId: string, id: string) => ['chat', userId, 'messages', id] as const,
}

export async function getConversations(signal?: AbortSignal) {
  const response = await listConversationsApiV1ChatConversationsGet(undefined, requestOptions(signal))
  if (response.status !== 200) throw new Error('Unexpected conversations response')
  return response.data
}

export async function getConversation(id: string, signal?: AbortSignal) {
  const response = await getConversationApiV1ChatConversationsConversationIdGet(id, requestOptions(signal))
  if (response.status !== 200) throw new Error('Unexpected conversation response')
  return response.data
}

export async function getMessages(id: string, before?: string, signal?: AbortSignal) {
  const response = await listMessagesApiV1ChatConversationsConversationIdMessagesGet(id, { before, limit: 50 }, requestOptions(signal))
  if (response.status !== 200) throw new Error('Unexpected messages response')
  return response.data
}

export async function sendMessage(id: string, body: MessageCreate) {
  const response = await sendMessageApiV1ChatConversationsConversationIdMessagesPost(id, body, requestOptions())
  if (response.status !== 201) throw new Error('Unexpected send response')
  return response.data
}

export async function markRead(id: string, messageId: string) {
  await markReadApiV1ChatConversationsConversationIdReadPost(id, { message_id: messageId }, requestOptions())
}

export async function uploadAttachment(id: string, file: File, signal: AbortSignal) {
  const response = await uploadAttachmentApiV1ChatConversationsConversationIdAttachmentsPost(id, { file }, { signal })
  if (response.status !== 201) throw new Error('Unexpected attachment response')
  return response.data
}

export async function downloadAttachment(id: string) {
  return (await orvalFetch<{ data: Blob }>(getDownloadAttachmentApiV1ChatAttachmentsAttachmentIdGetUrl(id), {
    ...requestOptions(), responseType: 'blob',
  })).data
}
