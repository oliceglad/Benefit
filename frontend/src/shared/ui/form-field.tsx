import type { ReactNode } from 'react'

import { Label } from '@/shared/ui/label'

export function FormField({ id, label, error, hint, children, required = false }: {
  id: string
  label: string
  error?: string
  hint?: string
  required?: boolean
  children: (props: { id: string; 'aria-invalid': boolean; 'aria-describedby': string | undefined; 'aria-required': boolean }) => ReactNode
}) {
  return (
    <div className="min-w-0 space-y-2">
      <Label htmlFor={id}>{label}{required ? <span className="text-destructive" aria-hidden="true"> *</span> : null}</Label>
      {children({ id, 'aria-invalid': Boolean(error), 'aria-describedby': error || hint ? `${id}-help` : undefined, 'aria-required': required })}
      {error || hint ? <p id={`${id}-help`} className={`text-xs leading-5 ${error ? 'text-destructive' : 'text-muted-foreground'}`} role={error ? 'alert' : undefined}>{error || hint}</p> : null}
    </div>
  )
}

export const formSelectClass = 'min-h-12 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/35 aria-invalid:border-destructive'
