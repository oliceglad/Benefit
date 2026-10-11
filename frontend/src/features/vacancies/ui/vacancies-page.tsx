import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import { BriefcaseBusiness, Plus, RotateCcw, Search, SlidersHorizontal, X } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'

import { employerVacancyEmptyCopy } from '@/features/vacancies/model/employer-vacancy-empty'
import { listOwnVacancies, listVacancies } from '@/features/vacancies/api/vacancies'
import { formatLabels, gradeLabels, vacancyPageSize, vacancySearchSchema, type VacancySearch } from '@/features/vacancies/model/vacancy-search'
import { EmployerVacancyList } from '@/features/vacancies/ui/employer-vacancy-list'
import { VacancyCard } from '@/features/vacancies/ui/vacancy-card'
import { RequestError } from '@/shared/api/ui/request-error'
import { useSession } from '@/shared/session/session'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'
import { Spinner } from '@/shared/ui/spinner'

export function VacanciesPage() {
  const employer = useSession().user?.role === 'employer'
  const search = vacancySearchSchema.parse(useSearch({ strict: false }))
  const navigate = useNavigate()
  const query = useQuery({
    queryKey: ['vacancies', employer ? 'own' : 'catalog', search],
    queryFn: async ({ signal }) => {
      if (!employer) {
        const catalogSearch = { q: search.q, city: search.city, grade: search.grade, work_format: search.work_format, salary_min: search.salary_min, offset: search.offset }
        return { ...await listVacancies({ ...catalogSearch, limit: vacancyPageSize }, signal), statusCounts: null }
      }
      const all = await listOwnVacancies(signal)
      const filtered = all.filter((vacancy) => (
        (!search.q || `${vacancy.title} ${vacancy.description}`.toLocaleLowerCase('ru').includes(search.q.toLocaleLowerCase('ru')))
        && (!search.city || vacancy.city?.toLocaleLowerCase('ru').includes(search.city.toLocaleLowerCase('ru')))
        && (!search.grade || vacancy.grade === search.grade)
        && (!search.work_format || vacancy.work_format === search.work_format)
        && (!search.status || vacancy.status === search.status)
        && (search.salary_min == null || (vacancy.salary_to ?? vacancy.salary_from ?? 0) >= search.salary_min)
      ))
      return {
        total: filtered.length,
        items: filtered.slice(search.offset, search.offset + vacancyPageSize),
        statusCounts: {
          all: all.length,
          draft: all.filter((item) => item.status === 'draft').length,
          published: all.filter((item) => item.status === 'published').length,
          closed: all.filter((item) => item.status === 'closed').length,
        },
      }
    },
  })

  function changeSearch(next: VacancySearch): void { void navigate({ to: '/vacancies', search: next }) }
  const hasFilters = Boolean(search.q || search.city || search.grade || search.work_format || search.salary_min != null)

  const results = query.data ? (
    <>
      <div className="flex items-center justify-between gap-3 border-t px-4 py-3 text-sm text-muted-foreground sm:px-5">
        <p role="status">Найдено: <span className="font-semibold text-foreground">{query.data.total}</span></p>
        {query.data.items.length ? <span className="text-xs">{search.offset + 1}–{Math.min(search.offset + vacancyPageSize, query.data.total)}</span> : null}
      </div>
      {query.data.items.length ? (
        employer ? <EmployerVacancyList vacancies={query.data.items} /> : <div className="grid gap-5 md:grid-cols-2">{query.data.items.map((vacancy) => <VacancyCard key={vacancy.id} vacancy={vacancy} />)}</div>
      ) : employer ? (
        <EmployerVacancyEmptyState allCount={query.data.statusCounts?.all ?? 0} status={search.status} hasFilters={hasFilters} onReset={() => changeSearch({ offset: 0 })} />
      ) : (
        <div className="grid justify-items-center gap-3 border-t px-6 py-10 text-center"><BriefcaseBusiness className="size-8 text-muted-foreground" aria-hidden="true" /><h2 className="text-xl font-semibold">{query.data.total ? 'На этой странице вакансий нет' : 'Вакансий пока нет'}</h2><p className="max-w-md text-sm leading-6 text-muted-foreground">Попробуйте другие условия поиска или вернитесь позже.</p>{hasFilters ? <Button variant="outline" onClick={() => changeSearch({ offset: 0 })}>Сбросить фильтры</Button> : null}</div>
      )}
      {query.data.total > vacancyPageSize || search.offset > 0 ? <Pagination search={search} total={query.data.total} fetching={query.isFetching} onChange={changeSearch} /> : null}
    </>
  ) : null

  return (
    <section className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-2xl space-y-1.5">
          {!employer ? <p className="text-sm font-medium text-primary">Новая глава вашей карьеры</p> : null}
          <h1 className="text-3xl font-semibold tracking-tight">{employer ? 'Мои вакансии' : 'Вакансии'}</h1>
          <p className="text-sm text-muted-foreground">{employer ? 'Управляйте публикациями и быстро находите нужную вакансию.' : 'Найдите команду, в которой пригодятся ваши навыки.'}</p>
        </div>
        {employer ? <Button asChild><Link to="/vacancies/new"><Plus aria-hidden="true" />Создать вакансию</Link></Button> : null}
      </header>

      <div className={employer ? 'overflow-hidden rounded-2xl border bg-card' : 'space-y-5'}>
        {employer ? <StatusTabs search={search} counts={query.data?.statusCounts ?? null} onChange={changeSearch} /> : null}
        <VacancyFilters key={JSON.stringify(search)} value={search} employer={employer} embedded={employer} onApply={changeSearch} />
        {query.isPending ? <div className="grid min-h-64 place-items-center border-t"><Spinner label="Загружаем вакансии…" /></div> : null}
        {query.isError ? <div className={employer ? 'border-t p-5' : ''}><RequestError error={query.error} onRetry={() => { void query.refetch() }} /></div> : null}
        {results}
      </div>
    </section>
  )
}

