import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { talentDefaults } from '@/features/talent/model/talent-search'
import { TalentFilters } from './talent-filters'

describe('employer search controls', () => {
  it('preserves an unfinished query when sorting changes and applies the current sort', async () => {
    const user = userEvent.setup()
    const onApply = vi.fn()
    const view = render(<TalentFilters value={talentDefaults} onApply={onApply} />)
    await user.type(screen.getByLabelText('Ключевые слова'), 'Python')
    view.rerender(<TalentFilters value={{ ...talentDefaults, sort: 'fsp' }} onApply={onApply} />)
    await user.click(screen.getByRole('button', { name: 'Применить фильтры' }))
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ q: 'Python', sort: 'fsp', grade_status: 'confirmed', offset: 0 }))
  })

  it('keeps the applied query unchanged when the experience range is inverted', async () => {
    const user = userEvent.setup()
    const onApply = vi.fn()
    render(<TalentFilters value={{ ...talentDefaults, experience_min: 6, experience_max: 2 }} onApply={onApply} />)
    await user.click(screen.getByRole('button', { name: 'Применить фильтры' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Максимальный опыт должен быть не меньше минимального')
    expect(onApply).not.toHaveBeenCalled()
  })
})
