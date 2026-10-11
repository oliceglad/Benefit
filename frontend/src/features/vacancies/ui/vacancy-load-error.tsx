import { Link } from '@tanstack/react-router'
import { AlertTriangle, ArrowLeft, RotateCcw } from 'lucide-react'

import { isApiError } from '@/shared/api/transport/api-error'
import { Button } from '@/shared/ui/button'

export function VacancyLoadError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const status = isApiError(error) ? error.status : 0
  const notFound = status === 404
  const forbidden = status === 403
  const title = notFound ? 'Вакансия не найдена' : forbidden ? 'Нет доступа к этой вакансии' : 'Не удалось загрузить вакансию'
  const description = notFound
    ? 'Возможно, вакансия была удалена или перемещена.'
    : forbidden
      ? 'Откройте вакансию своей компании или вернитесь к списку.'
      : 'Проверьте соединение и повторите попытку.'

  return (
    <div className="mx-auto grid min-h-72 max-w-xl place-items-center rounded-2xl border bg-card p-6 text-center">
      <div className="space-y-4"><span className="mx-auto grid size-12 place-items-center rounded-xl bg-muted"><AlertTriangle className="size-6 text-muted-foreground" aria-hidden="true" /></span><div><h1 className="text-2xl font-semibold">{title}</h1><p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p></div><div className="flex flex-wrap justify-center gap-2"><Button asChild variant="outline"><Link to="/vacancies" search={{ offset: 0 }}><ArrowLeft aria-hidden="true" />К списку вакансий</Link></Button>{!notFound && !forbidden ? <Button type="button" onClick={onRetry}><RotateCcw aria-hidden="true" />Повторить</Button> : null}</div></div>
    </div>
  )
}