function StatusTabs({ search, counts, onChange }: { search: VacancySearch; counts: { all: number; draft: number; published: number; closed: number } | null; onChange: (value: VacancySearch) => void }) {
  return <nav aria-label="Статусы вакансий" className="flex gap-1 overflow-x-auto border-b p-2">{(['all', 'published', 'draft', 'closed'] as const).map((status) => {
    const active = (search.status ?? 'all') === status
    return <Button key={status} variant="ghost" aria-pressed={active} size="sm" className={`shrink-0 whitespace-nowrap ${active ? 'bg-primary/10 text-primary' : 'text-muted-foreground'}`} onClick={() => onChange({ ...search, status: status === 'all' ? undefined : status, offset: 0 })}>{{ all: 'Все', published: 'Опубликованные', draft: 'Черновики', closed: 'Закрытые' }[status]}{counts ? <span className="ml-1 rounded-md bg-background/80 px-1.5 text-xs tabular-nums">{counts[status]}</span> : null}</Button>
  })}</nav>
}

function VacancyFilters({ value, employer, embedded, onApply }: { value: VacancySearch; employer: boolean; embedded: boolean; onApply: (value: VacancySearch) => void }) {
  const [q, setQ] = useState(value.q ?? '')
  const [city, setCity] = useState(value.city ?? '')
  const [grade, setGrade] = useState<string>(value.grade ?? '')
  const [format, setFormat] = useState<string>(value.work_format ?? '')
  const [salary, setSalary] = useState(value.salary_min?.toString() ?? '')
  const [filtersOpen, setFiltersOpen] = useState(!employer && Boolean(value.city || value.grade || value.work_format || value.salary_min != null))
  const active = Boolean(value.q || value.city || value.grade || value.work_format || value.salary_min != null)

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    onApply(vacancySearchSchema.parse({ q, city, grade: grade || undefined, work_format: format || undefined, salary_min: salary || undefined, offset: 0, status: value.status }))
  }
  const chips: ReactNode[] = []
  if (value.q) chips.push(<Badge key="q" variant="secondary">Поиск: {value.q}</Badge>)
  if (value.grade) chips.push(<Badge key="grade" variant="secondary">{gradeLabels[value.grade]}</Badge>)
  if (value.work_format) chips.push(<Badge key="format" variant="secondary">{formatLabels[value.work_format]}</Badge>)
  if (value.city) chips.push(<Badge key="city" variant="secondary">Город: {value.city}</Badge>)
  if (value.salary_min != null) chips.push(<Badge key="salary" variant="secondary">От {new Intl.NumberFormat('ru-RU').format(value.salary_min)} ₽</Badge>)

  return (
    <form onSubmit={submit} className={embedded ? 'p-3 sm:p-4' : 'rounded-2xl border bg-card p-3 sm:p-4'}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative w-full sm:max-w-md"><Search className="pointer-events-none absolute left-3 top-3.5 size-4 text-muted-foreground" aria-hidden="true" /><Input aria-label={employer ? 'Поиск по своим вакансиям' : 'Поиск вакансий'} className="pl-9" maxLength={100} placeholder={employer ? 'Название или описание' : 'Например, Python-разработчик'} value={q} onChange={(event) => setQ(event.target.value)} /></div>
        <div className="flex gap-2"><Button type="submit" size="sm" className="min-h-11"><Search aria-hidden="true" />Найти</Button><Button type="button" size="sm" variant="outline" className="min-h-11" aria-expanded={filtersOpen} aria-controls="vacancy-extra-filters" onClick={() => setFiltersOpen((open) => !open)}><SlidersHorizontal aria-hidden="true" />Фильтры{active ? <span className="size-2 rounded-full bg-primary" aria-label="Есть активные фильтры" /> : null}</Button></div>
      </div>
      {chips.length ? <div className="mt-3 flex flex-wrap items-center gap-2">{chips}<Button type="button" variant="ghost" size="sm" onClick={() => onApply({ status: value.status, offset: 0 })}><X aria-hidden="true" />Сбросить</Button></div> : null}
      {filtersOpen ? <div id="vacancy-extra-filters" className="mt-4 grid gap-4 border-t pt-4 sm:grid-cols-2 lg:grid-cols-4">
        <FilterSelect id="vacancy-grade" label="Грейд" value={grade} onChange={setGrade} options={gradeLabels} />
        <FilterSelect id="vacancy-format" label="Формат работы" value={format} onChange={setFormat} options={formatLabels} />
        <div className="space-y-2"><Label htmlFor="vacancy-city">Город</Label><Input id="vacancy-city" maxLength={100} value={city} placeholder="Любой город" onChange={(event) => setCity(event.target.value)} /></div>
        <div className="space-y-2"><Label htmlFor="vacancy-salary">Зарплата от, ₽</Label><Input id="vacancy-salary" type="number" min={0} max={100000000} step={1} value={salary} placeholder="Неважно" onChange={(event) => setSalary(event.target.value)} /></div>
        <div className="flex gap-2 sm:col-span-2 lg:col-span-4"><Button type="submit" size="sm">Применить</Button>{active ? <Button type="button" variant="ghost" size="sm" onClick={() => onApply({ status: value.status, offset: 0 })}><RotateCcw aria-hidden="true" />Сбросить</Button> : null}</div>
      </div> : null}
    </form>
  )
}

