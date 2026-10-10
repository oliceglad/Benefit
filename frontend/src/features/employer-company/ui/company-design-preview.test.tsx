import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { CompanyDesignPreview } from '@/features/employer-company/ui/company-design-preview'

describe('company design preview', () => {
  it('updates the company card while editing and restores the example on reset', async () => {
    const user = userEvent.setup()
    render(<CompanyDesignPreview />)
    const preview = within(screen.getByRole('complementary', { name: 'Предпросмотр компании' }))
    const name = screen.getByLabelText(/Название компании/)

    await user.clear(name)
    await user.type(name, 'Новая   команда')
    expect(name).toHaveValue('Новая   команда')
    expect(preview.getByRole('heading', { name: 'Новая команда' })).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Вернуть пример' }))
    expect(name).toHaveValue('Команда Север')
    expect(preview.getByRole('heading', { name: 'Команда Север' })).toBeVisible()
  })

  it('blocks an invalid form and confirms validation without claiming persistence', async () => {
    const user = userEvent.setup()
    render(<CompanyDesignPreview />)
    const name = screen.getByLabelText(/Название компании/)

    await user.clear(name)
    await user.click(screen.getByRole('button', { name: 'Проверить форму' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Укажите название компании')
    expect(name).toHaveFocus()
    expect(screen.queryByText(/Поля заполнены корректно/)).not.toBeInTheDocument()

    await user.type(name, 'Команда')
    await user.click(screen.getByRole('button', { name: 'Проверить форму' }))
    expect(await screen.findByText(/В этой пробе данные не отправляются на сервер/)).toBeVisible()
    expect(screen.queryByText(/Компания сохранена/)).not.toBeInTheDocument()
  })
})
