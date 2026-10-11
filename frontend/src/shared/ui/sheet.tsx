import * as SheetPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type * as React from 'react'

import { cn } from '@/shared/lib/cn'

const Sheet = SheetPrimitive.Root
const SheetTrigger = SheetPrimitive.Trigger
const SheetClose = SheetPrimitive.Close

function SheetContent({
  className,
  children,
  side = 'right',
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Content> & {
  side?: 'right' | 'bottom'
}) {
  return (
    <SheetPrimitive.Portal>
      <SheetPrimitive.Overlay className="fixed inset-0 z-50 bg-slate-950/45 data-[state=closed]:animate-out data-[state=open]:animate-in" />
      <SheetPrimitive.Content
        data-slot="sheet-content"
        data-side={side}
        className={cn(
          'fixed z-50 flex flex-col border bg-background shadow-xl outline-none data-[state=closed]:animate-out data-[state=open]:animate-in',
          side === 'right'
            ? 'inset-y-0 right-0 w-full max-w-lg border-l data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right'
            : 'inset-x-0 bottom-0 max-h-[90svh] rounded-t-2xl border-t data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom',
          className,
        )}
        {...props}
      >
        {children}
        <SheetPrimitive.Close className="absolute right-4 top-4 grid size-10 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/35">
          <X className="size-5" aria-hidden="true" />
          <span className="sr-only">Закрыть</span>
        </SheetPrimitive.Close>
      </SheetPrimitive.Content>
    </SheetPrimitive.Portal>
  )
}

function SheetHeader({ className, ...props }: React.ComponentProps<'div'>) {
  return <div className={cn('space-y-1.5 border-b px-5 py-5 pr-16', className)} {...props} />
}

function SheetFooter({ className, ...props }: React.ComponentProps<'div'>) {
  return <div className={cn('mt-auto flex gap-2 border-t p-5', className)} {...props} />
}

function SheetTitle({ className, ...props }: React.ComponentProps<typeof SheetPrimitive.Title>) {
  return <SheetPrimitive.Title className={cn('text-lg font-semibold', className)} {...props} />
}

function SheetDescription({ className, ...props }: React.ComponentProps<typeof SheetPrimitive.Description>) {
  return <SheetPrimitive.Description className={cn('text-sm leading-6 text-muted-foreground', className)} {...props} />
}

export { Sheet, SheetClose, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger }
