import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { PhoneInput } from '@/features/candidate-profile/ui/phone-input'

function PhoneInputHarness({ initialValue = '' }: { initialValue?: string }) {
  const [value, setValue] = useState(initialValue)
  return <PhoneInput aria-label="Телефон" value={value} onValueChange={setValue} />
}

describe('PhoneInput', () => {
  it('formats a Russian number while it is being typed from 8', async () => {
    const user = userEvent.setup()
    render(<PhoneInputHarness />)

    const input = screen.getByLabelText('Телефон')
    await user.type(input, '89991234567')

    expect(input).toHaveValue('+7 (999) 123-45-67')
  })

  it('formats a Russian number pasted with +7', async () => {
    const user = userEvent.setup()
    render(<PhoneInputHarness />)

    const input = screen.getByLabelText('Телефон')
    await user.click(input)
    await user.paste('+79991234567')

    expect(input).toHaveValue('+7 (999) 123-45-67')
  })

  it('keeps an international number available without adding a second country code', async () => {
    const user = userEvent.setup()
    render(<PhoneInputHarness />)

    const input = screen.getByLabelText('Телефон')
    await user.type(input, '+4930123456')

    expect(input).toHaveValue('+4930123456')
  })

  it('allows replacing a digit in the middle', async () => {
    const user = userEvent.setup()
    render(<PhoneInputHarness initialValue="+7 (999) 123-45-67" />)

    const input = screen.getByLabelText<HTMLInputElement>('Телефон')
    await user.click(input)
    input.setSelectionRange(6, 7)
    await user.keyboard('8')

    expect(input).toHaveValue('+7 (998) 123-45-67')
  })

  it('handles Backspace in the middle without moving the cursor to the end', async () => {
    const user = userEvent.setup()
    render(<PhoneInputHarness initialValue="+7 (999) 123-45-67" />)

    const input = screen.getByLabelText<HTMLInputElement>('Телефон')
    await user.click(input)
    input.setSelectionRange(7, 7)
    await user.keyboard('{Backspace}')

    expect(input.value.replace(/\D/g, '')).toHaveLength(10)
    expect(input.selectionStart).toBeLessThan(input.value.length)
  })
})
