import { cva, type VariantProps } from 'class-variance-authority'
import type * as React from 'react'

import { cn } from '@/shared/lib/cn'

const alertVariants = cva(
  'grid w-full grid-cols-[auto_1fr] items-start gap-x-3 gap-y-1 rounded-xl border px-4 py-3 text-sm',
  {
    variants: {
      variant: {
        default: 'border-border bg-muted/65 text-foreground',
        destructive: 'border-destructive/25 bg-destructive/10 text-destructive',
        success: 'border-success/25 bg-success/10 text-success-foreground',
        warning: 'border-warning/30 bg-warning/10 text-warning-foreground',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

function Alert({ className, variant, ...props }: React.ComponentProps<'div'> & VariantProps<typeof alertVariants>) {
  return <div role="alert" className={cn(alertVariants({ variant }), className)} {...props} />
}

function AlertTitle({ className, ...props }: React.ComponentProps<'div'>) {
  return <div className={cn('col-start-2 font-semibold', className)} {...props} />
}

function AlertDescription({ className, ...props }: React.ComponentProps<'div'>) {
  return <div className={cn('col-start-2 leading-5 opacity-90', className)} {...props} />
}

export { Alert, AlertDescription, AlertTitle }
