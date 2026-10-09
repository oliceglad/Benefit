import { describe, expect, it } from 'vitest'

import { candidateBackLink } from './candidate-navigation'

describe('candidate cabinet back navigation', () => {
  it('returns from an attempt to the assessment overview', () => {
    expect(candidateBackLink('/assessments/attempts/attempt-1')).toEqual({
      destination: 'assessments',
      label: 'К проверкам',
    })
  })

  it('returns from assessments to the skills section', () => {
    expect(candidateBackLink('/assessments')).toEqual({
      destination: 'skills',
      label: 'К навыкам профиля',
    })
  })

  it('does not add a back action to the profile itself', () => {
    expect(candidateBackLink('/profile')).toBeNull()
  })
})
