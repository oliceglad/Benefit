import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'

import { Textarea } from '@/shared/ui/textarea'

const originalScrollHeight = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'scrollHeight')

beforeAll(() => {
  Object.defineProperty(HTMLTextAreaElement.prototype, 'scrollHeight', {
    configurable: true,
    get(this: HTMLTextAreaElement) {
      return this.value.length > 20 ? 240 : 128
    },
  })
})

afterAll(() => {
  if (originalScrollHeight) Object.defineProperty(HTMLTextAreaElement.prototype, 'scrollHeight', originalScrollHeight)
  else Reflect.deleteProperty(HTMLTextAreaElement.prototype, 'scrollHeight')
})

function TextareaHarness() {
  const [value, setValue] = useState('Короткий текст')
  return <Textarea aria-label="Описание" value={value} onChange={(event) => setValue(event.target.value)} />
}

describe('Textarea', () => {
  it('grows with its content instead of creating an inner scrollbar', async () => {
    const user = userEvent.setup()
    render(<TextareaHarness />)

    const textarea = screen.getByLabelText('Описание')
    expect(textarea).toHaveStyle({ height: '128px' })
    expect(textarea).toHaveClass('overflow-hidden', 'resize-none')

    await user.type(textarea, ' с достаточно длинным продолжением')

    expect(textarea).toHaveStyle({ height: '240px' })
  })
})
