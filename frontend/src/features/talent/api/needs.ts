import {
  createNeedApiV1EmployersNeedsPost, getNeedApiV1EmployersNeedsNeedIdGet,
  listNeedsApiV1EmployersNeedsGet, matchesApiV1EmployersNeedsNeedIdMatchesGet,
  setNeedStatusApiV1EmployersNeedsNeedIdPatch, updateNeedApiV1EmployersNeedsNeedIdPut,
} from '@/shared/api/generated/employers/employers'
import type { NeedIn, NeedResponse, NeedStatus } from '@/shared/api/generated/employers/models'
import { ApiError } from '@/shared/api/transport/api-error'
import { requestOptions } from '@/shared/lib/request-options'
import { needMatchesSchema } from '@/features/talent/model/need-matches'
import { talentPageSize } from '@/features/talent/model/talent-search'

export const needsKey = (userId?: string) => ['talent-needs', userId] as const
export const needKey = (userId: string | undefined, needId?: string) => [...needsKey(userId), needId] as const
export const matchesKey = (userId: string | undefined, needId?: string) => ['talent-matches', userId, needId] as const

export async function listNeeds(signal?: AbortSignal) {
  const response = await listNeedsApiV1EmployersNeedsGet(requestOptions(signal))
  if (response.status !== 200) throw new Error('Unexpected needs response')
  return response.data
}

export async function getNeed(id: string, signal?: AbortSignal) {
  const response = await getNeedApiV1EmployersNeedsNeedIdGet(id, requestOptions(signal))
  if (response.status !== 200) throw new Error('Unexpected need response')
  return response.data
}

export async function saveNeed(payload: NeedIn, id?: string): Promise<NeedResponse> {
  const response = id ? await updateNeedApiV1EmployersNeedsNeedIdPut(id, payload, requestOptions()) : await createNeedApiV1EmployersNeedsPost(payload, requestOptions())
  if (response.status !== 200 && response.status !== 201) throw new Error('Unexpected need save response')
  return response.data
}

export async function setNeedStatus(id: string, status: NeedStatus) {
  const response = await setNeedStatusApiV1EmployersNeedsNeedIdPatch(id, { status }, requestOptions())
  if (response.status !== 200) throw new Error('Unexpected need status response')
  return response.data
}

export async function getNeedMatches(id: string, offset: number, hideContacted: boolean, signal?: AbortSignal) {
  const response = await matchesApiV1EmployersNeedsNeedIdMatchesGet(id, { offset, limit: talentPageSize, hide_contacted: hideContacted }, requestOptions(signal))
  if (response.status !== 200) throw new Error('Unexpected need matches response')
  const result = needMatchesSchema.safeParse(response.data)
  if (!result.success || result.data.need_id !== id) throw new ApiError({
    status: 502, code: 'invalid_matching_response', message: 'Не удалось прочитать подборку. Повторите запрос или сообщите команде о несовпадении данных.',
  })
  return result.data
}
