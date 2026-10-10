import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { candidateConsentsQueryKey, candidateProfileQueryKey, getCandidateProfile } from '@/features/candidate-profile/api/profile'
import { buildJuryStepUpdate } from '@/features/candidate-profile/model/jury-demo-data'
import type { ProfileSectionId } from '@/features/candidate-profile/model/profile-sections'
import { JuryStepTools } from '@/features/candidate-profile/ui/jury-step-tools'
import { PersonalForm } from '@/features/candidate-profile/ui/personal-form'
import type { ProfileUpdate } from '@/shared/api/generated/candidates/models'
import { createTestProfile } from '@/test/fixtures/candidate'
import { server } from '@/test/server'

const fillLabel = 'Заполнить шаг тестовыми данными'
const initialProfile = createTestProfile({ verified_grade: 'senior', verified_specialization: 'backend', has_photo: true })

beforeEach(() => vi.stubEnv('DEV', true))
afterEach(() => vi.unstubAllEnvs())

function renderTools(section: ProfileSectionId, dirty = false, onPendingChange = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  client.setQueryData(candidateProfileQueryKey, initialProfile)
  const view = render(
    <QueryClientProvider client={client}>
      <JuryStepTools section={section} completed={false} dirty={dirty} onPendingChange={onPendingChange} />
    </QueryClientProvider>,
  )
  return { client, ...view }
}