function FilterSelect({ id, label, value, onChange, options }: { id: string; label: string; value: string; onChange: (value: string) => void; options: Record<string, string> }) {
  return <div className="space-y-2"><Label htmlFor={id}>{label}</Label><Select value={value || 'any'} onValueChange={(next) => onChange(next === 'any' ? '' : next)}><SelectTrigger id={id}><SelectValue /></SelectTrigger><SelectContent><SelectItem value="any">Любой</SelectItem>{Object.entries(options).map(([option, title]) => <SelectItem key={option} value={option}>{title}</SelectItem>)}</SelectContent></Select></div>
}

function EmployerVacancyEmptyState({ allCount, status, hasFilters, onReset }: { allCount: number; status: VacancySearch['status']; hasFilters: boolean; onReset: () => void }) {
  const { title, description } = employerVacancyEmptyCopy(allCount, status, hasFilters)
  return <div className="grid justify-items-center gap-3 border-t px-6 py-10 text-center"><BriefcaseBusiness className="size-8 text-muted-foreground" aria-hidden="true" /><h2 className="text-lg font-semibold">{title}</h2><p className="max-w-md text-sm leading-6 text-muted-foreground">{description}</p>{allCount === 0 ? <Button asChild><Link to="/vacancies/new"><Plus aria-hidden="true" />Создать вакансию</Link></Button> : null}{allCount > 0 && (hasFilters || status) ? <Button variant="outline" onClick={onReset}><RotateCcw aria-hidden="true" />Сбросить фильтры</Button> : null}</div>
}

function Pagination({ search, total, fetching, onChange }: { search: VacancySearch; total: number; fetching: boolean; onChange: (value: VacancySearch) => void }) {
  return <nav aria-label="Страницы вакансий" className="flex justify-center gap-3 border-t p-4"><Button variant="outline" disabled={search.offset === 0 || fetching} onClick={() => onChange({ ...search, offset: Math.max(0, search.offset - vacancyPageSize) })}>Назад</Button><Button variant="outline" disabled={search.offset + vacancyPageSize >= total || fetching} onClick={() => onChange({ ...search, offset: search.offset + vacancyPageSize })}>Далее</Button></nav>
}
