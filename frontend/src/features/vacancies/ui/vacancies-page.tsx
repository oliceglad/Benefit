import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import { BriefcaseBusiness, Plus, Search, SlidersHorizontal } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { listOwnVacancies, listVacancies } from '@/features/vacancies/api/vacancies'
import {
  formatLabels,
  gradeLabels,
  vacancyPageSize,
  vacancySearchSchema,
  type VacancySearch,
} from '@/features/vacancies/model/vacancy-search'
import { VacancyCard } from '@/features/vacancies/ui/vacancy-card'
import { EmployerVacancyList } from '@/features/vacancies/ui/employer-vacancy-list'
import { RequestError } from '@/shared/api/ui/request-error'
import { useSession } from '@/shared/session/session'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
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
      return { total: filtered.length, items: filtered.slice(search.offset, search.offset + vacancyPageSize), statusCounts: {
        all: all.length, draft: all.filter((item) => item.status === 'draft').length,
        published: all.filter((item) => item.status === 'published').length, closed: all.filter((item) => item.status === 'closed').length,
      } }
    },
  })

  function changeSearch(next: VacancySearch) {
    void navigate({ to: '/vacancies', search: next })
  }

  return (
    <section className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-2xl space-y-2">
          <p className="text-sm font-medium text-primary">{employer ? 'Подбор команды' : 'Новая глава вашей карьеры'}</p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{employer ? 'Мои вакансии' : 'Вакансии'}</h1>
          <p className="text-muted-foreground">
            {employer ? 'Все вакансии компании: черновики, опубликованные и закрытые.' : 'Найдите команду, в которой пригодятся ваши навыки.'}
          </p>
        </div>
        {employer ? (
          <div className="flex flex-wrap gap-2"><Button asChild variant="outline"><Link to="/pipelines">Пайплайны</Link></Button><Button asChild><Link to="/vacancies/new"><Plus aria-hidden="true" />Создать вакансию</Link></Button></div>
        ) : null}
      </header>
      <VacancyFilters key={JSON.stringify(search)} value={search} onApply={changeSearch} />
      {employer ? (
        <nav aria-label="Статусы вакансий" className="flex flex-wrap gap-1 border-b pb-2">
          {(['all', 'published', 'draft', 'closed'] as const).map((status) => (
            <Button
              key={status}
              variant="ghost"
              aria-pressed={(search.status ?? 'all') === status}
              className={(search.status ?? 'all') === status ? 'bg-primary/8 text-primary' : 'text-muted-foreground'}
              onClick={() => changeSearch({ ...search, status: status === 'all' ? undefined : status, offset: 0 })}
            >
              {{ all: 'Все', published: 'Опубликованные', draft: 'Черновики', closed: 'Закрытые' }[status]}
              {query.data?.statusCounts ? (
                <span className="ml-1 rounded bg-muted px-1.5 text-xs tabular-nums">{query.data.statusCounts[status]}</span>
              ) : null}
            </Button>
          ))}
        </nav>
      ) : null}
      {query.isPending ? (
        <div className="grid min-h-64 place-items-center"><Spinner label="Загружаем вакансии…" /></div>
      ) : null}
      {query.isError ? <RequestError error={query.error} onRetry={() => { void query.refetch() }} /> : null}
      {query.data ? (
        <>
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground" role="status">
              Найдено вакансий: <span className="font-semibold text-foreground">{query.data.total}</span>
            </p>
            {query.data.items.length > 0 ? (
              <span className="text-xs text-muted-foreground">{search.offset + 1}–{Math.min(search.offset + vacancyPageSize, query.data.total)}</span>
            ) : null}
          </div>
          {query.data.items.length ? (
            employer ? <EmployerVacancyList vacancies={query.data.items} /> : <div className="grid gap-5 md:grid-cols-2">
              {query.data.items.map((vacancy) => <VacancyCard key={vacancy.id} vacancy={vacancy} employer={employer} />)}
            </div>
          ) : (
            <div className="grid justify-items-center gap-3 rounded-2xl border border-dashed bg-card px-6 py-16 text-center">
              <BriefcaseBusiness className="size-8 text-muted-foreground" aria-hidden="true" />
              <h2 className="text-xl font-semibold">{query.data.total ? 'На этой странице вакансий нет' : 'Вакансий пока нет'}</h2>
              <p className="max-w-md text-sm leading-6 text-muted-foreground">
                {employer ? 'Здесь появятся вакансии вашей компании. Попробуйте изменить фильтры.' : 'Попробуйте другие условия поиска или вернитесь позже.'}
              </p>
              <Button variant="outline" onClick={() => changeSearch({ offset: 0 })}>Сбросить фильтры</Button>
              {employer ? <Button asChild><Link to="/vacancies/new"><Plus aria-hidden="true" />Создать вакансию</Link></Button> : null}
            </div>
          )}
          {query.data.total > vacancyPageSize || search.offset > 0 ? (
            <nav aria-label="Страницы вакансий" className="flex justify-center gap-3">
              <Button
                variant="outline"
                disabled={search.offset === 0 || query.isFetching}
                onClick={() => changeSearch({ ...search, offset: Math.max(0, search.offset - vacancyPageSize) })}
              >
                Назад
              </Button>
              <Button
                variant="outline"
                disabled={search.offset + vacancyPageSize >= query.data.total || query.isFetching}
                onClick={() => changeSearch({ ...search, offset: search.offset + vacancyPageSize })}
              >
                Далее
              </Button>
            </nav>
          ) : null}
        </>
      ) : null}
    </section>
  )
}

