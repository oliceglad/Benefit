import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import {
  finishAssessment,
  getAssessmentAttempt,
  getAssessmentTask,
  startAssessment,
  submitAssessmentAnswer,
} from '@/features/candidate-profile/api/assessment'
import type { AttemptResponse } from '@/shared/api/generated/assessments/models'
import { server } from '@/test/server'

const attempt: AttemptResponse = {
  id: 'attempt-1',
  assessment: {
    id: 'assessment-1',
    slug: 'frontend-middle',
    title: 'Frontend — Middle',
    description: 'Проверка знаний frontend-разработчика',
    specialization: 'frontend',
    grade: 'middle',
    time_limit_seconds: 1200,
    tasks_per_attempt: 1,
  },
  status: 'in_progress',
  survey: {},
  claimed_grade: 'middle',
  started_at: '2026-10-09T10:00:00Z',
  deadline_at: '2026-10-09T10:20:00Z',
  finished_at: null,
  time_left_seconds: 1200,
  total_tasks: 1,
  answered_tasks: 0,
  max_score: 1,
  result: null,
}

describe('assessment candidate flow', () => {
  it('starts an attempt, loads a task, submits an answer and uses only the server result', async () => {
    const calls: string[] = []

    server.use(
      http.post('*/api/v1/assessments/attempts', async ({ request }) => {
        calls.push('start')
        expect(await request.json()).toEqual({
          industry: 'fintech',
          specialization: 'frontend',
          target_grade: 'middle',
          years_of_experience: 3.5,
          skills: ['TypeScript'],
        })
        return HttpResponse.json(attempt, { status: 201 })
      }),
      http.get('*/api/v1/assessments/attempts/attempt-1', () => {
        calls.push('attempt')
        return HttpResponse.json(attempt)
      }),
      http.get('*/api/v1/assessments/attempts/attempt-1/current-task', () => {
        calls.push('task')
        return HttpResponse.json({
          attempt_task_id: 'task-1',
          position: 1,
          total: 1,
          kind: 'single_choice',
          prompt: 'Какой тип точнее описывает строку?',
          code: null,
          options: [{ id: 'answer-1', text: 'string' }],
          points: 1,
          skills: ['TypeScript'],
          time_limit_seconds: 120,
          time_left_seconds: 120,
          started_at: '2026-10-09T10:01:00Z',
        })
      }),
      http.post('*/api/v1/assessments/attempts/attempt-1/answers', async ({ request }) => {
        calls.push('answer')
        expect(await request.json()).toEqual({
          attempt_task_id: 'task-1',
          answer: 'answer-1',
        })
        return HttpResponse.json({
          time_spent_seconds: 12,
          timed_out: false,
          finished: true,
          attempt: { ...attempt, answered_tasks: 1 },
        })
      }),
      http.post('*/api/v1/assessments/attempts/attempt-1/finish', () => {
        calls.push('finish')
        return HttpResponse.json({
          ...attempt,
          status: 'completed',
          answered_tasks: 1,
          finished_at: '2026-10-09T10:02:00Z',
          time_left_seconds: 1080,
          result: {
            score: 1,
            max_score: 1,
            percent: 100,
            outcome: 'confirmed',
            target_grade: 'middle',
            confirmed_grade: 'middle',
            message: 'Грейд подтверждён',
            duration_seconds: 120,
            tasks: [],
            skills: [{ skill: 'TypeScript', points: 1, max_points: 1, percent: 100 }],
          },
        })
      }),
    )

    const started = await startAssessment({
      industry: 'fintech',
      specialization: 'frontend',
      target_grade: 'middle',
      years_of_experience: 3.5,
      skills: ['TypeScript'],
    })
    await getAssessmentAttempt(started.id)
    const task = await getAssessmentTask(started.id)
    const answer = await submitAssessmentAnswer(started.id, {
      attempt_task_id: task.attempt_task_id,
      answer: 'answer-1',
    })
    const finished = await finishAssessment(started.id)

    expect(answer.finished).toBe(true)
    expect(finished.result).toMatchObject({
      percent: 100,
      confirmed_grade: 'middle',
      skills: [{ skill: 'TypeScript', percent: 100 }],
    })
    expect(calls).toEqual(['start', 'attempt', 'task', 'answer', 'finish'])
  })
})
