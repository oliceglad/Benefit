import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { RefreshCw, Users } from 'lucide-react'

import { getNeedMatches, matchesKey } from '@/features/talent/api/needs'
import { exclusionLabels } from '@/features/talent/model/need-matches'
import { gradeLabels, roleLabels, talentPageSize, talentSearchSchema } from '@/features/talent/model/talent-search'
import { NeedSummary } from '@/features/talent/ui/need-summary'
import { TalentCandidateCard } from '@/features/talent/ui/talent-candidate-card'
import type { NeedResponse } from '@/shared/api/generated/employers/models'
import { RequestError } from '@/shared/api/ui/request-error'
import { useSession } from '@/shared/session/session'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Checkbox } from '@/shared/ui/checkbox'
import { Spinner } from '@/shared/ui/spinner'

export function NeedMatching({ need, onEdit }: { need: NeedResponse; onEdit: () => void }) {
  const search = talentSearchSchema.parse(useSearch({ strict: false }))
  const userId = useSession().user?.id
  const navigate = useNavigate()
  const query = useQuery({
    queryKey: [...matchesKey(userId, need.id), need.updated_at, search.offset, search.hide_contacted],
    queryFn: ({ signal }) => getNeedMatches(need.id, search.offset, search.hide_contacted, signal),
  })
  function page(offset: number) { void navigate({ to: '/talent', search: { ...search, offset, candidate: undefined }, resetScroll: false }) }
  const data = query.data
  const excluded = Object.entries(data?.excluded ?? {}).filter(([, count]) => count > 0)

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
      <div className="space-y-4"><NeedSummary need={need} onEdit={onEdit} />{excluded.length ? <section aria-label="Причины исключения из подборки" className="space-y-3 rounded-xl border bg-card p-5"><h2 className="text-sm font-semibold">Что сузило подборку</h2><dl className="space-y-2">{excluded.map(([code, count]) => <div key={code} className="flex justify-between gap-3 text-xs leading-5"><dt className="text-muted-foreground">{exclusionLabels[code] ?? 'Другие условия'}</dt><dd className="tabular-nums">{count}</dd></div>)}</dl><p className="text-xs leading-5 text-muted-foreground">Один профиль может не соответствовать нескольким условиям.</p></section> : null}</div>
      <div className="min-w-0 space-y-5" aria-busy={query.isFetching}>
        <div className="flex flex-wrap items-center justify-between gap-3"><div className="space-y-1"><h2 className="text-lg font-semibold">Подборка для команды</h2><p role="status" className="text-sm text-muted-foreground">{query.isPending ? 'Сравниваем профили с требованиями…' : data ? `Подходящих кандидатов: ${data.total}` : 'Подборка недоступна'}</p></div><Button size="sm" variant="outline" disabled={query.isFetching} onClick={() => { void query.refetch() }}><RefreshCw size={14} aria-hidden="true" />Обновить</Button></div>
        <label className="flex items-center gap-2 text-sm"><Checkbox checked={search.hide_contacted} onCheckedChange={(checked) => { void navigate({ to: '/talent', search: { ...search, hide_contacted: checked === true, offset: 0, candidate: undefined }, resetScroll: false }) }} />Скрыть кандидатов, с которыми уже был контакт</label>
        {query.isPending ? <div className="grid min-h-64 place-items-center rounded-xl border bg-card"><Spinner label="Готовим подборку…" /></div> : null}
        {query.isError ? <RequestError error={query.error} onRetry={() => { void query.refetch() }} /> : null}
        {data && !query.isError ? <>
          {data.categories.length ? <section aria-label="Рекомендованные категории" className="space-y-3"><h3 className="text-xs font-semibold text-muted-foreground">Рекомендованные категории</h3><div className="grid gap-3 sm:grid-cols-2">{data.categories.map((category) => <div key={`${category.specialization}-${category.grade}-${category.grade_status}`} className="space-y-2 rounded-lg border bg-card p-4"><div className="flex flex-wrap gap-2"><Badge variant="secondary">{category.grade ? gradeLabels[category.grade] : 'Без грейда'}</Badge><Badge variant="secondary">{category.grade_status === 'confirmed' ? 'Подтверждён' : 'Не подтверждён'}</Badge></div><p className="text-sm font-medium">{category.specialization ? roleLabels[category.specialization] : 'Без специализации'}</p>{category.hint ? <p className="text-xs leading-5 text-muted-foreground">{category.hint}</p> : null}<p className="text-xs text-muted-foreground">Кандидатов: {category.count}{category.best_score != null ? ` · лучший результат ${category.best_score}/100` : ''}</p></div>)}</div></section> : null}
          {search.candidate && !data.candidates.some((item) => item.candidate.user_id === search.candidate) ? <p role="status" className="rounded-lg border bg-card p-4 text-sm text-muted-foreground">Выбранного кандидата нет на этой странице подборки. Условия или профиль могли измениться.</p> : null}
          {data.candidates.length ? <div className="space-y-4">{data.candidates.map((match) => <TalentCandidateCard key={match.candidate.user_id} candidate={match.candidate} match={match} open={search.candidate === match.candidate.user_id} onOpenChange={(open) => { void navigate({ to: '/talent', search: { ...search, candidate: open ? match.candidate.user_id : undefined }, resetScroll: false }) }} />)}</div> : <div className="grid justify-items-center gap-3 rounded-xl border border-dashed bg-card px-6 py-12 text-center"><Users size={28} className="text-muted-foreground" aria-hidden="true" /><h3 className="text-lg font-semibold">{data.total > 0 ? 'На этой странице кандидатов нет' : 'Пока нет подходящих кандидатов'}</h3><p className="max-w-md text-sm leading-6 text-muted-foreground">{data.total > 0 ? 'Вернитесь к началу подборки.' : 'Можно ослабить строгие требования или изменить обязательные навыки. Остальные условия сохранятся в редакторе.'}</p><Button variant="outline" onClick={() => data.total > 0 ? page(0) : onEdit()}>{data.total > 0 ? 'К первой странице' : 'Уточнить потребность'}</Button></div>}
          {data.suggestions.length ? <section aria-label="Как расширить подборку" className="space-y-3 rounded-xl border bg-card p-5"><h3 className="text-sm font-semibold">Как расширить подборку</h3><ul className="space-y-3">{data.suggestions.map((suggestion, index) => <li key={index} className="space-y-1"><p className="text-sm">{suggestion.text}</p><p className="text-xs text-muted-foreground">Возможных дополнительных кандидатов: {suggestion.extra_candidates}</p></li>)}</ul><Button variant="outline" size="sm" onClick={onEdit}>Изменить требования</Button></section> : null}
          {data.total > talentPageSize || search.offset > 0 ? <nav aria-label="Страницы подборки" className="flex flex-wrap items-center justify-center gap-3"><Button variant="outline" disabled={search.offset === 0 || query.isFetching} onClick={() => page(Math.max(0, search.offset - talentPageSize))}>Назад</Button><span className="text-xs text-muted-foreground">{data.candidates.length ? `${search.offset + 1}–${Math.min(search.offset + talentPageSize, data.total)} из ${data.total}` : `Всего: ${data.total}`}</span><Button variant="outline" disabled={search.offset + talentPageSize >= data.total || query.isFetching} onClick={() => page(search.offset + talentPageSize)}>Далее</Button></nav> : null}
        </> : null}
      </div>
    </div>
  )
}
