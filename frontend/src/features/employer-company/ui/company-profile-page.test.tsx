import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  Outlet,
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from '@tanstack/react-router'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { CompanyProfilePage } from '@/features/employer-company/ui/company-profile-page'
import type { CompanyResponse } from '@/shared/api/generated/employers/models'
import { session } from '@/shared/session/session'
import { server } from '@/test/server'

const company: CompanyResponse = {
  id: 'company-1',
  owner_id: 'employer-1',
  name: 'Benefit',
  legal_name: 'ООО Бенефит',
  inn: '7707083893',
  industry: 'ai',
  description: 'Платформа найма',
  website: 'https://benefit.example',
  city: 'Самара',
  size: '11-50',
  tech_stack: ['TypeScript', 'Python'],
  contact_name: 'Анна Иванова',
  contact_email: 'hr@benefit.example',
  contact_phone: '+70000000000',
  telegram: '@benefit_hr',
  created_at: '2026-10-11T10:00:00Z',
  updated_at: '2026-10-11T10:00:00Z',
}

async function renderPage() {
  session.setAuthenticated({
    id: 'employer-1',
    email: 'employer@example.ru',
    role: 'employer',
    isEmailVerified: true,
  })
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const rootRoute = createRootRoute({
    component: () => <QueryClientProvider client={client}><Outlet /></QueryClientProvider>,
  })
  const companyRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/company',
    component: CompanyProfilePage,
  })
  const otherRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/vacancies',
    component: () => <p>Другой экран</p>,
  })
  const router = createRouter({
    routeTree: rootRoute.addChildren([companyRoute, otherRoute]),
    history: createMemoryHistory({ initialEntries: ['/company'] }),
  })
  await router.load()
  render(<RouterProvider router={router} />)
  return { client, router }
}

describe('employer company profile', () => {
  it('loads every field, sends a full PUT and resets from the server response', async () => {
    let payload: Record<string, unknown> | undefined
    server.use(
      http.get('*/api/v1/employers/company', () => HttpResponse.json(company)),
      http.put('*/api/v1/employers/company', async ({ request }) => {
        payload = await request.json() as Record<string, unknown>
        return HttpResponse.json({
          ...company,
          ...payload,
          name: 'Benefit — подтверждено сервером',
          updated_at: '2026-10-11T11:00:00Z',
        })
      }),
    )
    await renderPage()
    const user = userEvent.setup()

    const name = await screen.findByLabelText(/Название компании/)
    expect(name).toHaveValue('Benefit')
    expect(screen.getByLabelText('Telegram')).toHaveValue('@benefit_hr')
    await user.clear(name)
    await user.type(name, 'Benefit new')
    await user.click(screen.getByRole('button', { name: 'Сохранить изменения' }))

    await waitFor(() => expect(name).toHaveValue('Benefit — подтверждено сервером'))
    expect(payload).toMatchObject({
      name: 'Benefit new',
      legal_name: 'ООО Бенефит',
      inn: '7707083893',
      industry: 'ai',
      description: 'Платформа найма',
      size: '11-50',
      tech_stack: ['TypeScript', 'Python'],
      contact_email: 'hr@benefit.example',
      telegram: '@benefit_hr',
    })
    expect(screen.getByText('Все изменения сохранены')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Сохранить изменения' })).toBeDisabled()
  })

  it('keeps input after 422 and maps a server issue to its field', async () => {
    server.use(
      http.get('*/api/v1/employers/company', () => HttpResponse.json(company)),
      http.put('*/api/v1/employers/company', () => HttpResponse.json({
        error: {
          code: 'validation_error',
          message: 'Проверьте данные: inn',
          details: [{ field: 'inn', message: 'ИНН не прошёл проверку контрольной суммы' }],
        },
      }, { status: 422 })),
    )
    await renderPage()
    const user = userEvent.setup()

    const name = await screen.findByLabelText(/Название компании/)
    await user.clear(name)
    await user.type(name, 'Несохранённое название')
    await user.click(screen.getByRole('button', { name: 'Сохранить изменения' }))

    expect(await screen.findByText('ИНН не прошёл проверку контрольной суммы')).toBeVisible()
    expect(name).toHaveValue('Несохранённое название')
    expect(screen.getByText('Проверьте поля формы')).toBeVisible()
  })

  it('treats 404 as creation and protects dirty input during navigation', async () => {
    server.use(
      http.get('*/api/v1/employers/company', () => HttpResponse.json({
        error: { code: 'company_not_found', message: 'Профиль компании не заполнен' },
      }, { status: 404 })),
    )
    const { router } = await renderPage()
    const user = userEvent.setup()
    const name = await screen.findByLabelText(/Название компании/)

    expect(screen.getByText('Профиль компании ещё не заполнен')).toBeVisible()
    await user.type(name, 'Новая компания')
    void router.navigate({ to: '/vacancies', search: { offset: 0 } })
    expect(await screen.findByRole('alertdialog')).toHaveTextContent('Есть несохранённые изменения')

    await user.click(screen.getByRole('button', { name: 'Остаться' }))
    expect(router.state.location.pathname).toBe('/company')
    expect(name).toHaveValue('Новая компания')

    void router.navigate({ to: '/vacancies', search: { offset: 0 } })
    await user.click(await screen.findByRole('button', { name: 'Не сохранять' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/vacancies'))
  })

  it('shows a truthful forbidden state without retrying the request', async () => {
    let calls = 0
    server.use(http.get('*/api/v1/employers/company', () => {
      calls += 1
      return HttpResponse.json({
        error: { code: 'forbidden', message: 'Недостаточно прав' },
      }, { status: 403 })
    }))
    await renderPage()

    expect(await screen.findByText('Этот раздел доступен только аккаунту работодателя.')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Повторить' })).not.toBeInTheDocument()
    expect(calls).toBe(1)
  })

  it('blocks repeated submission while creation is pending', async () => {
    let calls = 0
    let resolveRequest!: () => void
    const requestReady = new Promise<void>((resolve) => { resolveRequest = resolve })
    server.use(
      http.get('*/api/v1/employers/company', () => HttpResponse.json({
        error: { code: 'company_not_found', message: 'Профиль компании не заполнен' },
      }, { status: 404 })),
      http.put('*/api/v1/employers/company', async ({ request }) => {
        calls += 1
        const payload = await request.json() as Record<string, unknown>
        await requestReady
        return HttpResponse.json({
          ...company,
          ...payload,
          updated_at: '2026-10-11T12:00:00Z',
        })
      }),
    )
    await renderPage()
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/Название компании/), 'Новая компания')
    await user.type(screen.getByLabelText(/Описание/), 'Описание компании')
    const submit = screen.getByRole('button', { name: 'Создать компанию' })

    await user.dblClick(submit)
    await waitFor(() => expect(calls).toBe(1))
    expect(submit).toBeDisabled()
    resolveRequest()
    await waitFor(() => expect(screen.getByText('Все изменения сохранены')).toBeVisible())
  })
})
