import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { CandidateAccountMenu } from './candidate-layout'

function renderMenu(onLogout = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <CandidateAccountMenu
        userId="candidate-1"
        hasPhoto={false}
        firstName="Анна"
        lastName="Иванова"
        accountName="Анна Иванова"
        pending={false}
        onLogout={onLogout}
      />
    </QueryClientProvider>,
  )
  return onLogout
}

describe('candidate account menu', () => {
  it('supports keyboard opening, closing and focus restoration', async () => {
    const user = userEvent.setup()
    renderMenu()
    const trigger = screen.getByRole('button', { name: 'Открыть меню аккаунта' })

    trigger.focus()
    await user.keyboard('{Enter}')
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getAllByText('Анна Иванова')).toHaveLength(2)
    expect(screen.getAllByText('Кандидат')).toHaveLength(2)

    await user.keyboard('{Escape}')
    expect(trigger).toHaveFocus()
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })

  it('uses the provided logout action', async () => {
    const user = userEvent.setup()
    const onLogout = renderMenu()

    await user.click(screen.getByRole('button', { name: 'Открыть меню аккаунта' }))
    await user.click(screen.getByRole('menuitem', { name: 'Выйти' }))

    expect(onLogout).toHaveBeenCalledOnce()
  })
})
