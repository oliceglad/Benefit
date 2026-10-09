import { describe, expect, it } from 'vitest'

import { buildSkillVerificationState } from '@/features/candidate-profile/model/skill-verification'
import type {
  AssessmentInfo,
  AssessmentStatus,
  AttemptResponse,
  Outcome,
} from '@/shared/api/generated/assessments/models'

const catalog: AssessmentInfo[] = [{
  id: 'test-id',
  slug: 'frontend-middle',
  title: 'Frontend — Middle',
  description: 'Проверка знаний',
  specialization: 'frontend',
  grade: 'middle',
  time_limit_seconds: 1200,
  tasks_per_attempt: 8,
}]

const baseStatus: AssessmentStatus = {
  verified: null,
  active_attempt_id: null,
  cooldowns: [],
  attempts_total: 0,
}

function completedAttempt(outcome: Outcome, confirmedGrade: 'middle' | null): AttemptResponse {
  return {
    id: `attempt-${outcome}`,
    assessment: catalog[0],
    status: 'completed',
    survey: {},
    claimed_grade: 'middle',
    started_at: '2026-10-09T10:00:00Z',
    deadline_at: '2026-10-09T10:20:00Z',
    finished_at: '2026-10-09T10:12:00Z',
    time_left_seconds: 0,
    total_tasks: 8,
    answered_tasks: 8,
    max_score: 8,
    result: {
      score: confirmedGrade ? 7 : 4,
      max_score: 8,
      percent: confirmedGrade ? 87.5 : 50,
      outcome,
      target_grade: 'middle',
      confirmed_grade: confirmedGrade,
      message: 'Результат готов',
      duration_seconds: 720,
      tasks: [],
      skills: [{ skill: 'TypeScript', points: confirmedGrade ? 4 : 2, max_points: 4, percent: confirmedGrade ? 100 : 50 }],
    },
  }
}

const common = {
  skill: 'TypeScript',
  dirty: false,
  loading: false,
  failed: false,
  profileRoles: ['frontend'] as const,
  profileGrade: 'middle' as const,
  catalog,
  status: baseStatus,
  attempts: [],
}

describe('buildSkillVerificationState', () => {
  it('requires unsaved skills to be persisted before opening an assessment', () => {
    expect(buildSkillVerificationState({ ...common, dirty: true }).kind).toBe('unsaved')
  })

  it('maps an active server attempt to continuation', () => {
    const state = buildSkillVerificationState({
      ...common,
      status: { ...baseStatus, active_attempt_id: 'active-attempt' },
    })
    expect(state).toMatchObject({ kind: 'in_progress', attemptId: 'active-attempt' })
  })

  it('shows availability only when a matching specialization and grade test exists', () => {
    expect(buildSkillVerificationState(common).kind).toBe('available')
    expect(buildSkillVerificationState({ ...common, catalog: [] }).kind).toBe('unavailable')
  })

  it('keeps skill score separate from the confirmed overall grade', () => {
    const state = buildSkillVerificationState({
      ...common,
      attempts: [completedAttempt('confirmed', 'middle')],
    })
    expect(state).toMatchObject({ kind: 'result', percent: 100, confirmedGrade: 'middle' })
    expect(state.description).toContain('Подтверждён общий грейд')
  })

  it('shows an unsuccessful overall attempt without calling the skill unconfirmed', () => {
    const state = buildSkillVerificationState({
      ...common,
      attempts: [completedAttempt('not_confirmed', null)],
    })
    expect(state).toMatchObject({ kind: 'not_confirmed', percent: 50 })
    expect(state.description).toContain('Общий грейд не подтверждён')
  })
})
