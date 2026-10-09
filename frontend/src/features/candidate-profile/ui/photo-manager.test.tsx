import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { PhotoManager } from './photo-manager'
import { privateObjectUrlTestApi } from '@/shared/lib/private-object-url'
import { createTestProfile } from '@/test/fixtures/candidate'

let revokeObjectUrl: ReturnType<typeof vi.fn>

beforeEach(() => {
  let objectUrlId = 0
  privateObjectUrlTestApi.reset()
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => `blob:private-${++objectUrlId}`) })
  revokeObjectUrl = vi.fn()
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectUrl })
})

afterEach(() => {
  privateObjectUrlTestApi.reset()
  vi.restoreAllMocks()
})

function renderManager(hasPhoto: boolean) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  queryClient.setQueryData(['candidate', 'profile'], createTestProfile({ has_photo: hasPhoto }))
  render(
    <QueryClientProvider client={queryClient}>
      <PhotoManager profile={createTestProfile({ has_photo: hasPhoto })} />
    </QueryClientProvider>,
  )
  return queryClient
}

describe('PhotoManager', () => {
  it('shows a local preview and uploads the chosen photo', async () => {
    const user = userEvent.setup()
    const methods: string[] = []
    vi.spyOn(globalThis, 'fetch').mockImplementation((_input, init) => {
      methods.push(init?.method ?? 'GET')
      return Promise.resolve(new Response(null, { status: 204 }))
    })
    renderManager(false)

    const file = new File(['photo'], 'candidate.webp', { type: 'image/webp' })
    await user.upload(screen.getByLabelText('Выбрать фото'), file)
    expect(screen.getByRole('img', { name: 'Фото кандидата' })).toHaveAttribute('src', 'blob:private-1')
    await user.click(screen.getByRole('button', { name: 'Загрузить' }))

    await waitFor(() => expect(methods).toContain('PUT'))
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:private-1')
  })

  it('deletes an existing photo only after confirmation', async () => {
    const user = userEvent.setup()
    const methods: string[] = []
    vi.spyOn(globalThis, 'fetch').mockImplementation((_input, init) => {
      const method = init?.method ?? 'GET'
      methods.push(method)
      if (method === 'GET') {
        return Promise.resolve(new Response(new Uint8Array([255, 216, 255, 217]), { headers: { 'Content-Type': 'image/jpeg' } }))
      }
      return Promise.resolve(new Response(null, { status: 204 }))
    })
    const queryClient = renderManager(true)

    await user.click(screen.getByRole('button', { name: 'Изменить фото' }))
    await user.click(screen.getByRole('menuitem', { name: 'Удалить фото' }))
    expect(screen.getByText('Удалить фото?')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Удалить' }))

    await waitFor(() => expect(methods).toContain('DELETE'))
    expect(queryClient.getQueryData(['candidate', 'profile'])).toMatchObject({ has_photo: false })
  })
})
