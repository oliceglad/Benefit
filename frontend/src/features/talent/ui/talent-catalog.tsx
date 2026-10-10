import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { Users } from 'lucide-react'
import type { ReactNode } from 'react'
import type { CandidateCard } from '@/shared/api/generated/talent/models'

import { searchCandidates } from '@/features/talent/api/talent'
import { gradeLabels, roleLabels, sortLabels, talentDefaults, talentPageSize, talentRequest, talentSearchSchema, type TalentSearch } from '@/features/talent/model/talent-search'
import { TalentCandidateCard } from '@/features/talent/ui/talent-candidate-card'
import { TalentFilters } from '@/features/talent/ui/talent-filters'
import { RequestError } from '@/shared/api/ui/request-error'
import { useSession } from '@/shared/session/session'
import { Button } from '@/shared/ui/button'
import { Label } from '@/shared/ui/label'
import { Spinner } from '@/shared/ui/spinner'

export function TalentCatalog({ candidateActions }: { candidateActions?: (candidate: CandidateCard) => ReactNode }) {
  const search = talentSearchSchema.parse(useSearch({ strict: false }))
  const navigate = useNavigate()
  const userId = useSession().user?.id
  const params = talentRequest(search)
  const query = useQuery({
    queryKey: ['talent', userId, params],
    queryFn: ({ signal }) => searchCandidates(params, signal),
  })
  function changeSearch(next: TalentSearch) { void navigate({ to: '/talent', search: next, resetScroll: false }) }

  return (
      <div className="grid items-start gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <TalentFilters key={JSON.stringify({ ...search, candidate: undefined })} value={search} onApply={changeSearch} />
        <div className="min-w-0 space-y-5" aria-busy={query.isFetching}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p role="status" className="text-sm text-muted-foreground">{query.isPending ? 'Ищем кандидатов…' : query.data ? <>Найдено кандидатов: <strong className="text-foreground">{query.data.total}</strong></> : 'Поиск недоступен'}</p>
            <div className="flex items-center gap-2"><Label htmlFor="talent-sort" className="sr-only">Сортировка кандидатов</Label><select id="talent-sort" className="h-10 max-w-full rounded-lg border border-input bg-card px-3 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40" value={search.sort} onChange={(event) => changeSearch({ ...search, sort: talentSearchSchema.shape.sort.parse(event.target.value), offset: 0, candidate: undefined })}>{Object.entries(sortLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
          </div>
          {search.sort === 'fsp' ? <p className="text-xs leading-5 text-muted-foreground">Сначала кандидаты с большим числом доступных достижений ФСП, затем — с более свежей активностью.</p> : null}
          {query.isPending ? <div className="grid min-h-64 place-items-center rounded-xl border bg-card"><Spinner label="Загружаем кандидатов…" /></div> : null}
          {query.isError ? <RequestError error={query.error} onRetry={() => { void query.refetch() }} /> : null}
          {query.data && !query.isError ? <>
            {query.data.categories.length ? <section aria-label="Категории в найденной выборке" className="space-y-2"><h2 className="text-xs font-medium text-muted-foreground">Категории в найденной выборке</h2><div className="flex flex-wrap gap-2">{query.data.categories.map((category) => <Button key={`${category.specialization}-${category.grade}-${category.grade_status}`} type="button" variant="outline" size="sm" className="h-auto min-h-9 whitespace-normal text-left text-xs" onClick={() => changeSearch({ ...search, specialization: category.specialization ?? undefined, grade: category.grade ? [category.grade] : undefined, grade_status: talentSearchSchema.shape.grade_status.parse(category.grade_status), offset: 0, candidate: undefined })}>{category.specialization ? roleLabels[category.specialization] : 'Без специализации'} · {category.grade ? gradeLabels[category.grade] : 'Без грейда'} · {category.grade_status === 'confirmed' ? 'Подтверждён' : 'Не подтверждён'}<span className="rounded bg-muted px-1.5 tabular-nums">{category.count}</span></Button>)}</div></section> : null}
            {search.candidate && !query.data.items.some((candidate) => candidate.user_id === search.candidate) ? <p role="status" className="rounded-lg border bg-card p-4 text-sm text-muted-foreground">Выбранного кандидата нет на этой странице выдачи. Он мог изменить профиль или перестать соответствовать фильтрам.</p> : null}
            {query.data.items.length ? <div className="space-y-4">{query.data.items.map((candidate) => <TalentCandidateCard key={candidate.user_id} candidate={candidate} actions={candidateActions?.(candidate)} open={search.candidate === candidate.user_id} onOpenChange={(open) => changeSearch({ ...search, candidate: open ? candidate.user_id : undefined })} />)}</div> : <div className="grid justify-items-center gap-3 rounded-xl border border-dashed bg-card px-6 py-14 text-center"><Users size={30} className="text-muted-foreground" aria-hidden="true" /><h2 className="text-xl font-semibold">{query.data.total > 0 ? 'На этой странице кандидатов нет' : 'Кандидаты не найдены'}</h2><p className="max-w-md text-sm leading-6 text-muted-foreground">{search.fsp === 'with' ? 'В доступной базе нет кандидатов с подтверждёнными достижениями ФСП, соответствующих выбранным условиям.' : 'Попробуйте расширить условия поиска. Здесь появляются опубликованные профили кандидатов.'}</p><Button variant="outline" onClick={() => changeSearch(talentDefaults)}>Сбросить фильтры</Button></div>}
            {query.data.total > talentPageSize || search.offset > 0 ? <nav aria-label="Страницы кандидатов" className="flex flex-wrap items-center justify-center gap-3"><Button variant="outline" disabled={search.offset === 0 || query.isFetching} onClick={() => changeSearch({ ...search, offset: Math.max(0, search.offset - talentPageSize), candidate: undefined })}>Назад</Button><span className="text-xs text-muted-foreground">{query.data.items.length ? `${search.offset + 1}–${Math.min(search.offset + talentPageSize, query.data.total)} из ${query.data.total}` : `Всего: ${query.data.total}`}</span><Button variant="outline" disabled={search.offset + talentPageSize >= query.data.total || query.isFetching} onClick={() => changeSearch({ ...search, offset: search.offset + talentPageSize, candidate: undefined })}>Далее</Button></nav> : null}
          </> : null}
        </div>
      </div>
  )
}
