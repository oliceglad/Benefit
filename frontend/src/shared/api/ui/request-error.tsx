import { isApiError } from '@/shared/api/transport/api-error'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import { Button } from '@/shared/ui/button'

export function RequestError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = isApiError(error) ? error.message : 'Не удалось загрузить данные. Попробуйте ещё раз.'
  return <Alert variant="destructive"><AlertTitle>Действие не выполнено</AlertTitle><AlertDescription className="space-y-3"><p>{message}</p>{isApiError(error) && error.retryAfterSeconds ? <p>Повторите через {error.retryAfterSeconds} сек.</p> : null}{onRetry ? <Button type="button" size="sm" variant="outline" onClick={onRetry}>Повторить</Button> : null}</AlertDescription></Alert>
}
