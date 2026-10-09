import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { SearchableMultiSelect } from '@/features/candidate-profile/ui/searchable-multi-select'

const options = [
  { value: 'frontend', label: 'Frontend-разработчик' },
  { value: 'backend', label: 'Backend-разработчик' },
  { value: 'qa', label: 'Тестировщик' },
] as const

type OptionValue = (typeof options)[number]['value']

function TestSelect() {
  const [value, setValue] = useState<OptionValue[]>(['frontend'])
  return (
    <SearchableMultiSelect
      id="roles"
      label="IT-роли"
      options={options}
      value={value}
      onChange={setValue}
      placeholder="Выберите роли"
      searchPlaceholder="Найти роль"
      maxSelections={2}
    />
  )
}

describe('SearchableMultiSelect', () => {
  it('filters and selects options from the keyboard without exceeding the limit', async () => {
    const user = userEvent.setup()
    render(<TestSelect />)

    const input = screen.getByRole('combobox', { name: 'IT-роли' })
    expect(screen.getByText('Frontend-разработчик')).toBeVisible()
    expect(screen.getByText('Выбрано 1 из 2')).toBeVisible()

    await user.click(input)
    await user.type(input, 'backend')
    expect(screen.getByRole('option', { name: 'Backend-разработчик' })).toBeVisible()
    expect(screen.queryByRole('option', { name: 'Тестировщик' })).not.toBeInTheDocument()
    await user.keyboard('{Enter}')

    expect(screen.getByText('Выбрано 2 из 2')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Убрать Backend-разработчик' })).toBeVisible()

    await user.type(input, 'тест')
    expect(screen.getByRole('option', { name: 'Тестировщик' })).toHaveAttribute('aria-disabled', 'true')
    await user.keyboard('{Enter}')
    expect(screen.getByText('Выбрано 2 из 2')).toBeVisible()
  })

  it('removes a selected value with an accessible button', async () => {
    const user = userEvent.setup()
    render(<TestSelect />)

    await user.click(screen.getByRole('button', { name: 'Убрать Frontend-разработчик' }))

    expect(screen.getByText('Выбрано 0 из 2')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Убрать Frontend-разработчик' })).not.toBeInTheDocument()
  })
})
