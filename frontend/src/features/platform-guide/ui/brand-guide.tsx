import { ArrowRight, Check, ChevronDown, CirclePlay, X } from 'lucide-react'
import { useEffect, useId, useRef, useState, type RefObject } from 'react'
import { createPortal } from 'react-dom'

import { guideSteps, type GuideRole } from '@/features/platform-guide/model/guide-steps'
import { GuideArtwork } from '@/features/platform-guide/ui/guide-artwork'
import { cn } from '@/shared/lib/cn'
import { BrandLogo } from '@/shared/ui/brand-logo'
import { Button } from '@/shared/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/shared/ui/dropdown-menu'

import './platform-guide.css'

export function BrandGuide({ role, className }: { role: GuideRole; className?: string }) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)

  return <>
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button ref={triggerRef} type="button" className={cn('platform-guide__trigger', className)} aria-label="Открыть меню Benefit" title="Меню Benefit">
          <BrandLogo className="h-7 shrink-0 sm:h-8" /><ChevronDown size={13} className="text-muted-foreground" aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-72">
        <DropdownMenuLabel><span className="block">Ваш Benefit</span><span className="mt-1 block text-xs font-normal text-muted-foreground">Короткий гид по вашему кабинету</span></DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => setOpen(true)}><CirclePlay aria-hidden="true" />Знакомство с платформой</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
    {open ? <GuideDialog role={role} onClose={() => setOpen(false)} returnFocusRef={triggerRef} /> : null}
  </>
}

function GuideDialog({ role, onClose, returnFocusRef }: { role: GuideRole; onClose: () => void; returnFocusRef: RefObject<HTMLButtonElement | null> }) {
  const [index, setIndex] = useState(0)
  const steps = guideSteps[role]
  const step = steps[index]
  const last = index === steps.length - 1
  const titleId = useId()
  const descriptionId = useId()
  const dialogRef = useRef<HTMLDialogElement>(null)
  const titleRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    const previousOverflow = document.body.style.overflow
    const returnTarget = returnFocusRef.current
    document.body.style.overflow = 'hidden'
    dialog.showModal()
    return () => {
      dialog.close()
      document.body.style.overflow = previousOverflow
      returnTarget?.focus({ preventScroll: true })
    }
  }, [returnFocusRef])

  useEffect(() => { titleRef.current?.focus({ preventScroll: true }) }, [index])

  return createPortal(
    <dialog ref={dialogRef} className="platform-guide" aria-labelledby={titleId} aria-describedby={descriptionId} onCancel={(event) => { event.preventDefault(); onClose() }} onKeyDown={(event) => {
      if (event.key !== 'Tab') return
      const buttons = event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')
      const first = buttons[0]
      const lastButton = buttons[buttons.length - 1]
      if (!first || !lastButton) return
      if (!event.shiftKey && document.activeElement === lastButton) { event.preventDefault(); first.focus() }
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); lastButton.focus() }
    }}>
      <div className="platform-guide__layout">
        <GuideArtwork step={step} />
        <div className="platform-guide__body">
          <div className="platform-guide__top"><span>{role === 'employer' ? 'Кабинет работодателя' : 'Кабинет кандидата'}</span><Button type="button" variant="ghost" size="icon" className="-mr-2 -mt-2" onClick={onClose} aria-label="Закрыть знакомство"><X aria-hidden="true" /></Button></div>
          <section key={step.id} className="platform-guide__copy">
            <p className="platform-guide__eyebrow">Знакомство · {String(index + 1).padStart(2, '0')} / {String(steps.length).padStart(2, '0')}</p>
            <h2 ref={titleRef} id={titleId} tabIndex={-1}>{step.title}</h2>
            <p id={descriptionId} className="platform-guide__description">{step.description}</p>
            <ul className="platform-guide__points">{step.points.map((point) => <li key={point}><span><Check size={14} aria-hidden="true" /></span>{point}</li>)}</ul>
          </section>
          <footer className="platform-guide__footer">
            <nav aria-label="Шаги знакомства"><ol className="platform-guide__progress">{steps.map((item, position) => <li key={item.id}><button type="button" aria-label={`Шаг ${position + 1}: ${item.title}`} aria-current={position === index ? 'step' : undefined} data-complete={position < index} onClick={() => setIndex(position)}><span /></button></li>)}</ol></nav>
            <div className="platform-guide__actions"><Button type="button" variant="ghost" onClick={() => index === 0 ? onClose() : setIndex(index - 1)}>{index === 0 ? 'Пропустить' : 'Назад'}</Button><Button type="button" onClick={() => last ? onClose() : setIndex(index + 1)}>{last ? 'Начать работу' : 'Далее'}<ArrowRight size={16} aria-hidden="true" /></Button></div>
            <p className="platform-guide__replay">Вернуться к гиду: Benefit → Знакомство с платформой</p>
          </footer>
        </div>
      </div>
    </dialog>, document.body,
  )
}
