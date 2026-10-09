import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { candidateProfileQueryKey } from '@/features/candidate-profile/api/profile'
import { profileDraft } from '@/features/candidate-profile/model/profile-draft'
import { ProfileFileActions } from '@/features/candidate-profile/ui/profile-file-actions'
import { createTestProfile, testProfileDictionaries } from '@/test/fixtures/candidate'

afterEach(() => vi.restoreAllMocks())

function renderActions({ dirty = false, onImportActiveChange = vi.fn() } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <ProfileFileActions
        profile={createTestProfile()}
        dictionaries={testProfileDictionaries}
        draft={{ section: 'personal', isDirty: dirty }}
        onImportActiveChange={onImportActiveChange}
      />
    </QueryClientProvider>,
  )
  return { queryClient, onImportActiveChange }
}

function installResumeFetch(profileAfterApply = createTestProfile({ city: 'Самара' })) {
  const modes: string[] = []
  const patches: unknown[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
    const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url)
    if (url.pathname === '/api/v1/candidates/me') {
      if (init?.method === 'PATCH') {
        if (typeof init.body !== 'string') throw new Error('Expected JSON request body')
        patches.push(JSON.parse(init.body) as unknown)
      }
      return Promise.resolve(new Response(JSON.stringify(profileAfterApply), { headers: { 'Content-Type': 'application/json' } }))
    }
    const apply = url.searchParams.get('apply') ?? 'false'
    modes.push(apply)
    return Promise.resolve(new Response(JSON.stringify({
      draft: { city: 'Самара' },
      warnings: [],
      applied: apply === 'true',
      applied_fields: apply === 'true' ? ['city'] : [],
    }), { headers: { 'Content-Type': 'application/json' } }))
  })
  return { modes, patches }
}

describe('ProfileFileActions', () => {
  it('resolves an unsaved section before import and cancellation never applies data', async () => {
    const user = userEvent.setup()
    const { modes } = installResumeFetch()
    const discard = vi.fn()
    const unregister = profileDraft.register({ section: 'personal', save: () => Promise.resolve(true), discard })
    const onImportActiveChange = vi.fn()
    renderActions({ dirty: true, onImportActiveChange })

    await user.click(screen.getByRole('button', { name: 'Загрузить резюме' }))
    expect(screen.getByText('Есть несохранённые изменения')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Не сохранять' }))
    expect(discard).toHaveBeenCalledOnce()

    const file = new File(['%PDF-1.7'], 'long-candidate-resume.pdf', { type: 'application/pdf' })
    await user.upload(screen.getByLabelText('Выбрать PDF-резюме'), file)
    expect(await screen.findByText('Проверка данных резюме')).toBeVisible()
    expect(modes).toEqual(['false'])

    await user.click(screen.getByRole('button', { name: 'Отмена' }))
    expect(screen.queryByText('Проверка данных резюме')).not.toBeInTheDocument()
    expect(modes).toEqual(['false'])
    expect(onImportActiveChange).toHaveBeenNthCalledWith(1, true)
    expect(onImportActiveChange).toHaveBeenLastCalledWith(false)
    unregister()
  })

  it('applies only after confirmation and refreshes profile data from the server', async () => {
    const user = userEvent.setup()
    const updated = createTestProfile({ city: 'Самара', completeness: { ...createTestProfile().completeness, percent: 58 } })
    const { modes, patches } = installResumeFetch(updated)
    const { queryClient } = renderActions()
    const file = new File(['%PDF-1.7'], 'resume.pdf', { type: 'application/pdf' })

    await user.upload(screen.getByLabelText('Выбрать PDF-резюме'), file)
    expect(await screen.findByText('Проверка данных резюме')).toBeVisible()
    expect(modes).toEqual(['false'])
    await user.click(screen.getByRole('checkbox', { name: 'Импортировать: Город' }))
    await user.click(screen.getByRole('button', { name: 'Применить выбранное (1)' }))

    expect(await screen.findByText('Выбранные данные применены')).toBeVisible()
    expect(modes).toEqual(['false'])
    expect(patches).toEqual([{ city: 'Самара' }])
    await waitFor(() => expect(queryClient.getQueryData(candidateProfileQueryKey)).toMatchObject({ city: 'Самара', completeness: { percent: 58 } }))
  })
})
