import { Search, SlidersHorizontal } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { formatLabels, gradeLabels, industryLabels, roleLabels, talentDefaults, talentSearchSchema, type TalentSearch } from '@/features/talent/model/talent-search'
import { Grade, Industry, ITRole, WorkFormat } from '@/shared/api/generated/talent/models'
import { Button } from '@/shared/ui/button'
import { Checkbox } from '@/shared/ui/checkbox'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'

const selectClass = 'h-11 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40'

export function TalentFilters({ value, onApply }: { value: TalentSearch; onApply: (search: TalentSearch) => void }) {
  const [form, setForm] = useState(value)
  const [error, setError] = useState('')
  function submit(event: FormEvent) {
    event.preventDefault()
    if (form.experience_min != null && form.experience_max != null && form.experience_min > form.experience_max) {
      setError('Максимальный опыт должен быть не меньше минимального.')
      return
    }
    setError('')
    onApply(talentSearchSchema.parse({ ...form, sort: value.sort, offset: 0, candidate: undefined }))
  }
  return (
    <form onSubmit={submit} className="space-y-5 rounded-xl border bg-card p-5 shadow-card" aria-label="Поиск кандидатов">
      <div className="flex items-center gap-2"><SlidersHorizontal size={18} className="text-muted-foreground" aria-hidden="true" /><h2 className="font-semibold">Поиск и фильтры</h2></div>
      <div className="space-y-2"><Label htmlFor="talent-query">Ключевые слова</Label><Input id="talent-query" value={form.q ?? ''} maxLength={200} placeholder="Должность, опыт, проекты" onChange={(event) => setForm({ ...form, q: event.target.value })} /></div>
      <div className="space-y-2"><Label htmlFor="talent-role">Специализация</Label><select id="talent-role" className={selectClass} value={form.specialization ?? ''} onChange={(event) => setForm({ ...form, specialization: talentSearchSchema.shape.specialization.parse(event.target.value) })}><option value="">Любая</option>{Object.values(ITRole).map((role) => <option key={role} value={role}>{roleLabels[role]}</option>)}</select></div>
      <fieldset className="space-y-2"><legend className="mb-2 text-sm font-medium">Грейд</legend><div className="flex flex-wrap gap-2">{Object.values(Grade).map((grade) => <Button key={grade} type="button" size="sm" variant="outline" aria-pressed={form.grade?.includes(grade) ?? false} className={form.grade?.includes(grade) ? 'border-primary bg-primary/8 text-primary' : ''} onClick={() => setForm({ ...form, grade: form.grade?.includes(grade) ? form.grade.filter((item) => item !== grade) : [...form.grade ?? [], grade] })}>{gradeLabels[grade]}</Button>)}</div></fieldset>
      <div className="space-y-2"><Label htmlFor="talent-confirmation">Подтверждение грейда</Label><select id="talent-confirmation" className={selectClass} value={form.grade_status} onChange={(event) => setForm({ ...form, grade_status: talentSearchSchema.shape.grade_status.parse(event.target.value) })}><option value="confirmed">Подтверждён тестом</option><option value="all">Все статусы</option><option value="not_confirmed">Ещё не подтверждён</option></select><p className="text-xs leading-5 text-muted-foreground">Начинаем с квалификации, подтверждённой тестированием.</p></div>
      <div className="space-y-2 rounded-lg border border-primary/20 bg-primary/5 p-3"><Label htmlFor="talent-fsp">Достижения ФСП</Label><select id="talent-fsp" className={selectClass} value={form.fsp ?? ''} onChange={(event) => setForm({ ...form, fsp: talentSearchSchema.shape.fsp.parse(event.target.value) })}><option value="">Все кандидаты</option><option value="with">Есть подтверждённые</option><option value="without">Нет в доступных данных</option></select><p className="text-xs leading-5 text-muted-foreground">Учитываются сведения, которые кандидат разрешил показывать.</p></div>
      <div className="space-y-2"><Label htmlFor="talent-skills">Стек</Label><Input id="talent-skills" maxLength={500} value={form.skills ?? ''} placeholder="React, TypeScript, SQL" onChange={(event) => setForm({ ...form, skills: event.target.value })} /><p className="text-xs text-muted-foreground">Разделяйте навыки запятой.</p><Label className="sr-only" htmlFor="talent-skills-mode">Совпадение навыков</Label><select id="talent-skills-mode" className={selectClass} value={form.skills_mode} onChange={(event) => setForm({ ...form, skills_mode: talentSearchSchema.shape.skills_mode.parse(event.target.value) })}><option value="all">Все указанные навыки</option><option value="any">Любой из навыков</option></select></div>
      <details className="group border-t pt-4" open={Boolean(value.city || value.work_format || value.industry || value.salary_max != null || value.experience_min != null || value.experience_max != null || value.active_only || value.include_not_looking || error)}>
        <summary className="cursor-pointer text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring">Условия, опыт и активность</summary>
        <div className="mt-4 space-y-4">
          <div className="space-y-2"><Label htmlFor="talent-industry">Отрасль</Label><select id="talent-industry" className={selectClass} value={form.industry ?? ''} onChange={(event) => setForm({ ...form, industry: talentSearchSchema.shape.industry.parse(event.target.value) })}><option value="">Любая отрасль</option>{Object.values(Industry).map((industry) => <option key={industry} value={industry}>{industryLabels[industry]}</option>)}</select></div>
          <div className="space-y-2"><Label htmlFor="talent-city">Город</Label><Input id="talent-city" maxLength={100} value={form.city ?? ''} onChange={(event) => setForm({ ...form, city: event.target.value })} /><p className="text-xs leading-5 text-muted-foreground">Также учитываются удалённая работа и готовность к переезду.</p></div>
          <div className="space-y-2"><Label htmlFor="talent-format">Формат работы</Label><select id="talent-format" className={selectClass} value={form.work_format ?? ''} onChange={(event) => setForm({ ...form, work_format: talentSearchSchema.shape.work_format.parse(event.target.value) })}><option value="">Любой</option>{Object.values(WorkFormat).map((format) => <option key={format} value={format}>{formatLabels[format]}</option>)}</select></div>
          <fieldset className="space-y-2"><legend className="text-sm font-medium">Опыт работы, лет</legend><div className="grid grid-cols-2 gap-3">
            <div className="space-y-1"><Label htmlFor="talent-experience" className="text-xs text-muted-foreground">От</Label><Input id="talent-experience" type="number" min={0} max={50} step={0.5} value={form.experience_min ?? ''} onChange={(event) => setForm({ ...form, experience_min: talentSearchSchema.shape.experience_min.parse(event.target.value) })} /></div>
            <div className="space-y-1"><Label htmlFor="talent-experience-max" className="text-xs text-muted-foreground">До</Label><Input id="talent-experience-max" type="number" min={0} max={50} step={0.5} value={form.experience_max ?? ''} aria-invalid={Boolean(error)} aria-describedby={error ? 'talent-filter-error' : undefined} onChange={(event) => setForm({ ...form, experience_max: talentSearchSchema.shape.experience_max.parse(event.target.value) })} /></div>
          </div></fieldset>
          <div className="space-y-2"><Label htmlFor="talent-budget">Зарплатные ожидания до, ₽</Label><Input id="talent-budget" type="number" min={0} max={100_000_000} step={1000} value={form.salary_max ?? ''} onChange={(event) => setForm({ ...form, salary_max: talentSearchSchema.shape.salary_max.parse(event.target.value) })} /><p className="text-xs leading-5 text-muted-foreground">Ограничение ожиданий кандидата. Условия приглашения задаются отдельно.</p></div>
          <div className="space-y-3"><label className="flex items-start gap-2 text-sm"><Checkbox className="mt-0.5" checked={form.active_only} onCheckedChange={(value) => setForm({ ...form, active_only: value === true })} />Активны за последние 30 дней</label><label className="flex items-start gap-2 text-sm"><Checkbox className="mt-0.5" checked={form.include_not_looking} onCheckedChange={(value) => setForm({ ...form, include_not_looking: value === true })} />Включить тех, кто не ищет работу</label></div>
        </div>
      </details>
      {error ? <p id="talent-filter-error" role="alert" className="text-xs text-destructive">{error}</p> : null}
      <div className="space-y-2 border-t pt-4"><Button className="w-full" type="submit"><Search size={16} aria-hidden="true" />Применить фильтры</Button><Button className="w-full" type="button" variant="ghost" onClick={() => { setForm(talentDefaults); setError(''); onApply(talentDefaults) }}>Сбросить фильтры</Button></div>
    </form>
  )
}
