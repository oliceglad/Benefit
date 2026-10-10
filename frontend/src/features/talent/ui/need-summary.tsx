import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Pencil } from 'lucide-react'
import { useState } from 'react'

import { needKey, needsKey, setNeedStatus } from '@/features/talent/api/needs'
import { formatLabels, gradeLabels, roleLabels } from '@/features/talent/model/talent-search'
import type { NeedResponse } from '@/shared/api/generated/employers/models'
import { RequestError } from '@/shared/api/ui/request-error'
import { useSession } from '@/shared/session/session'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/shared/ui/alert-dialog'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'

export function NeedSummary({ need, onEdit }: { need: NeedResponse; onEdit: () => void }) {
  const userId = useSession().user?.id
  const client = useQueryClient()
  const [confirmStatus, setConfirmStatus] = useState(false)
  const status = useMutation({
    mutationFn: () => setNeedStatus(need.id, need.status === 'active' ? 'closed' : 'active'),
    onSuccess: async (saved) => {
      await client.cancelQueries({ queryKey: needsKey(userId) })
      client.setQueryData(needKey(userId, need.id), saved)
      client.setQueryData<NeedResponse[]>(needsKey(userId), (current) => current?.map((item) => item.id === saved.id ? saved : item) ?? [saved])
      void client.invalidateQueries({ queryKey: needsKey(userId), exact: true })
      setConfirmStatus(false)
    },
  })
  const money = (value: number) => new Intl.NumberFormat('ru-RU').format(value)
  const budget = need.salary_from != null && need.salary_to != null ? `${money(need.salary_from)}–${money(need.salary_to)}` : need.salary_from != null ? `от ${money(need.salary_from)}` : need.salary_to != null ? `до ${money(need.salary_to)}` : null

  return (
    <aside className="space-y-5 rounded-xl border bg-card p-5 shadow-card" aria-label="Сохранённые условия подбора">
      <div className="space-y-3"><Badge variant="secondary">{need.status === 'active' ? 'Активная потребность' : 'Потребность закрыта'}</Badge><h2 className="text-lg font-semibold leading-6">{need.title}</h2><p className="text-sm text-muted-foreground">{roleLabels[need.specialization]} · {gradeLabels[need.grade]}</p></div>
      <dl className="space-y-3 text-sm"><div><dt className="text-xs text-muted-foreground">Сотрудников</dt><dd>{need.headcount ?? 1}</dd></div><div><dt className="text-xs text-muted-foreground">Бюджет</dt><dd>{budget ? `${budget} ${need.currency === 'RUB' ? '₽' : need.currency ?? ''}` : 'Не указан'}</dd></div><div><dt className="text-xs text-muted-foreground">Формат и город</dt><dd>{need.work_formats?.map((format) => formatLabels[format]).join(' · ') || 'Любой формат'}{need.city ? ` · ${need.city}` : ''}</dd></div></dl>
      <div className="space-y-2"><h3 className="text-xs font-semibold">Обязательные навыки</h3><div className="flex flex-wrap gap-1.5">{need.required_skills.map((skill) => <Badge key={skill} variant="secondary" className="font-normal">{skill}</Badge>)}</div></div>
      {need.optional_skills?.length ? <div className="space-y-2"><h3 className="text-xs font-semibold">Желательные</h3><p className="text-sm text-muted-foreground">{need.optional_skills.join(', ')}</p></div> : null}
      <details className="space-y-3"><summary className="cursor-pointer text-xs font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring">Задачи и точность подбора</summary><p className="whitespace-pre-wrap break-words text-sm leading-6 text-muted-foreground">{need.team_description}</p><ul className="space-y-2 text-xs leading-5 text-muted-foreground"><li>Отклонение грейда: {need.grade_tolerance ?? 1} ступ.</li>{need.require_confirmed_grade ? <li>Только подтверждённый грейд</li> : null}{need.strict_skills ? <li>Все обязательные навыки — точное совпадение</li> : null}{need.min_experience_months != null ? <li>Опыт от {need.min_experience_months} мес.</li> : null}{need.hard_budget ? <li>Строгий бюджет</li> : null}{need.strict_format ? <li>Строгий формат работы</li> : null}</ul></details>
      {need.status === 'closed' ? <p className="text-xs leading-5 text-muted-foreground">Можно просмотреть подборку или возобновить поиск.</p> : null}
      <div className="space-y-2"><Button className="w-full" variant="outline" disabled={status.isPending} onClick={onEdit}><Pencil size={15} aria-hidden="true" />Изменить условия</Button><Button className="w-full" variant="ghost" size="sm" disabled={status.isPending} onClick={() => { status.reset(); setConfirmStatus(true) }}>{need.status === 'active' ? 'Закрыть потребность' : 'Возобновить поиск'}</Button></div>
      <AlertDialog open={confirmStatus}>
        <AlertDialogContent><AlertDialogHeader><AlertDialogTitle>{need.status === 'active' ? 'Закрыть потребность?' : 'Возобновить поиск?'}</AlertDialogTitle><AlertDialogDescription>{need.status === 'active' ? 'Потребность останется в списке. Её можно будет открыть снова.' : 'Потребность снова станет активной.'}</AlertDialogDescription></AlertDialogHeader>{status.isError ? <RequestError error={status.error} /> : null}<AlertDialogFooter><AlertDialogCancel disabled={status.isPending} onClick={() => setConfirmStatus(false)}>Отмена</AlertDialogCancel><Button disabled={status.isPending} onClick={() => status.mutate()}>{status.isPending ? 'Сохраняем…' : 'Подтвердить'}</Button></AlertDialogFooter></AlertDialogContent>
      </AlertDialog>
    </aside>
  )
}
