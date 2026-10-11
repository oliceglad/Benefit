import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { searchCandidates } from '@/features/talent/api/talent'
import { talentDefaults, type TalentSearch } from '@/features/talent/model/talent-search'
import type { CandidateCard, SearchPage } from '@/shared/api/generated/talent/models'
import { session } from '@/shared/session/session'
import { TalentCatalog } from './talent-catalog'

const route = vi.hoisted(() => ({ search: {} as TalentSearch, navigate: vi.fn() }))
vi.mock('@tanstack/react-router', () => ({ useSearch: () => route.search, useNavigate: () => route.navigate }))
vi.mock('@/features/talent/api/talent', () => ({ searchCandidates: vi.fn() }))

const candidate: CandidateCard = {
  user_id: '00000000-0000-4000-8000-000000000001', full_name: 'Тестовый кандидат', headline: 'Backend',
  city: null, relocation_ready: false, job_search_status: 'active', roles: ['backend'],
  category: { specialization: 'backend', grade: 'middle', grade_status: 'confirmed', industry: null, verified_percent: 90, test_title: 'Проверка Backend' },
  skills: [], verified_skills: [{ skill: 'SQL', level: 'advanced', title: 'Продвинутый', percent: 92 }],
  experience_months: 36, work_formats: ['remote'], salary_from: 150000, salary_currency: 'RUB',
  fsp_count: 0, fsp_achievements: [], has_photo: false,
  actuality: { status: 'active', last_active_at: '2026-10-11T10:00:00Z', days_since_active: 0 },
}

describe('candidate bank refinement', () => {
  beforeEach(() => {
    vi.mocked(searchCandidates).mockReset()
    route.search = talentDefaults
    session.setAuthenticated({ id: 'employer-1', role: 'employer', email: 'employer@example.test', isEmailVerified: true })
  })

  it('keeps previous candidates visible during refinement and replaces them after the server responds', async () => {
    let finish!: (page: SearchPage) => void
    vi.mocked(searchCandidates).mockResolvedValueOnce({ total: 1, items: [candidate], categories: [] })
      .mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const content = <QueryClientProvider client={client}><TalentCatalog /></QueryClientProvider>
    const view = render(content)
    expect(await screen.findByText('Тестовый кандидат')).toBeInTheDocument()
    route.search = { ...talentDefaults, fsp: 'with' }
    view.rerender(<QueryClientProvider client={client}><TalentCatalog /></QueryClientProvider>)
    expect(await screen.findByText(/Предыдущая выдача остаётся/)).toBeInTheDocument()
    expect(screen.getByText('Тестовый кандидат')).toBeInTheDocument()
    act(() => { finish({ total: 0, items: [], categories: [] }) })
    expect(await screen.findByRole('heading', { name: 'Кандидаты не найдены' })).toBeInTheDocument()
    expect(screen.queryByText('Тестовый кандидат')).not.toBeInTheDocument()
    client.clear()
  })

  it('does not show the previous employer’s candidates after switching accounts', async () => {
    vi.mocked(searchCandidates).mockResolvedValueOnce({ total: 1, items: [candidate], categories: [] })
      .mockImplementationOnce(() => new Promise(() => {}))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><TalentCatalog /></QueryClientProvider>)
    expect(await screen.findByText('Тестовый кандидат')).toBeInTheDocument()
    act(() => { session.setAuthenticated({ id: 'employer-2', role: 'employer', email: 'another@example.test', isEmailVerified: true }) })
    expect(await screen.findByText('Ищем кандидатов…')).toBeInTheDocument()
    expect(screen.queryByText('Тестовый кандидат')).not.toBeInTheDocument()
    client.clear()
  })

  it('lets the employer retry a failed search with the same applied conditions', async () => {
    route.search = { ...talentDefaults, salary_max: 200000, experience_max: 5 }
    vi.mocked(searchCandidates).mockRejectedValueOnce(new Error('Unavailable'))
      .mockResolvedValueOnce({ total: 1, items: [candidate], categories: [] })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><TalentCatalog /></QueryClientProvider>)
    expect(await screen.findByText('Действие не выполнено')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
    expect(await screen.findByText('Тестовый кандидат')).toBeInTheDocument()
    expect(vi.mocked(searchCandidates).mock.calls[1]?.[0]).toMatchObject({ salary_max: 200000, experience_max: 5, grade_status: 'confirmed' })
    client.clear()
  })

  it('shows server-verified skill results separately in the expanded card', async () => {
    route.search = { ...talentDefaults, candidate: candidate.user_id }
    vi.mocked(searchCandidates).mockResolvedValueOnce({ total: 1, items: [candidate], categories: [] })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><TalentCatalog /></QueryClientProvider>)
    expect(await screen.findByText('SQL · Продвинутый')).toBeInTheDocument()
    expect(screen.getByText('Результат: 92%')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Навыки из профиля' })).toBeInTheDocument()
    client.clear()
  })

  it('opens older candidate responses without inventing per-skill confirmation', async () => {
    route.search = { ...talentDefaults, candidate: candidate.user_id }
    vi.mocked(searchCandidates).mockResolvedValueOnce({ total: 1, items: [{ ...candidate, verified_skills: undefined }], categories: [] })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><TalentCatalog /></QueryClientProvider>)
    expect(await screen.findByText(/Отдельные результаты проверки навыков не предоставлены/)).toBeInTheDocument()
    expect(screen.queryByText(/Подтверждены тестами:/)).not.toBeInTheDocument()
    client.clear()
  })
})
