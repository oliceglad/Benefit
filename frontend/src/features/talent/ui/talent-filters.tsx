import { Search, SlidersHorizontal } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { formatLabels, gradeLabels, roleLabels, talentDefaults, talentSearchSchema, type TalentSearch } from '@/features/talent/model/talent-search'
import { Grade, ITRole, WorkFormat } from '@/shared/api/generated/talent/models'
import { Button } from '@/shared/ui/button'
import { Checkbox } from '@/shared/ui/checkbox'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'

const selectClass = 'h-11 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40'

export function TalentFilters({ value, onApply }: { value: TalentSearch; onApply: (search: TalentSearch) => void }) {
  const [form, setForm] = useState(value)
  function submit(event: FormEvent) {
    event.preventDefault()
    onApply(talentSearchSchema.parse({ ...form, offset: 0, candidate: undefined }))
  }
  return (
    <form onSubmit={submit} className="space-y-5 rounded-xl border bg-card p-5 shadow-card" aria-label="Поиск кандидатов">
      <div className="flex items-center gap-2"><SlidersHorizontal size={18} className="text-muted-foreground" aria-hidden="true" /><h2 className="font-semibold">Поиск и фильтры</h2></div>
      <div className="space-y-2"><Label htmlFor="talent-query">Ключевые слова</Label><Input id="talent-query" value={form.q ?? ''} maxLength={200} placeholder="Должность, опыт, проекты" onChange={(event) => setForm({ ...form, q: event.target.value })} /></div>
      <div className="space-y-2"><Label htmlFor="talent-role">Специализация</Label><select id="talent-role" className={selectClass} value={form.specialization ?? ''} onChange={(event) => setForm({ ...form, specialization: talentSearchSchema.shape.specialization.parse(event.target.value) })}><option value="">Любая</option>{Object.values(ITRole).map((role) => <option key={role} value={role}>{roleLabels[role]}</option>)}</select></div>
      <fieldset className="space-y-2"><legend className="mb-2 text-sm font-medium">Грейд</legend><div className="flex flex-wrap gap-2">{Object.values(Grade).map((grade) => <Button key={grade} type="button" size="sm" variant="outline" aria-pressed={form.grade?.includes(grade) ?? false} className={form.grade?.includes(grade) ? 'border-primary bg-primary/8 text-primary' : ''} onClick={() => setForm({ ...form, grade: form.grade?.includes(grade) ? form.grade.filter((item) => item !== grade) : [...form.grade ?? [], grade] })}>{gradeLabels[grade]}</Button>)}</div></fieldset>
      <div className="space-y-2"><Label htmlFor="talent-confirmation">Подтверждение грейда</Label><select id="talent-confirmation" className={selectClass} value={form.grade_status ?? ''} onChange={(event) => setForm({ ...form, grade_status: talentSearchSchema.shape.grade_status.parse(event.target.value) })}><option value="">Любой статус</option><option value="confirmed">Подтверждён тестом</option><option value="not_confirmed">Ещё не подтверждён</option></select></div>
      <div className="space-y-2 rounded-lg border border-primary/20 bg-primary/5 p-3"><Label htmlFor="talent-fsp">Достижения ФСП</Label><select id="talent-fsp" className={selectClass} value={form.fsp ?? ''} onChange={(event) => setForm({ ...form, fsp: talentSearchSchema.shape.fsp.parse(event.target.value) })}><option value="">Все кандидаты</option><option value="with">Есть подтверждённые</option><option value="without">Нет в доступных данных</option></select><p className="text-xs leading-5 text-muted-foreground">Учитываются сведения, которые кандидат разрешил показывать.</p></div>
      <div className="space-y-2"><Label htmlFor="talent-skills">Стек</Label><Input id="talent-skills" maxLength={500} value={form.skills ?? ''} placeholder="React, TypeScript, SQL" onChange={(event) => setForm({ ...form, skills: event.target.value })} /><p className="text-xs text-muted-foreground">Разделяйте навыки запятой.</p><Label className="sr-only" htmlFor="talent-skills-mode">Совпадение навыков</Label><select id="talent-skills-mode" className={selectClass} value={form.skills_mode} onChange={(event) => setForm({ ...form, skills_mode: talentSearchSchema.shape.skills_mode.parse(event.target.value) })}><option value="all">Все указанные навыки</option><option value="any">Любой из навыков</option></select></div>
      <div className="space-y-2"><Label htmlFor="talent-city">Город</Label><Input id="talent-city" maxLength={100} value={form.city ?? ''} onChange={(event) => setForm({ ...form, city: event.target.value })} /><p className="text-xs leading-5 text-muted-foreground">Также учитываются удалённая работа и готовность к переезду.</p></div>
      <div className="space-y-2"><Label htmlFor="talent-format">Формат работы</Label><select id="talent-format" className={selectClass} value={form.work_format ?? ''} onChange={(event) => setForm({ ...form, work_format: talentSearchSchema.shape.work_format.parse(event.target.value) })}><option value="">Любой</option>{Object.values(WorkFormat).map((format) => <option key={format} value={format}>{formatLabels[format]}</option>)}</select></div>
      <div className="space-y-2"><Label htmlFor="talent-experience">Опыт от, лет</Label><Input id="talent-experience" type="number" min={0} max={50} step={0.5} value={form.experience_min ?? ''} onChange={(event) => setForm({ ...form, experience_min: talentSearchSchema.shape.experience_min.parse(event.target.value) })} /></div>
      <div className="space-y-3"><label className="flex items-center gap-2 text-sm"><Checkbox checked={form.active_only} onCheckedChange={(value) => setForm({ ...form, active_only: value === true })} />Активны за последние 30 дней</label><label className="flex items-center gap-2 text-sm"><Checkbox checked={form.include_not_looking} onCheckedChange={(value) => setForm({ ...form, include_not_looking: value === true })} />Включить тех, кто не ищет работу</label></div>
      <div className="space-y-2"><Button className="w-full" type="submit"><Search size={16} aria-hidden="true" />Найти кандидатов</Button><Button className="w-full" type="button" variant="ghost" onClick={() => { setForm(talentDefaults); onApply(talentDefaults) }}>Сбросить фильтры</Button></div>
    </form>
  )
}
