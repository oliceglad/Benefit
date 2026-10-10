import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { HiringJourneyPreview } from '@/features/employer-company/ui/hiring-journey-preview'

describe('hiring journey design preview', () => {
  it('selects a stage and shows its status, branch and participants', async () => {
    const user = userEvent.setup()
    render(<HiringJourneyPreview />)
    const details = within(screen.getByRole('region', { name: 'Сведения об этапе' }))

    expect(screen.getByRole('button', { name: /Обсуждение с командой/ })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: /Практическое задание/ }))

    expect(details.getByRole('heading', { name: 'Практическое задание' })).toBeVisible()
    expect(details.getByText('Задание · опционально')).toBeVisible()
    expect(details.getByText('Кандидат и технический специалист')).toBeVisible()
    expect(screen.getByRole('button', { name: /Практическое задание/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /Обсуждение с командой/ })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByText('4 из 8 пройдено')).toBeVisible()
  })

  it('allows keyboard selection without changing the hiring progress', async () => {
    const user = userEvent.setup()
    render(<HiringJourneyPreview />)

    await user.tab()
    expect(screen.getByRole('button', { name: /Приглашение принято/ })).toHaveFocus()
    await user.keyboard('{Enter}')

    const details = within(screen.getByRole('region', { name: 'Сведения об этапе' }))
    expect(details.getByRole('heading', { name: 'Приглашение принято' })).toBeVisible()
    expect(details.getByText('Пройдено')).toBeVisible()
    expect(screen.getByText('4 из 8 пройдено')).toBeVisible()
    expect(screen.getByText(/не история реального кандидата/)).toBeVisible()
  })
})
