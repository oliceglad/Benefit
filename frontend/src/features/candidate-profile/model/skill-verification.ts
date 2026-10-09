import type {
  AssessmentInfo,
  AssessmentStatus,
  AttemptResponse,
  Grade,
  ITRole,
} from '@/shared/api/generated/assessments/models'

export type SkillVerificationState =
  | { kind: 'loading'; title: string; description: string }
  | { kind: 'unavailable'; title: string; description: string }
  | { kind: 'unsaved'; title: string; description: string }
  | { kind: 'available'; title: string; description: string }
  | { kind: 'in_progress'; title: string; description: string; attemptId: string }
  | { kind: 'checking'; title: string; description: string; attemptId: string }
  | { kind: 'result'; title: string; description: string; attemptId: string; percent: number; confirmedGrade: Grade | null }
  | { kind: 'not_confirmed'; title: string; description: string; attemptId: string; percent: number }

function sameSkill(left: string, right: string): boolean {
  return left.localeCompare(right, 'ru-RU', { sensitivity: 'accent' }) === 0
}

function latestSkillResult(skill: string, attempts: readonly AttemptResponse[]): { attempt: AttemptResponse; percent: number } | null {
  const sorted = [...attempts].sort((left, right) => Date.parse(right.started_at) - Date.parse(left.started_at))
  for (const attempt of sorted) {
    const score = attempt.result?.skills.find((item) => sameSkill(item.skill, skill))
    if (score) return { attempt, percent: score.percent }
  }
  return null
}

function matchingTest(catalog: readonly AssessmentInfo[], roles: readonly ITRole[], grade: Grade | null): AssessmentInfo | null {
  if (!grade) return null
  return catalog.find((test) => roles.includes(test.specialization) && test.grade === grade) ?? null
}

export function buildSkillVerificationState({
  skill,
  dirty,
  loading,
  failed,
  profileRoles,
  profileGrade,
  catalog,
  status,
  attempts,
}: {
  skill: string
  dirty: boolean
  loading: boolean
  failed: boolean
  profileRoles: readonly ITRole[]
  profileGrade: Grade | null
  catalog: readonly AssessmentInfo[]
  status: AssessmentStatus | null
  attempts: readonly AttemptResponse[]
}): SkillVerificationState {
  if (dirty) {
    return {
      kind: 'unsaved',
      title: 'Сначала сохраните навыки',
      description: 'Проверка использует сохранённые данные профиля.',
    }
  }
  if (loading) {
    return { kind: 'loading', title: 'Проверяем доступность', description: 'Это займёт несколько секунд.' }
  }
  if (failed || !status) {
    return {
      kind: 'unavailable',
      title: 'Проверка временно недоступна',
      description: 'Не удалось загрузить доступные проверки. Обновите страницу или попробуйте позже.',
    }
  }
  if (status.active_attempt_id) {
    return {
      kind: 'in_progress',
      title: 'Попытка начата',
      description: 'Таймер продолжает идти по серверному сроку.',
      attemptId: status.active_attempt_id,
    }
  }

  const result = latestSkillResult(skill, attempts)
  if (result?.attempt.result?.outcome === 'not_confirmed') {
    return {
      kind: 'not_confirmed',
      title: 'Попытка завершена',
      description: `Результат по заданиям с этим навыком — ${result.percent}%. Общий грейд не подтверждён.`,
      attemptId: result.attempt.id,
      percent: result.percent,
    }
  }
  if (result?.attempt.result) {
    const confirmedGrade = result.attempt.result.confirmed_grade
    return {
      kind: 'result',
      title: confirmedGrade ? 'Есть подтверждённый результат' : 'Есть результат проверки',
      description: confirmedGrade
        ? `По заданиям с этим навыком — ${result.percent}%. Подтверждён общий грейд.`
        : `По заданиям с этим навыком — ${result.percent}%.`,
      attemptId: result.attempt.id,
      percent: result.percent,
      confirmedGrade,
    }
  }

  if (!profileGrade || profileRoles.length === 0) {
    return {
      kind: 'unavailable',
      title: 'Нужно заполнить специализацию',
      description: 'Укажите IT-роль и заявленный грейд, чтобы подобрать задания.',
    }
  }
  const cooldown = status.cooldowns.find((item) => profileRoles.includes(item.specialization))
  if (cooldown) {
    const availableAt = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(cooldown.available_at))
    return {
      kind: 'unavailable',
      title: 'Повторная попытка пока недоступна',
      description: `Следующую попытку можно начать ${availableAt}.`,
    }
  }
  if (matchingTest(catalog, profileRoles, profileGrade)) {
    return {
      kind: 'available',
      title: 'Проверка доступна',
      description: 'Навык может встретиться в общем тесте по специализации и грейду.',
    }
  }
  return {
    kind: 'unavailable',
    title: 'Заданий пока нет',
    description: 'Для выбранной специализации и грейда проверка ещё не подготовлена.',
  }
}
