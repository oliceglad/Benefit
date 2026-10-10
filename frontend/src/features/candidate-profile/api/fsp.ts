import { linkApiV1AuthOauthProviderLinkPost, listProvidersApiV1AuthProvidersGet } from '@/shared/api/generated/auth/auth'
import { syncFspApiV1CandidatesMeFspSyncPost } from '@/shared/api/generated/candidates/candidates'
import { requestOptions } from '@/shared/lib/request-options'

export async function fspProviders(signal?: AbortSignal) {
  return (await listProvidersApiV1AuthProvidersGet(requestOptions(signal))).data
}

export async function linkFsp() {
  const response = await linkApiV1AuthOauthProviderLinkPost('fsp_id', requestOptions())
  if (response.status !== 200) throw new Error('Unexpected FSP authorization response')
  const url = new URL(response.data.authorization_url)
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname))) throw new Error('Небезопасный адрес входа ФСП')
  return url.href
}

export async function syncFsp() {
  const response = await syncFspApiV1CandidatesMeFspSyncPost(requestOptions())
  if (response.status !== 200) throw new Error('Unexpected FSP sync response')
  return response.data
}