describe('JuryStepTools', () => {
  it.each<[ProfileSectionId, string[]]>([
    ['personal', ['last_name', 'first_name', 'middle_name', 'birth_date', 'city', 'relocation_ready']],
    ['contacts', ['contact_email', 'phone', 'telegram']],
    ['specialization', ['headline', 'about', 'grade', 'roles']],
    ['skills', ['skills', 'soft_skills', 'languages']],
    ['experience', ['experience', 'education', 'courses', 'projects']],
    ['preferences', ['salary_from', 'salary_currency', 'employment_types', 'work_formats', 'job_search_status']],
  ])('saves only the %s step without changing protected profile data', async (section, allowedKeys) => {
    const requests: ProfileUpdate[] = []
    server.use(http.patch('*/api/v1/candidates/me', async ({ request }) => {
      expect(request.credentials).toBe('same-origin')
      const update = await request.json() as ProfileUpdate
      requests.push(update)
      return HttpResponse.json({ ...initialProfile, ...update })
    }))
    const { client } = renderTools(section)
    await userEvent.click(screen.getByRole('button', { name: fillLabel }))

    expect(await screen.findByRole('status')).toHaveTextContent('Текущий шаг заполнен тестовыми данными и сохранён.')
    expect(requests).toHaveLength(1)
    expect(Object.keys(requests[0]).sort()).toEqual(allowedKeys.sort())
    expect(client.getQueryData(candidateProfileQueryKey)).toMatchObject({
      verified_grade: 'senior', verified_specialization: 'backend', has_photo: true,
      status: initialProfile.status, privacy: initialProfile.privacy, fsp: initialProfile.fsp,
    })
  })

  it('keeps unsaved input safe by disabling the fill action', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch')
    renderTools('contacts', true)
    expect(screen.getByText('Сначала сохраните введённые изменения.')).toBeVisible()
    const button = screen.getByRole('button', { name: fillLabel })
    expect(button).toBeDisabled()
    await userEvent.click(button)
    expect(fetch).not.toHaveBeenCalled()
    fetch.mockRestore()
  })

  it('waits for the server, blocks repeated clicks and updates a clean form from the saved profile', async () => {
    let respond!: () => void
    const responseReady = new Promise<void>((resolve) => { respond = resolve })
    server.use(http.patch('*/api/v1/candidates/me', async ({ request }) => {
      const update = await request.json() as ProfileUpdate
      await responseReady
      return HttpResponse.json({ ...initialProfile, ...update })
    }))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    client.setQueryData(candidateProfileQueryKey, initialProfile)
    const pending = vi.fn()
    function ProfileWithTools() {
      const { data } = useQuery({ queryKey: candidateProfileQueryKey, queryFn: ({ signal }) => getCandidateProfile(signal), staleTime: Infinity })
      return <><JuryStepTools section="personal" completed={data!.completeness.onboarding_completed} dirty={false} onPendingChange={pending} /><PersonalForm profile={data!} onContinue={() => undefined} /></>
    }
    render(<QueryClientProvider client={client}><ProfileWithTools /></QueryClientProvider>)
    await userEvent.click(screen.getByRole('button', { name: fillLabel }))
    expect(screen.getByRole('button', { name: 'Заполняем…' })).toBeDisabled()
    expect(screen.queryByText('Текущий шаг заполнен тестовыми данными и сохранён.')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Фамилия')).toHaveValue('Иванов')
    expect(pending).toHaveBeenCalledWith(true)
    respond()
    await waitFor(() => expect(screen.getByLabelText('Фамилия')).toHaveValue('Тестов'))
    expect(pending).toHaveBeenLastCalledWith(false)
  })

  it('checks readiness with GET only and reports missing consents without accepting or publishing', async () => {
    const methods: string[] = []
    const consents = [{ type: 'personal_data', granted: false }]
    server.use(http.all('*/api/v1/candidates/*', ({ request }) => {
      methods.push(request.method)
      return request.url.endsWith('/consents') ? HttpResponse.json(consents) : HttpResponse.json(createTestProfile({
        completeness: { ...initialProfile.completeness, can_publish: false, missing_required: ['consents'] },
      }))
    }))
    const { client } = renderTools('consents')
    await userEvent.click(screen.getByRole('button', { name: 'Проверить готовность' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Осталось заполнить: Действующие согласия.')
    expect(methods).toEqual(['GET', 'GET'])
    expect(client.getQueryData(candidateConsentsQueryKey)).toEqual(consents)
    expect(client.getQueryData(candidateProfileQueryKey)).toMatchObject({ status: 'draft' })
  })

  it('retains the cached profile on failure and allows an explicit retry', async () => {
    let attempts = 0
    server.use(http.patch('*/api/v1/candidates/me', async ({ request }) => {
      attempts += 1
      if (attempts === 1) return HttpResponse.json({ error: { code: 'temporarily_unavailable', message: 'Сервис временно недоступен' } }, { status: 503 })
      return HttpResponse.json({ ...initialProfile, ...await request.json() as ProfileUpdate })
    }))
    const { client } = renderTools('personal')
    await userEvent.click(screen.getByRole('button', { name: fillLabel }))
    expect(await screen.findByRole('alert')).toBeVisible()
    expect(attempts).toBe(1)
    expect(client.getQueryData(candidateProfileQueryKey)).toEqual(initialProfile)
    await userEvent.click(screen.getByRole('button', { name: fillLabel }))
    expect(await screen.findByRole('status')).toHaveTextContent('сохранён')
    expect(attempts).toBe(2)
  })

  it('reports newly missing requirements even for a previously published profile', async () => {
    server.use(
      http.get('*/api/v1/candidates/me', () => HttpResponse.json(createTestProfile({
        status: 'published', completeness: { ...initialProfile.completeness, missing_required: ['consents'] },
      }))),
      http.get('*/api/v1/candidates/me/consents', () => HttpResponse.json([])),
    )
    renderTools('consents')
    await userEvent.click(screen.getByRole('button', { name: 'Проверить готовность' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Действующие согласия')
    expect(screen.queryByText('Профиль опубликован.')).not.toBeInTheDocument()
  })

  it('is hidden in a standard production build and enabled by the jury flag', () => {
    vi.stubEnv('DEV', false)
    vi.stubEnv('VITE_ENABLE_JURY_TOOLS', 'false')
    const { rerender, client } = renderTools('personal')
    expect(screen.queryByRole('complementary', { name: 'Инструменты жюри' })).not.toBeInTheDocument()
    vi.stubEnv('VITE_ENABLE_JURY_TOOLS', 'true')
    rerender(<QueryClientProvider client={client}><JuryStepTools section="personal" completed={false} dirty={false} onPendingChange={() => undefined} /></QueryClientProvider>)
    expect(screen.getByRole('button', { name: fillLabel })).toBeEnabled()
  })

  it('returns fresh fixture arrays and no update for the consent step', () => {
    const update = buildJuryStepUpdate('skills')!
    update.skills!.length = 0
    expect(buildJuryStepUpdate('skills')?.skills).toHaveLength(3)
    expect(buildJuryStepUpdate('consents')).toBeNull()
  })

  it('hides jury tools as soon as onboarding is complete, including in a jury build', () => {
    vi.stubEnv('VITE_ENABLE_JURY_TOOLS', 'true')
    const { client, rerender } = renderTools('personal')
    expect(screen.getByRole('button', { name: fillLabel })).toBeVisible()
    rerender(<QueryClientProvider client={client}><JuryStepTools section="personal" completed dirty={false} onPendingChange={() => undefined} /></QueryClientProvider>)
    expect(screen.queryByRole('complementary', { name: 'Инструменты жюри' })).not.toBeInTheDocument()
    rerender(<QueryClientProvider client={client}><JuryStepTools section="consents" completed dirty={false} onPendingChange={() => undefined} /></QueryClientProvider>)
    expect(screen.queryByRole('button', { name: 'Проверить готовность' })).not.toBeInTheDocument()
  })
})
