import { myCompanyApiV1EmployersCompanyGet, saveCompanyApiV1EmployersCompanyPut } from '@/shared/api/generated/employers/employers'
import type { CompanyIn } from '@/shared/api/generated/employers/models'
import { isApiError } from '@/shared/api/transport/api-error'
import { requestOptions } from '@/shared/lib/request-options'

export async function getCompany(signal?: AbortSignal) {
  try {
    const response = await myCompanyApiV1EmployersCompanyGet(requestOptions(signal))
    if (response.status !== 200) throw new Error('Unexpected company response')
    return response.data
  } catch (error) {
    if (isApiError(error) && error.status === 404 && error.code === 'company_not_found') return null
    throw error
  }
}

export async function saveCompany(values: CompanyIn) {
  const response = await saveCompanyApiV1EmployersCompanyPut(values, requestOptions())
  if (response.status !== 200) throw new Error('Unexpected company save response')
  return response.data
}