function VacancyFilters({ value, onApply }: { value: VacancySearch; onApply: (value: VacancySearch) => void }) {
  const [q, setQ] = useState(value.q ?? '')
  const [city, setCity] = useState(value.city ?? '')
  const [grade, setGrade] = useState<string>(value.grade ?? '')
  const [format, setFormat] = useState<string>(value.work_format ?? '')
  const [salary, setSalary] = useState(value.salary_min?.toString() ?? '')

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onApply(vacancySearchSchema.parse({
      q, city, grade: grade || undefined, work_format: format || undefined,
      salary_min: salary || undefined, offset: 0,
      status: value.status,
    }))
  }

  const selectClass = 'min-h-12 w-full rounded-xl border border-input bg-background px-3 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/35'
  return (
    <form onSubmit={submit} className="space-y-4 rounded-2xl border bg-card p-5 shadow-card">
      <div className="flex items-center gap-2 text-sm font-semibold"><SlidersHorizontal className="size-4" aria-hidden="true" />Поиск и фильтры</div>
      <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
        <div className="space-y-2">
          <Label htmlFor="vacancy-query">Должность или ключевые слова</Label>
          <Input id="vacancy-query" maxLength={100} placeholder="Например, Python-разработчик" value={q} onChange={(event) => setQ(event.target.value)} />
        </div>
        <Button className="self-end" type="submit"><Search aria-hidden="true" />Найти вакансии</Button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-2">
          <Label htmlFor="vacancy-grade">Грейд</Label>
          <select id="vacancy-grade" className={selectClass} value={grade} onChange={(event) => setGrade(event.target.value)}>
            <option value="">Любой</option>
            {Object.entries(gradeLabels).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="vacancy-format">Формат работы</Label>
          <select id="vacancy-format" className={selectClass} value={format} onChange={(event) => setFormat(event.target.value)}>
            <option value="">Любой</option>
            {Object.entries(formatLabels).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="vacancy-city">Город</Label>
          <Input id="vacancy-city" maxLength={100} value={city} placeholder="Любой город" onChange={(event) => setCity(event.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="vacancy-salary">Зарплата от, ₽</Label>
          <Input id="vacancy-salary" type="number" min={0} max={100000000} step={1} value={salary} placeholder="Неважно" onChange={(event) => setSalary(event.target.value)} />
        </div>
      </div>
    </form>
  )
}
