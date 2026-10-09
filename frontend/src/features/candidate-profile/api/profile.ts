import {
  getDictionariesApiV1CandidatesDictionariesGet,
  getProfileApiV1CandidatesMeGet,
  grantConsentApiV1CandidatesMeConsentsPost,
  listConsentsApiV1CandidatesMeConsentsGet,
  publishApiV1CandidatesMePublishPost,
  revokeConsentApiV1CandidatesMeConsentsConsentTypeDelete,
  suggestSkillsApiV1CandidatesDictionariesSkillsGet,
  unpublishApiV1CandidatesMeUnpublishPost,
  updateProfileApiV1CandidatesMePatch,
} from '@/shared/api/generated/candidates/candidates'
import type {
  ConsentGrant,
  ConsentStatus,
  ConsentType,
  ProfileResponse,
  ProfileUpdate,
} from '@/shared/api/generated/candidates/models'
import {
  profileDictionariesSchema,
  type ProfileDictionaries,
} from '@/features/candidate-profile/model/dictionaries'

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

export async function getProfileDictionaries(signal?: AbortSignal): Promise<ProfileDictionaries> {
  const response = await getDictionariesApiV1CandidatesDictionariesGet({ signal })
  return profileDictionariesSchema.parse(response.data)
}

export async function searchProfileSkills(query: string, signal?: AbortSignal): Promise<string[]> {
  const response = await suggestSkillsApiV1CandidatesDictionariesSkillsGet(
    { q: query, limit: 12 },
    { signal },
  )
  if (response.status !== 200) throw new Error('Skill search returned an unexpected status')
  return response.data
}

export async function getCandidateConsents(signal?: AbortSignal): Promise<ConsentStatus[]> {
  const response = await listConsentsApiV1CandidatesMeConsentsGet({ signal })
  return response.data
}

export async function grantCandidateConsent(grant: ConsentGrant): Promise<ConsentStatus[]> {
  const response = await grantConsentApiV1CandidatesMeConsentsPost(grant)
  if (response.status !== 200) throw new Error('Grant consent returned an unexpected status')
  return response.data
}

export async function revokeCandidateConsent(type: ConsentType): Promise<ConsentStatus[]> {
  const response = await revokeConsentApiV1CandidatesMeConsentsConsentTypeDelete(type)
  if (response.status !== 200) throw new Error('Revoke consent returned an unexpected status')
  return response.data
}

export async function publishCandidateProfile(): Promise<ProfileResponse> {
  const response = await publishApiV1CandidatesMePublishPost()
  return response.data
}

export async function unpublishCandidateProfile(): Promise<ProfileResponse> {
  const response = await unpublishApiV1CandidatesMeUnpublishPost()
  return response.data
}

export const candidateProfileQueryKey = ['candidate', 'profile'] as const
export const profileDictionariesQueryKey = ['candidate', 'profile-dictionaries'] as const
export const candidateConsentsQueryKey = ['candidate', 'consents'] as const
