import {
  getMyVacancyApiV1EmployersVacanciesVacancyIdGet, getVacancyApiV1VacanciesVacancyIdGet,
  listVacanciesApiV1VacanciesGet, myVacanciesApiV1EmployersVacanciesGet,
  createVacancyApiV1EmployersVacanciesPost, updateVacancyApiV1EmployersVacanciesVacancyIdPut,
  setVacancyStatusApiV1EmployersVacanciesVacancyIdPatch,
} from '@/shared/api/generated/employers/employers'
import { applyApiV1ApplicationsPost, myApplicationsApiV1ApplicationsGet } from '@/shared/api/generated/applications/applications'
import type { ListVacanciesApiV1VacanciesGetParams, VacancyIn, VacancyStatus } from '@/shared/api/generated/employers/models'
import { requestOptions } from '@/shared/lib/request-options'

export async function listVacancies(params: ListVacanciesApiV1VacanciesGetParams, signal?: AbortSignal) {
  const response = await listVacanciesApiV1VacanciesGet(params, requestOptions(signal))
  if (response.status !== 200) throw new Error('Unexpected vacancy catalog response')
  return response.data
}
export async function listOwnVacancies(signal?: AbortSignal) {
  return (await myVacanciesApiV1EmployersVacanciesGet(requestOptions(signal))).data
}
export async function getVacancy(id: string, employer: boolean, signal?: AbortSignal) {
  const request = employer ? getMyVacancyApiV1EmployersVacanciesVacancyIdGet : getVacancyApiV1VacanciesVacancyIdGet
  const response = await request(id, requestOptions(signal))
  if (response.status !== 200) throw new Error('Unexpected vacancy response')
  return response.data
}
export async function myApplications(signal?: AbortSignal) {
  return (await myApplicationsApiV1ApplicationsGet(requestOptions(signal))).data
}
export async function applyForVacancy(id: string, coverLetter: string) {
  const response = await applyApiV1ApplicationsPost({ vacancy_id: id, cover_letter: coverLetter.trim() || null }, requestOptions())
  if (response.status !== 201) throw new Error('Unexpected application response')
  return response.data
}

export async function saveVacancy(values: VacancyIn, id?: string) {
  const response = id
    ? await updateVacancyApiV1EmployersVacanciesVacancyIdPut(id, values, requestOptions())
    : await createVacancyApiV1EmployersVacanciesPost(values, requestOptions())
  if (response.status !== 200 && response.status !== 201) throw new Error('Unexpected vacancy save response')
  return response.data
}

export async function changeVacancyStatus(id: string, status: VacancyStatus) {
  const response = await setVacancyStatusApiV1EmployersVacanciesVacancyIdPatch(id, { status }, requestOptions())
  if (response.status !== 200) throw new Error('Unexpected vacancy status response')
  return response.data
}
