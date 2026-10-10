import {
  deletePhotoApiV1CandidatesMePhotoDelete,
  getExportResumeApiV1CandidatesMeResumePdfGetUrl,
  getGetPhotoApiV1CandidatesMePhotoGetUrl,
  importResumeApiV1CandidatesMeResumeImportPost,
  uploadPhotoApiV1CandidatesMePhotoPut,
} from '@/shared/api/generated/candidates/candidates'
import type { ResumeImportResponse } from '@/shared/api/generated/candidates/models'
import { orvalFetch } from '@/shared/api/transport/orval-fetch'
import { searchProfileSkills } from './profile'

const MAX_RESUME_SKILL_LOOKUPS = 12
const RESUME_SKILL_LOOKUP_CONCURRENCY = 2
const proseWords = new Set([
  'для',
  'инструмент',
  'инструменты',
  'использовал',
  'использовала',
  'проект',
  'проекта',
  'проекте',
  'разработка',
  'разработке',
])

type BinaryResponse = {
  data: Blob
  status: number
  headers: Headers
}

export type ResumeDownload = {
  blob: Blob
  filename: string
}

function filenameFromDisposition(disposition: string | null): string {
  if (!disposition) return 'resume.pdf'
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(disposition)?.[1]
  if (encoded) {
    try {
      return decodeURIComponent(encoded)
    } catch {
      return 'resume.pdf'
    }
  }
  return /filename="?([^";]+)"?/i.exec(disposition)?.[1] ?? 'resume.pdf'
}

// Duck typing instead of instanceof: the fetch Blob and the environment Blob
// (e.g. jsdom in tests) can be different classes.
function isBlob(value: unknown): value is Blob {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as Blob).arrayBuffer === 'function' &&
    typeof (value as Blob).type === 'string'
  )
}

function requireBlob(response: BinaryResponse, expectedType: string): Blob {
  if (!isBlob(response.data) || !response.data.type.includes(expectedType)) {
    throw new Error('Сервер вернул файл в неожиданном формате')
  }
  return response.data
}

export async function getCandidatePhoto(signal?: AbortSignal): Promise<Blob> {
  const response = await orvalFetch<BinaryResponse>(getGetPhotoApiV1CandidatesMePhotoGetUrl(), {
    method: 'GET',
    signal,
  })
  return requireBlob(response, 'image/')
}

export async function uploadCandidatePhoto(file: File): Promise<void> {
  const response = await uploadPhotoApiV1CandidatesMePhotoPut({ file })
  if (response.status !== 204) throw new Error('Фото не было сохранено')
}

export async function deleteCandidatePhoto(): Promise<void> {
  const response = await deletePhotoApiV1CandidatesMePhotoDelete()
  if (response.status !== 204) throw new Error('Фото не было удалено')
}

export async function inspectCandidateResume(file: File): Promise<ResumeImportResponse> {
  const response = await importResumeApiV1CandidatesMeResumeImportPost({ file })
  if (response.status !== 200) throw new Error('Резюме не было обработано')
  return validateRecognizedSkills(response.data)
}

export async function downloadCandidateResume(signal?: AbortSignal): Promise<ResumeDownload> {
  const response = await orvalFetch<BinaryResponse>(getExportResumeApiV1CandidatesMeResumePdfGetUrl(), {
    method: 'GET',
    signal,
  })
  const blob = requireBlob(response, 'application/pdf')
  const signature = new TextDecoder().decode(await blob.slice(0, 4).arrayBuffer())
  if (signature !== '%PDF') throw new Error('Сервер вернул повреждённый PDF')
  return {
    blob,
    filename: filenameFromDisposition(response.headers.get('Content-Disposition')),
  }
}

export const candidatePhotoQueryKey = (userId: string) => ['candidate', userId, 'photo'] as const

function skillName(value: unknown): string | null {
  return value && typeof value === 'object' && 'name' in value && typeof value.name === 'string'
    ? value.name.trim()
    : null
}

function isPlausibleSkillName(name: string): boolean {
  if (name.length > 64 || !/[\p{L}\p{N}]/u.test(name)) return false
  if (!/^[\p{L}\p{N}+#./ -]+$/u.test(name)) return false
  const words = name.toLocaleLowerCase('ru-RU').split(/\s+/)
  return words.length <= 4 && !words.some((word) => proseWords.has(word))
}

async function validateRecognizedSkills(result: ResumeImportResponse): Promise<ResumeImportResponse> {
  const rawSkills = result.draft.skills
  if (!Array.isArray(rawSkills)) return result
  const skillValues: unknown[] = rawSkills
  const candidates: Array<{ value: unknown; name: string }> = skillValues
    .map((value) => ({ value, name: skillName(value) ?? '' }))
    .filter(({ name }) => name.length > 0)
  const uniqueCandidates = candidates.filter((candidate, index, all) =>
    all.findIndex(({ name }) => name.toLocaleLowerCase('ru-RU') === candidate.name.toLocaleLowerCase('ru-RU')) === index)
  const plausible = uniqueCandidates.filter(({ name }) => isPlausibleSkillName(name))
  const queued = plausible.slice(0, MAX_RESUME_SKILL_LOOKUPS)
  const valid: unknown[] = []
  const rejected = uniqueCandidates
    .filter((candidate) => !queued.includes(candidate))
    .map(({ name }) => name)
  let catalogUnavailable = false

  for (let index = 0; index < queued.length; index += RESUME_SKILL_LOOKUP_CONCURRENCY) {
    const batch = queued.slice(index, index + RESUME_SKILL_LOOKUP_CONCURRENCY)
    const checked = await Promise.all(batch.map(async (candidate) => {
      try {
        const suggestions = await searchProfileSkills(candidate.name)
        const canonical = suggestions.find((name) => name.toLocaleLowerCase('ru-RU') === candidate.name.toLocaleLowerCase('ru-RU'))
        return { ...candidate, canonical }
      } catch {
        catalogUnavailable = true
        return { ...candidate, canonical: undefined }
      }
    }))
    checked.forEach(({ value, name, canonical }) => {
      if (!canonical) {
        rejected.push(name)
        return
      }
      valid.push(value && typeof value === 'object' ? { ...value, name: canonical } : value)
    })
    if (catalogUnavailable) {
      rejected.push(...queued
        .slice(index + RESUME_SKILL_LOOKUP_CONCURRENCY)
        .map(({ name }) => name))
      break
    }
  }

  const draft = { ...result.draft }
  if (valid.length > 0) draft.skills = valid
  else delete draft.skills
  const rejectedPreview = rejected.slice(0, 5).join(', ')
  const rejectedSuffix = rejected.length > 5 ? ` и ещё ${rejected.length - 5}` : ''
  const warnings = [...result.warnings]
  if (rejected.length > 0) {
    warnings.push(`Пропущены значения вне каталога навыков: ${rejectedPreview}${rejectedSuffix}`)
  }
  if (catalogUnavailable) {
    warnings.push('Часть навыков не удалось проверить по каталогу. Их можно добавить вручную.')
  }
  return {
    ...result,
    draft,
    warnings,
  }
}
