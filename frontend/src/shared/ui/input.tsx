import type * as React from 'react'

import { cn } from '@/shared/lib/cn'
import { inputClassName } from '@/shared/ui/input-styles'

function Input({ className, type, ...props }: React.ComponentProps<'input'>) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(inputClassName, className)}
      {...props}
    />
  )
}

export { Input }
