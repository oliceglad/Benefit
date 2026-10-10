import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Globe, LockKeyhole, Pencil, X } from 'lucide-react'
import { useState } from 'react'

import { changeVacancyStatus } from '@/features/vacancies/api/vacancies'
import { vacancyStatusLabels } from '@/features/vacancies/model/vacancy-search'
import type { VacancyResponse, VacancyStatus } from '@/shared/api/generated/employers/models'
import { RequestError } from '@/shared/api/ui/request-error'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/shared/ui/alert-dialog'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Spinner } from '@/shared/ui/spinner'

const transitions = {
  published: { title: 'Опубликовать вакансию?', action: 'Опубликовать', description: 'Вакансия появится в каталоге. Соискатели смогут посмотреть условия и отправить отклик.' },
  draft: { title: 'Снять вакансию с публикации?', action: 'В черновик', description: 'Вакансия исчезнет из каталога. Её можно будет отредактировать и опубликовать снова.' },
  closed: { title: 'Закрыть вакансию?', action: 'Закрыть вакансию', description: 'Вакансия исчезнет из каталога и останется в списке компании со статусом «Закрыта».' },
}

export function VacancyActions({ vacancy }: { vacancy: VacancyResponse }) {
  const client = useQueryClient()
  const [target, setTarget] = useState<VacancyStatus | null>(null)
  const [notice, setNotice] = useState('')
  const mutation = useMutation({
    mutationFn: (status: VacancyStatus) => changeVacancyStatus(vacancy.id, status),
    onSuccess: (saved) => {
      client.setQueryData(['vacancies', 'detail', vacancy.id, true], saved)
      void client.invalidateQueries({ queryKey: ['vacancies'] })
      setNotice(saved.status === 'published' ? 'Вакансия опубликована и доступна соискателям.' : `Статус обновлён: ${vacancyStatusLabels[saved.status].toLocaleLowerCase('ru')}.`)
      setTarget(null)
    },
  })
  function selectStatus(status: VacancyStatus) {
    mutation.reset()
    setNotice('')
    setTarget(status)
  }

  return (
    <div className="space-y-4 rounded-xl border bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          {vacancy.status === 'published' ? <Globe className="size-5 text-primary" aria-hidden="true" /> : <LockKeyhole className="size-5 text-muted-foreground" aria-hidden="true" />}
          <div className="space-y-1">
            <p className="text-sm font-semibold">Управление вакансией</p>
            <p className="text-xs text-muted-foreground">{vacancy.status === 'published' ? 'Видна в каталоге соискателей' : 'Сейчас видна только вашей компании'}</p>
          </div>
          <Badge variant="secondary">{vacancyStatusLabels[vacancy.status]}</Badge>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline"><Link to="/vacancies/$vacancyId/edit" params={{ vacancyId: vacancy.id }}><Pencil aria-hidden="true" />Редактировать</Link></Button>
          {vacancy.status === 'published' ? (
            <Button variant="outline" onClick={() => selectStatus('draft')}>Снять с публикации</Button>
          ) : (
            <Button onClick={() => selectStatus('published')}><Globe aria-hidden="true" />Опубликовать</Button>
          )}
          {vacancy.status !== 'closed' ? <Button variant="ghost" onClick={() => selectStatus('closed')}><X aria-hidden="true" />Закрыть</Button> : null}
        </div>
      </div>
      {notice ? <p role="status" className="text-sm text-primary">{notice}</p> : null}
      <AlertDialog open={target !== null} onOpenChange={(open) => { if (!open && !mutation.isPending) setTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{target ? transitions[target].title : ''}</AlertDialogTitle>
            <AlertDialogDescription>{target ? transitions[target].description : ''}</AlertDialogDescription>
          </AlertDialogHeader>
          <p className="break-words text-sm font-medium">{vacancy.title}</p>
          {mutation.isError ? <RequestError error={mutation.error} /> : null}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={mutation.isPending}>Отмена</AlertDialogCancel>
            <Button disabled={mutation.isPending} onClick={() => { if (target) mutation.mutate(target) }}>
              {mutation.isPending ? <Spinner label="Обновляем статус…" /> : target ? transitions[target].action : ''}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
