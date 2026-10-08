import { LoaderCircle } from 'lucide-react'

import { cn } from '@/shared/lib/cn'

export function Spinner({ className, label = 'Загрузка' }: { className?: string; label?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)} role="status">
      <LoaderCircle className="animate-spin" aria-hidden="true" />
      <span>{label}</span>
    </span>
  )
}
