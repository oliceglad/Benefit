import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'

import { BrandGuide } from '@/features/platform-guide/ui/brand-guide'

// jsdom has no browser top layer; the real modal/focus trap is checked in Chromium.
const originalShow = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal')
const originalClose = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'close')
beforeAll(() => {
  Object.defineProperties(HTMLDialogElement.prototype, {
    showModal: { configurable: true, value(this: HTMLDialogElement) { this.setAttribute('open', '') } },
    close: { configurable: true, value(this: HTMLDialogElement) { this.removeAttribute('open') } },
  })
})
afterAll(() => {
  if (originalShow) Object.defineProperty(HTMLDialogElement.prototype, 'showModal', originalShow)
  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal')
  if (originalClose) Object.defineProperty(HTMLDialogElement.prototype, 'close', originalClose)
  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'close')
})

describe('optional platform guide', () => {
  it('requires a menu choice, supports dismissal and restores focus without navigation', async () => {
    const user = userEvent.setup()
    render(<BrandGuide role="employer" />)
    const trigger = screen.getByRole('button', { name: 'Открыть меню Benefit' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(trigger)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('menuitem', { name: 'Знакомство с платформой' }))
    const dialog = screen.getByRole('dialog', { name: 'Сильная команда начинается с вашей задачи' })
    expect(document.body.style.overflow).toBe('hidden')
    await user.click(within(dialog).getByRole('button', { name: 'Далее' }))
    expect(within(dialog).getByRole('heading', { name: 'Смотрите глубже названия должности' })).toHaveFocus()
    within(dialog).getByRole('button', { name: 'Далее' }).focus()
    await user.tab()
    expect(within(dialog).getByRole('button', { name: 'Закрыть знакомство' })).toHaveFocus()
    await user.tab({ shift: true })
    expect(within(dialog).getByRole('button', { name: 'Далее' })).toHaveFocus()
    fireEvent(dialog, new Event('cancel', { cancelable: true }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
    expect(document.body.style.overflow).toBe('')
    await user.click(trigger)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows candidate instructions, completes and can restart from step one', async () => {
    const user = userEvent.setup()
    render(<BrandGuide role="candidate" />)
    await user.click(screen.getByRole('button', { name: 'Открыть меню Benefit' }))
    await user.click(screen.getByRole('menuitem', { name: 'Знакомство с платформой' }))
    expect(screen.getByRole('heading', { name: 'Пусть ваш опыт говорит за вас' })).toBeInTheDocument()
    for (let index = 0; index < 4; index += 1) await user.click(screen.getByRole('button', { name: 'Далее' }))
    expect(screen.getByRole('heading', { name: 'Следующий шаг — знакомство с командой' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Начать работу' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Открыть меню Benefit' }))
    await user.click(screen.getByRole('menuitem', { name: 'Знакомство с платформой' }))
    expect(screen.getByRole('heading', { name: 'Пусть ваш опыт говорит за вас' })).toBeInTheDocument()
  })
})
