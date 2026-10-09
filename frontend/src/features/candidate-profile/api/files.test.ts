import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  deleteCandidatePhoto,
  downloadCandidateResume,
  getCandidatePhoto,
  inspectCandidateResume,
  uploadCandidatePhoto,
} from './files'
import { server } from '@/test/server'

afterEach(() => vi.restoreAllMocks())

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  return input instanceof URL ? input.href : input.url
}

describe('candidate profile files API', () => {
  it('loads, uploads and deletes a private photo through the authenticated transport', async () => {
    const calls: string[] = []
    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const method = init?.method ?? 'GET'
      expect(init?.credentials).toBe('include')
      if (method === 'GET') {
        calls.push('get')
        return Promise.resolve(new Response(new Uint8Array([255, 216, 255, 217]), {
          headers: { 'Content-Type': 'image/jpeg' },
        }))
      }
      if (method === 'PUT') {
        calls.push('put')
        const form = init?.body
        expect(form).toBeInstanceOf(FormData)
        if (!(form instanceof FormData)) throw new Error('Expected multipart form data')
        const file = form.get('file')
        expect(file).toBeInstanceOf(File)
        expect((file as File).name).toBe('candidate.png')
        return Promise.resolve(new Response(null, { status: 204 }))
      }
      if (method === 'DELETE') {
        calls.push('delete')
        return Promise.resolve(new Response(null, { status: 204 }))
      }
      throw new Error(`Unexpected request: ${requestUrl(input)}`)
    })

    const photo = await getCandidatePhoto()
    await uploadCandidatePhoto(new File(['image'], 'candidate.png', { type: 'image/png' }))
    await deleteCandidatePhoto()

    expect(photo.type).toBe('image/jpeg')
    expect(calls).toEqual(['get', 'put', 'delete'])
  })

  it('previews a resume without applying it', async () => {
    const modes: string[] = []
    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const apply = new URL(requestUrl(input)).searchParams.get('apply') ?? 'false'
      modes.push(apply)
      const form = init?.body
      expect(form).toBeInstanceOf(FormData)
      if (!(form instanceof FormData)) throw new Error('Expected multipart form data')
      expect((form.get('file') as File).name).toBe('resume.pdf')
      return Promise.resolve(new Response(JSON.stringify({
          draft: { headline: 'Frontend-разработчик' },
          warnings: [],
          applied: apply === 'true',
          applied_fields: apply === 'true' ? ['headline'] : [],
      }), { headers: { 'Content-Type': 'application/json' } }))
    })
    const file = new File(['%PDF-1.7'], 'resume.pdf', { type: 'application/pdf' })

    const preview = await inspectCandidateResume(file)
    expect(preview.applied).toBe(false)
    expect(modes).toEqual(['false'])

    expect(modes).toEqual(['false'])
  })

  it('keeps only exact skills from the server catalog in the preview', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = new URL(requestUrl(input))
      if (url.pathname.endsWith('/dictionaries/skills')) {
        const query = url.searchParams.get('q')
        const suggestions = query === 'React' ? ['React', 'React Native'] : []
        return Promise.resolve(new Response(JSON.stringify(suggestions), { headers: { 'Content-Type': 'application/json' } }))
      }
      return Promise.resolve(new Response(JSON.stringify({
        draft: { skills: [{ name: 'React' }, { name: 'проекта:' }, { name: '•' }] },
        warnings: [],
        applied: false,
        applied_fields: [],
      }), { headers: { 'Content-Type': 'application/json' } }))
    })

    const preview = await inspectCandidateResume(new File(['%PDF'], 'resume.pdf', { type: 'application/pdf' }))

    expect(preview.draft.skills).toEqual([{ name: 'React' }])
    expect(preview.warnings).toContain('Пропущены значения вне каталога навыков: проекта:, •')
  })

  it('bounds catalog lookups when the parser returns many fragments', async () => {
    let catalogRequests = 0
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = new URL(requestUrl(input))
      if (url.pathname.endsWith('/dictionaries/skills')) {
        catalogRequests += 1
        return Promise.resolve(new Response('[]', { headers: { 'Content-Type': 'application/json' } }))
      }
      return Promise.resolve(new Response(JSON.stringify({
        draft: {
          skills: Array.from({ length: 30 }, (_, index) => ({ name: `Technology ${index}` })),
        },
        warnings: [],
        applied: false,
        applied_fields: [],
      }), { headers: { 'Content-Type': 'application/json' } }))
    })

    const preview = await inspectCandidateResume(new File(['%PDF'], 'resume.pdf', { type: 'application/pdf' }))

    expect(catalogRequests).toBe(12)
    expect(preview.draft.skills).toBeUndefined()
    expect(preview.warnings[0]).toContain('и ещё 25')
  })

  it('keeps the PDF preview usable when catalog validation is rate limited', async () => {
    let catalogRequests = 0
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = new URL(requestUrl(input))
      if (url.pathname.endsWith('/dictionaries/skills')) {
        catalogRequests += 1
        return Promise.resolve(new Response(JSON.stringify({
          error: { code: 'rate_limited', message: 'Слишком много запросов' },
        }), { status: 429, headers: { 'Content-Type': 'application/json', 'Retry-After': '60' } }))
      }
      return Promise.resolve(new Response(JSON.stringify({
        draft: { skills: [{ name: 'React' }, { name: 'TypeScript' }, { name: 'Vite' }] },
        warnings: [],
        applied: false,
        applied_fields: [],
      }), { headers: { 'Content-Type': 'application/json' } }))
    })

    const preview = await inspectCandidateResume(new File(['%PDF'], 'resume.pdf', { type: 'application/pdf' }))

    expect(catalogRequests).toBe(2)
    expect(preview.draft.skills).toBeUndefined()
    expect(preview.warnings).toContain('Часть навыков не удалось проверить по каталогу. Их можно добавить вручную.')
  })

  it('downloads a real PDF with the server filename and never accepts a JSON error as a file', async () => {
    server.use(
      http.get('*/api/v1/candidates/me/resume.pdf', () => new HttpResponse('%PDF-1.7\ncontent', {
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': "attachment; filename=resume.pdf; filename*=UTF-8''resume-%D0%98%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2.pdf",
        },
      })),
    )

    const downloaded = await downloadCandidateResume()
    expect(downloaded.filename).toBe('resume-Иванов.pdf')
    expect(await downloaded.blob.text()).toContain('%PDF-1.7')

    server.use(
      http.get('*/api/v1/candidates/me/resume.pdf', () => HttpResponse.json({
        error: { code: 'resume_unavailable', message: 'Резюме недоступно' },
      }, { status: 422 })),
    )
    await expect(downloadCandidateResume()).rejects.toMatchObject({
      code: 'resume_unavailable',
      message: 'Резюме недоступно',
    })
  })
})
