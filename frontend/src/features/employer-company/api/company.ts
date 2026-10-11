import {
  deleteCompanyLogoApiV1EmployersCompanyLogoDelete,
  getGetCompanyLogoApiV1EmployersCompanyLogoGetUrl,
  myCompanyApiV1EmployersCompanyGet,
  saveCompanyApiV1EmployersCompanyPut,
  uploadCompanyLogoApiV1EmployersCompanyLogoPut,
} from '@/shared/api/generated/employers/employers'
import type {
  CompanyIn,
  CompanyResponse,
} from '@/shared/api/generated/employers/models'
import { isApiError } from '@/shared/api/transport/api-error'
import { orvalFetch } from '@/shared/api/transport/orval-fetch'
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

type BinaryResponse = { data: Blob; status: number; headers: Headers }

export const employerCompanyLogoQueryKey = (companyId: string) => (
  ['employer', 'company', companyId, 'logo'] as const
)

export async function getEmployerCompanyLogo(signal?: AbortSignal): Promise<Blob> {
  const response = await orvalFetch<BinaryResponse>(getGetCompanyLogoApiV1EmployersCompanyLogoGetUrl(), {
    method: 'GET',
    signal,
    responseType: 'blob',
  })
  if (!response.data.type.startsWith('image/')) throw new Error('Сервер вернул файл в неожиданном формате')
  return response.data
}

export async function uploadEmployerCompanyLogo(file: File): Promise<void> {
  const response = await uploadCompanyLogoApiV1EmployersCompanyLogoPut({ file })
  if (response.status !== 204) throw new Error('Логотип не был сохранён')
}

export async function deleteEmployerCompanyLogo(): Promise<void> {
  const response = await deleteCompanyLogoApiV1EmployersCompanyLogoDelete()
  if (response.status !== 204) throw new Error('Логотип не был удалён')
}
