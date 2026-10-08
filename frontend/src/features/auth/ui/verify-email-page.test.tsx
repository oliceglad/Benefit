import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { verificationFlow } from '@/features/auth/model/verification-flow'
import { VerifyEmailPage } from '@/features/auth/ui/verify-email-page'
import { server } from '@/test/server'

const navigate = vi.hoisted(() => vi.fn())

vi.mock('@tanstack/react-router', async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  useNavigate: () => navigate,
}))

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <VerifyEmailPage />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  verificationFlow.clear()
  navigate.mockReset()
})

describe('VerifyEmailPage', () => {
  it('allows entering the email manually after the page is reloaded', () => {
    verificationFlow.clear()

    renderPage()

    expect(screen.getByLabelText('Почта')).toBeVisible()
    expect(screen.getByText('Укажите почту и введите код из письма.')).toBeVisible()
  })

  it.each([
    ['invalid_code', 'Код не подходит. Проверьте цифры и попробуйте снова.'],
    ['code_expired', 'Срок действия кода истёк. Отправьте новый код.'],
  ])('keeps the code and email after a %s response', async (code, message) => {
    const user = userEvent.setup()
    verificationFlow.setEmail('candidate@example.ru')
    server.use(
      http.post('*/api/v1/auth/verify-email', () =>
        HttpResponse.json(
          { error: { code, message: 'Verification code rejected' } },
          { status: 400 },
        ),
      ),
    )
    renderPage()

    const codeInput = screen.getByLabelText('Код из письма')
    await user.type(codeInput, '012345')
    await user.click(screen.getByRole('button', { name: 'Подтвердить' }))

    expect(await screen.findByText(message)).toBeVisible()
    expect(codeInput).toHaveValue('012345')
    expect(screen.getByText('candidate@example.ru')).toBeVisible()
  })

  it('blocks resend during the registration cooldown', () => {
    verificationFlow.start('candidate@example.ru', 600, 60)

    renderPage()

    expect(screen.getByRole('button', { name: 'Отправить код повторно' })).toBeDisabled()
  })

  it('sends one resend request and applies Retry-After after a double click', async () => {
    const user = userEvent.setup()
    let requestCount = 0
    verificationFlow.setEmail('candidate@example.ru')
    server.use(
      http.post('*/api/v1/auth/resend-code', async () => {
        requestCount += 1
        await delay(40)
        return HttpResponse.json(
          { error: { code: 'resend_cooldown', message: 'Wait before retrying' } },
          { status: 429, headers: { 'Retry-After': '12' } },
        )
      }),
    )
    renderPage()

    const resendButton = screen.getByRole('button', { name: 'Отправить код повторно' })
    await Promise.all([user.click(resendButton), user.click(resendButton)])

    expect(await screen.findByText('Новый код можно отправить через 12 сек.')).toBeVisible()
    await waitFor(() => expect(resendButton).toBeDisabled())
    expect(requestCount).toBe(1)
  })
})
