import { searchCandidatesApiV1TalentCandidatesGet } from '@/shared/api/generated/talent/talent'
import type { SearchCandidatesApiV1TalentCandidatesGetParams } from '@/shared/api/generated/talent/models'
import { requestOptions } from '@/shared/lib/request-options'

export async function searchCandidates(params: SearchCandidatesApiV1TalentCandidatesGetParams, signal?: AbortSignal) {
  const response = await searchCandidatesApiV1TalentCandidatesGet(params, requestOptions(signal))
  if (response.status !== 200) throw new Error('Unexpected candidate search response')
  return response.data
}
