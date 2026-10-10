import { myCompanyApiV1EmployersCompanyGet, saveCompanyApiV1EmployersCompanyPut } from '@/shared/api/generated/employers/employers'
import type { CompanyIn } from '@/shared/api/generated/employers/models'
import { isApiError } from '@/shared/api/transport/api-error'
import { requestOptions } from '@/shared/lib/request-options'

export async function getVacancyCompany(signal?: AbortSignal) {
  try {
    return (await myCompanyApiV1EmployersCompanyGet(requestOptions(signal))).data
  } catch (error) {
    if (isApiError(error) && error.status === 404 && error.code === 'company_not_found') return null
    throw error
  }
}

export async function createVacancyCompany(values: CompanyIn) {
  // The vacancy flow only offers setup when GET confirmed that no company exists.
  // Read again before PUT, so a company created in another tab is not blanked.
  const existing = await getVacancyCompany()
  if (existing) return existing
  const response = await saveCompanyApiV1EmployersCompanyPut(values, requestOptions())
  if (response.status !== 200) throw new Error('Unexpected company save response')
  return response.data
}
