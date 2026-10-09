import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import type * as React from 'react'

import { cn } from '@/shared/lib/cn'

const buttonVariants = cva(
  'inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/45 disabled:pointer-events-none disabled:opacity-55 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        outline:
          'border border-border bg-background text-foreground hover:bg-muted',
        ghost: 'text-muted-foreground hover:bg-muted hover:text-foreground',
        destructive:
          'bg-destructive text-white hover:bg-destructive/90 focus-visible:ring-destructive/35',
      },
      size: {
        default: 'min-h-12',
        sm: 'min-h-10 rounded-lg px-3',
        icon: 'size-11 min-h-11 px-0',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

type ButtonProps = React.ComponentProps<'button'> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }

function Button({ className, variant, size, asChild = false, ...props }: ButtonProps) {
  const Component = asChild ? Slot : 'button'

  return (
    <Component
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

// buttonVariants is also used by button-like Radix primitives.
// eslint-disable-next-line react-refresh/only-export-components
export { Button, buttonVariants }
