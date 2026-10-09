import * as React from 'react'

import { cn } from '@/shared/lib/cn'

function resizeToContent(textarea: HTMLTextAreaElement | null): void {
  if (!textarea) return
  textarea.style.height = 'auto'
  textarea.style.height = `${textarea.scrollHeight}px`
}

const Textarea = React.forwardRef<HTMLTextAreaElement, React.ComponentProps<'textarea'>>(function Textarea(
  { className, onInput, ...props },
  forwardedRef,
) {
  const textareaRef = React.useRef<HTMLTextAreaElement | null>(null)
  const setRef = React.useCallback((node: HTMLTextAreaElement | null) => {
    textareaRef.current = node
    if (typeof forwardedRef === 'function') forwardedRef(node)
    else if (forwardedRef) forwardedRef.current = node
  }, [forwardedRef])

  React.useLayoutEffect(() => {
    resizeToContent(textareaRef.current)
  })

  return (
    <textarea
      ref={setRef}
      data-slot="textarea"
      className={cn(
        'flex min-h-28 w-full resize-none overflow-hidden rounded-xl border border-input bg-background px-3 py-3 text-base leading-6 outline-none transition-[border-color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/35 disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60 aria-invalid:border-destructive aria-invalid:ring-[3px] aria-invalid:ring-destructive/20',
        className,
      )}
      onInput={(event) => {
        resizeToContent(event.currentTarget)
        onInput?.(event)
      }}
      {...props}
    />
  )
})

export { Textarea }
