import {
  myCompanyApiV1EmployersCompanyGet,
  saveCompanyApiV1EmployersCompanyPut,
} from '@/shared/api/generated/employers/employers'
import type {
  CompanyIn,
  CompanyResponse,
} from '@/shared/api/generated/employers/models'
import { isApiError } from '@/shared/api/transport/api-error'
import { requestOptions } from '@/shared/lib/request-options'

export function employerCompanyQueryKey(accountId: string) {
  return ['employer', accountId, 'company'] as const
}

export async function getEmployerCompany(
  signal?: AbortSignal,
): Promise<CompanyResponse | null> {
  try {
    return (await myCompanyApiV1EmployersCompanyGet(requestOptions(signal))).data
  } catch (error) {
    if (
      isApiError(error)
      && error.status === 404
      && error.code === 'company_not_found'
    ) {
      return null
    }
    throw error
  }
}

export async function saveEmployerCompany(
  company: CompanyIn,
): Promise<CompanyResponse> {
  const response = await saveCompanyApiV1EmployersCompanyPut(
    company,
    requestOptions(),
  )
  if (response.status !== 200) {
    throw new Error('Company save returned an unexpected status')
  }
  return response.data
}
