import { BadgeCheck, CircleHelp, CircleX, ClipboardCheck, LoaderCircle, Save, Timer } from 'lucide-react'

import type { SkillVerificationState } from '@/features/candidate-profile/model/skill-verification'
import { Button } from '@/shared/ui/button'

const iconByKind = {
  loading: LoaderCircle,
  unavailable: CircleHelp,
  unsaved: Save,
  available: ClipboardCheck,
  in_progress: Timer,
  checking: LoaderCircle,
  result: BadgeCheck,
  not_confirmed: CircleX,
} satisfies Record<SkillVerificationState['kind'], typeof CircleHelp>

function actionLabel(state: SkillVerificationState): string | null {
  if (state.kind === 'unsaved') return 'Сохранить и перейти'
  if (state.kind === 'available') return 'Подтвердить навык'
  if (state.kind === 'in_progress') return 'Продолжить'
  if (state.kind === 'result' || state.kind === 'not_confirmed') return 'Посмотреть результат'
  return null
}

export function SkillVerificationPanel({
  state,
  pending,
  onAction,
}: {
  state: SkillVerificationState
  pending: boolean
  onAction: () => void
}) {
  const Icon = iconByKind[state.kind]
  const label = actionLabel(state)
  if (label) {
    return (
      <Button type="button" size="sm" className="px-4" disabled={pending} onClick={onAction} title={state.description}>
        {pending ? 'Сохраняем…' : label}
      </Button>
    )
  }
  return (
    <div
      className="inline-flex min-h-11 max-w-full items-center gap-2 rounded-xl bg-muted px-3 py-2 text-sm font-medium text-muted-foreground"
      role="status"
      aria-label={`${state.title}. ${state.description}`}
      title={state.description}
    >
      <Icon className={`size-4 shrink-0 ${state.kind === 'loading' || state.kind === 'checking' ? 'animate-spin' : ''}`} aria-hidden="true" />
      <span className="min-w-0 break-words">{state.title}</span>
    </div>
  )
}
