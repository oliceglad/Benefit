import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { createTestProfile, testProfileDictionaries } from '@/test/fixtures/candidate'

import { CandidateProfileOverview } from './profile-overview'

vi.mock('./photo-manager', () => ({ PhotoManager: () => <div>Фото</div> }))

describe('mobile candidate profile overview', () => {
  it('shows grouped section links and opens the selected section', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()
    render(
      <CandidateProfileOverview
        profile={createTestProfile({ first_name: 'Анна', last_name: 'Иванова' })}
        dictionaries={testProfileDictionaries}
        consents={[]}
        consentsFailed={false}
        resumeActions={<button type="button">Скачать резюме</button>}
        onNavigate={onNavigate}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Данные профиля' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Видимость профиля' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Контакты/ }))
    expect(onNavigate).toHaveBeenCalledWith('contacts')
  })
})
