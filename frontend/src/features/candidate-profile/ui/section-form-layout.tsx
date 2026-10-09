import { AlertCircle, CheckCircle2, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'

import type { SaveConfirmation } from '@/features/candidate-profile/model/use-profile-section-save'
import { isApiError } from '@/shared/api/transport/api-error'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Spinner } from '@/shared/ui/spinner'

export function SectionFormCard({
  title,
  description,
  children,
  standalone = false,
}: {
  title: string
  description: string
  children: ReactNode
  standalone?: boolean
}) {
  return (
    <Card className={standalone ? 'border-0 shadow-none' : undefined}>
      <CardHeader className={standalone ? 'p-0 pb-5' : undefined}>
        <CardTitle className={standalone ? 'sr-only' : undefined}>{title}</CardTitle>
        <CardDescription className={standalone ? 'text-sm leading-5' : undefined}>{description}</CardDescription>
      </CardHeader>
      <CardContent className={standalone ? 'p-0' : undefined}>{children}</CardContent>
    </Card>
  )
}

export function SaveState({
  confirmation,
  error,
  dirty,
  onRetry,
  retrying = false,
}: {
  confirmation: SaveConfirmation
  error: unknown
  dirty: boolean
  onRetry?: () => void
  retrying?: boolean
}) {
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="size-4" aria-hidden="true" />
        <AlertTitle>Не удалось сохранить</AlertTitle>
        <AlertDescription>
          {isApiError(error) ? error.message : 'Проверьте данные и повторите попытку.'}
        </AlertDescription>
      </Alert>
    )
  }
  if (!dirty && confirmation === 'confirmed') {
    return (
      <Alert variant="success">
        <CheckCircle2 className="size-4" aria-hidden="true" />
        <AlertTitle>Раздел сохранён</AlertTitle>
        <AlertDescription>Изменения сохранены.</AlertDescription>
      </Alert>
    )
  }
  if (!dirty && confirmation === 'unconfirmed') {
    return (
      <Alert variant="warning">
        <TriangleAlert className="size-4" aria-hidden="true" />
        <AlertTitle>Раздел сохранён</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>Не удалось получить актуальные данные. Повторите получение, прежде чем покинуть раздел.</p>
          {onRetry ? <Button type="button" size="sm" variant="outline" disabled={retrying} onClick={onRetry}>{retrying ? <Spinner label="Получаем данные…" /> : 'Повторить получение'}</Button> : null}
        </AlertDescription>
      </Alert>
    )
  }
  return null
}

export function SectionActions({
  dirty,
  pending,
  onSave,
}: {
  dirty: boolean
  pending: boolean
  hasNext: boolean
  onSave: () => void
  onSaveAndContinue: () => void
}) {
  return (
    <div className="border-t pt-5">
      <Button type="button" className="w-full sm:w-auto" variant={dirty ? 'default' : 'outline'} disabled={pending || !dirty} onClick={onSave}>
        {pending ? <Spinner label="Сохраняем…" /> : dirty ? 'Сохранить изменения' : 'Нет изменений'}
      </Button>
    </div>
  )
}
