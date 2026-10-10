import { Check, CircleAlert } from 'lucide-react'

import type { MatchedCandidate } from '@/shared/api/generated/talent/models'
import { Badge } from '@/shared/ui/badge'

const fitLabels: Record<MatchedCandidate['fit'], string> = { excellent: 'Высокое соответствие', good: 'Хорошее соответствие', partial: 'Частичное соответствие' }

export function MatchPreview({ match }: { match: MatchedCandidate }) {
  return <div className="space-y-2 border-t bg-primary/5 px-5 py-3"><div className="flex flex-wrap items-center gap-2"><Badge className="bg-primary/10 text-primary">{match.score} из 100</Badge><span className="text-xs font-medium">{fitLabels[match.fit]}</span></div>{match.reasons.length ? <p className="text-xs leading-5 text-muted-foreground">{match.reasons.slice(0, 2).join(' · ')}</p> : <p className="text-xs text-muted-foreground">Причины соответствия не предоставлены.</p>}</div>
}

export function MatchExplanation({ match }: { match: MatchedCandidate }) {
  return (
    <section className="space-y-5" aria-label="Объяснение подбора">
      <div className="space-y-1"><h3 className="font-semibold">Почему в подборке</h3><p className="text-xs leading-5 text-muted-foreground">Оценка по условиям потребности: {match.score} из 100. Она помогает сравнить профили и не является вероятностью найма.</p></div>
      {match.reasons.length ? <ul className="space-y-2">{match.reasons.map((reason, index) => <li key={index} className="flex gap-2 text-sm leading-6"><Check size={16} className="mt-1 shrink-0 text-primary" aria-hidden="true" />{reason}</li>)}</ul> : null}
      {match.warnings.length ? <ul className="space-y-2 rounded-lg border bg-muted/40 p-4">{match.warnings.map((warning, index) => <li key={index} className="flex gap-2 text-sm leading-6"><CircleAlert size={16} className="mt-1 shrink-0 text-muted-foreground" aria-hidden="true" />{warning}</li>)}</ul> : null}
      <div className="grid gap-4 sm:grid-cols-2"><div className="space-y-2"><h4 className="text-xs font-semibold">Совпавшие обязательные навыки</h4><p className="text-sm text-muted-foreground">{match.matched_skills.join(', ') || 'Точных совпадений нет'}</p></div><div className="space-y-2"><h4 className="text-xs font-semibold">Недостающие обязательные навыки</h4><p className="text-sm text-muted-foreground">{match.missing_skills.join(', ') || 'Не указаны'}</p></div></div>
      {match.related_skills.length ? <div className="space-y-2"><h4 className="text-xs font-semibold">Близкие технологии</h4><ul className="space-y-1 text-sm text-muted-foreground">{match.related_skills.map((skill, index) => <li key={index}>Нужен {skill.required} · в профиле {skill.has}</li>)}</ul><p className="text-xs text-muted-foreground">Близкая технология учитывается отдельно от точного совпадения.</p></div> : null}
      {match.breakdown.length ? <details className="rounded-lg border p-4"><summary className="cursor-pointer text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring">Из чего складывается оценка</summary><dl className="mt-4 space-y-3">{match.breakdown.map((part, index) => <div key={`${part.component}-${index}`} className="flex items-baseline justify-between gap-3 text-sm"><dt className="text-muted-foreground">{part.title}</dt><dd className="shrink-0 tabular-nums">{new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(part.points)} / {part.max_points}</dd></div>)}</dl></details> : null}
      {match.contact_status ? <p className="text-xs text-muted-foreground">{contactLabel(match.contact_status)}</p> : null}
    </section>
  )
}

function contactLabel(status: string): string {
  const labels: Record<string, string> = {
    'invitation:pending': 'Приглашение уже отправлено, ожидается ответ.', 'invitation:accepted': 'Кандидат принял приглашение.',
    'invitation:declined': 'Кандидат отказался от приглашения.', 'invitation:withdrawn': 'Приглашение отозвано.',
    'application:new': 'Кандидат уже откликнулся на вашу вакансию.', 'application:viewed': 'Отклик уже просмотрен.',
    'application:invited': 'По отклику уже отправлено приглашение.', 'application:rejected': 'Отклик отклонён.', 'application:withdrawn': 'Кандидат отозвал отклик.',
  }
  return labels[status] ?? 'С кандидатом уже был контакт.'
}
