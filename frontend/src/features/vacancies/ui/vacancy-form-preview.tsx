import { Building2, MapPin } from 'lucide-react'

import { employmentLabels, parseSkills, specializationLabels, type VacancyFormValues } from '@/features/vacancies/model/vacancy-form'
import { formatLabels, gradeLabels, salaryLabel } from '@/features/vacancies/model/vacancy-search'
import { Badge } from '@/shared/ui/badge'

export function VacancyFormPreview({ values, company, full = false }: { values: VacancyFormValues; company: string; full?: boolean }) {
  const skills = parseSkills(values.skills)
  return (
    <article className="space-y-5 rounded-xl border bg-card p-6 shadow-card">
      <p className="flex items-center gap-2 text-sm text-muted-foreground"><Building2 className="size-4" aria-hidden="true" />{company}</p>
      <h2 className="break-words text-2xl font-semibold leading-tight">{values.title.trim() || 'Название вакансии'}</h2>
      <p className="text-lg font-semibold">{salaryLabel(values.salary_from ? Number(values.salary_from) : null, values.salary_to ? Number(values.salary_to) : null, values.currency.toUpperCase() || 'RUB')}</p>
      <div className="flex flex-wrap gap-2">
        <Badge variant="secondary">{gradeLabels[values.grade]}</Badge>
        {values.work_format ? <Badge variant="secondary">{formatLabels[values.work_format]}</Badge> : null}
        {values.employment_type ? <Badge variant="secondary">{employmentLabels[values.employment_type]}</Badge> : null}
      </div>
      <p className="text-sm text-muted-foreground">{specializationLabels[values.specialization]}</p>
      {values.city.trim() ? <p className="flex items-center gap-1 text-sm text-muted-foreground"><MapPin className="size-4" aria-hidden="true" />{values.city}</p> : null}
      {full ? <div className="border-t pt-5"><h3 className="mb-3 font-semibold">О работе</h3><p className="whitespace-pre-wrap break-words text-sm leading-7 text-muted-foreground">{values.description.trim() || 'Здесь появится описание работы.'}</p></div> : null}
      {skills.length ? <div className="flex flex-wrap gap-1.5">{skills.map((skill) => <Badge key={skill} variant="secondary" className="max-w-full break-words whitespace-normal">{skill}</Badge>)}</div> : null}
    </article>
  )
}
