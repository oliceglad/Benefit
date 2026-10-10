import {
  acceptApiV1InvitationsInvitationIdAcceptPost, createInvitationApiV1InvitationsPost,
  declineApiV1InvitationsInvitationIdDeclinePost, incomingApiV1InvitationsIncomingGet,
  sentApiV1InvitationsSentGet, withdrawApiV1InvitationsInvitationIdWithdrawPost,
} from '@/shared/api/generated/applications/applications'
import type { InvitationCreate } from '@/shared/api/generated/applications/models'
import { getCandidateApiV1CandidatesUserIdGet } from '@/shared/api/generated/candidates/candidates'
import { listConversationsApiV1ChatConversationsGet } from '@/shared/api/generated/chat/chat'
import { myCompanyApiV1EmployersCompanyGet, myVacanciesApiV1EmployersVacanciesGet } from '@/shared/api/generated/employers/employers'
import { isApiError } from '@/shared/api/transport/api-error'
import { requestOptions } from '@/shared/lib/request-options'

export const invitationKey = (userId: string | undefined) => ['invitations', userId] as const

export async function listInvitations(employer: boolean, signal?: AbortSignal) {
  const response = await (employer ? sentApiV1InvitationsSentGet : incomingApiV1InvitationsIncomingGet)(undefined, requestOptions(signal))
  if (response.status !== 200) throw new Error('Unexpected invitation list response')
  return response.data
}

export async function sendInvitation(input: InvitationCreate) {
  const response = await createInvitationApiV1InvitationsPost(input, requestOptions())
  if (response.status !== 201) throw new Error('Unexpected invitation create response')
  return response.data
}

export async function respondToInvitation(id: string, action: 'accept' | 'decline' | 'withdraw', message: string) {
  const response = action === 'withdraw'
    ? await withdrawApiV1InvitationsInvitationIdWithdrawPost(id, requestOptions())
    : await (action === 'accept' ? acceptApiV1InvitationsInvitationIdAcceptPost : declineApiV1InvitationsInvitationIdDeclinePost)(id, { message: message.trim() || null }, requestOptions())
  if (response.status !== 200) throw new Error('Unexpected invitation response')
  return response.data
}

export async function getOfferOptions(signal?: AbortSignal) {
  const company = myCompanyApiV1EmployersCompanyGet(requestOptions(signal)).then((response) => response.data).catch((error: unknown) => {
    if (isApiError(error) && error.status === 404 && error.code === 'company_not_found') return null
    throw error
  })
  const vacancies = myVacanciesApiV1EmployersVacanciesGet(requestOptions(signal)).then((response) => response.data)
  const [companyData, vacancyData] = await Promise.all([company, vacancies])
  return { company: companyData, vacancies: vacancyData.filter((vacancy) => vacancy.status !== 'closed') }
}

export async function invitationConversation(id: string, signal?: AbortSignal) {
  const response = await listConversationsApiV1ChatConversationsGet(undefined, requestOptions(signal))
  if (response.status !== 200) throw new Error('Unexpected conversations response')
  return response.data.find((conversation) => conversation.source === 'invitation' && conversation.invitation_id === id) ?? null
}

export async function candidateContacts(id: string, signal?: AbortSignal) {
  const response = await getCandidateApiV1CandidatesUserIdGet(id, requestOptions(signal))
  if (response.status !== 200) throw new Error('Unexpected candidate response')
  return response.data
}
