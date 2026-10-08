import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { ContactForm } from '@/features/candidate-profile/ui/contact-form'
import { session } from '@/shared/session/session'
import { server } from '@/test/server'

describe('ContactForm', () => {
  it('patches contacts, refetches the profile and only then confirms persistence', async () => {
    const user = userEvent.setup()
    let contacts = {
      phone: '+7 900 000-00-00',
      contact_email: 'old@example.ru',
      telegram: '@old_name',
    }
    let getCount = 0
    let patchCount = 0

    session.setTokens({
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
      expiresIn: 900,
      refreshExpiresIn: 604800,
    })
    server.use(
      http.get('*/api/v1/candidates/me', ({ request }) => {
        expect(request.headers.get('Authorization')).toBe('Bearer access-token')
        getCount += 1
        return HttpResponse.json({ user_id: 'candidate-id', ...contacts })
      }),
      http.patch('*/api/v1/candidates/me', async ({ request }) => {
        patchCount += 1
        contacts = { ...contacts, ...((await request.json()) as typeof contacts) }
        return HttpResponse.json({ user_id: 'candidate-id', ...contacts })
      }),
    )
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <ContactForm />
      </QueryClientProvider>,
    )

    const email = await screen.findByLabelText('Контактная почта')
    await user.clear(email)
    await user.type(email, 'very-long-candidate-name@example.ru')
    const telegram = screen.getByLabelText('Telegram')
    await user.clear(telegram)
    await user.type(telegram, '@candidate_from_samara_longname')
    await user.click(screen.getByRole('button', { name: 'Сохранить контакты' }))

    expect(await screen.findByText('Контакты сохранены')).toBeVisible()
    expect(patchCount).toBe(1)
    expect(getCount).toBe(2)
    expect(screen.getByLabelText('Контактная почта')).toHaveValue(
      'very-long-candidate-name@example.ru',
    )
    await waitFor(() => expect(screen.getByText('Все изменения сохранены')).toBeVisible())
  })

  it('reports a successful PATCH separately when the confirmation GET fails', async () => {
    const user = userEvent.setup()
    let getCount = 0
    server.use(
      http.get('*/api/v1/candidates/me', () => {
        getCount += 1
        if (getCount > 1) {
          return HttpResponse.json({ error: { code: 'temporarily_unavailable' } }, { status: 503 })
        }
        return HttpResponse.json({
          user_id: 'candidate-id',
          phone: '+79000000000',
          contact_email: 'old@example.ru',
          telegram: '@old_name',
        })
      }),
      http.patch('*/api/v1/candidates/me', async ({ request }) =>
        HttpResponse.json({ user_id: 'candidate-id', ...((await request.json()) as object) }),
      ),
    )
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <ContactForm />
      </QueryClientProvider>,
    )

    const email = await screen.findByLabelText('Контактная почта')
    await user.clear(email)
    await user.type(email, 'saved@example.ru')
    await user.click(screen.getByRole('button', { name: 'Сохранить контакты' }))

    expect(await screen.findByText('Не удалось получить актуальные данные. Обновите профиль позже.')).toBeVisible()
    expect(screen.queryByText('Не удалось сохранить')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Контактная почта')).toHaveValue('saved@example.ru')
  })

  it('does not overwrite unsaved values during a background profile update', async () => {
    const user = userEvent.setup()
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    server.use(
      http.get('*/api/v1/candidates/me', () =>
        HttpResponse.json({
          user_id: 'candidate-id',
          phone: '+79000000000',
          contact_email: 'initial@example.ru',
          telegram: '@initial',
        }),
      ),
    )
    render(
      <QueryClientProvider client={queryClient}>
        <ContactForm />
      </QueryClientProvider>,
    )

    const email = await screen.findByLabelText('Контактная почта')
    await user.clear(email)
    await user.type(email, 'unsaved@example.ru')
    queryClient.setQueryData(['candidate', 'profile'], {
      user_id: 'candidate-id',
      phone: '+79999999999',
      contact_email: 'background@example.ru',
      telegram: '@background',
    })

    await waitFor(() => expect(email).toHaveValue('unsaved@example.ru'))
    expect(screen.getByText('Есть несохранённые изменения')).toBeVisible()
  })
})
