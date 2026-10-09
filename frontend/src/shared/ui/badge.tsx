import { cva, type VariantProps } from 'class-variance-authority'
import type * as React from 'react'

import { cn } from '@/shared/lib/cn'

const badgeVariants = cva(
  'inline-flex min-h-6 items-center rounded-full px-2.5 py-0.5 text-xs font-semibold',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground',
        secondary: 'bg-muted text-muted-foreground',
        success: 'bg-success/15 text-success-foreground',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

function Badge({ className, variant, ...props }: React.ComponentProps<'span'> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge }
