import {
  getProfileApiV1CandidatesMeGet,
  updateProfileApiV1CandidatesMePatch,
} from '@/shared/api/generated/candidates/candidates'
import type {
  ProfileResponse,
  ProfileUpdate,
} from '@/shared/api/generated/candidates/models'

export async function getCandidateProfile(signal?: AbortSignal): Promise<ProfileResponse> {
  const response = await getProfileApiV1CandidatesMeGet({ signal })
  return response.data
}

export async function updateCandidateProfile(update: ProfileUpdate): Promise<ProfileResponse> {
  const response = await updateProfileApiV1CandidatesMePatch(update)
  if (response.status !== 200) {
    throw new Error('Candidate profile update returned an unexpected status')
  }
  return response.data
}

export const candidateProfileQueryKey = ['candidate', 'profile'] as const
