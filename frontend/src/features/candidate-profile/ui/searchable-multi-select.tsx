import { Check, Search, X } from 'lucide-react'
import { useId, useMemo, useRef, useState } from 'react'

import { cn } from '@/shared/lib/cn'
import { Label } from '@/shared/ui/label'

type MultiSelectOption<T extends string> = {
  value: T
  label: string
}

export function SearchableMultiSelect<T extends string>({
  id,
  label,
  options,
  value,
  onChange,
  placeholder,
  searchPlaceholder,
  maxSelections,
}: {
  id: string
  label: string
  options: ReadonlyArray<MultiSelectOption<T>>
  value: readonly T[]
  onChange: (value: T[]) => void
  placeholder: string
  searchPlaceholder: string
  maxSelections?: number
}) {
  const generatedId = useId()
  const listId = `${generatedId}-listbox`
  const statusId = `${generatedId}-status`
  const rootRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const selected = useMemo(() => new Set(value), [value])
  const selectedOptions = options.filter((option) => selected.has(option.value))
  const filteredOptions = options.filter((option) =>
    option.label.toLocaleLowerCase('ru-RU').includes(query.trim().toLocaleLowerCase('ru-RU')),
  )
  const resolvedActiveIndex = Math.min(activeIndex, Math.max(filteredOptions.length - 1, 0))
  const limitReached = maxSelections !== undefined && value.length >= maxSelections

  function toggle(option: MultiSelectOption<T>): void {
    if (selected.has(option.value)) {
      onChange(value.filter((item) => item !== option.value))
    } else if (!limitReached) {
      onChange([...value, option.value])
    }
    setQuery('')
    setActiveIndex(0)
  }

  function remove(option: MultiSelectOption<T>): void {
    onChange(value.filter((item) => item !== option.value))
  }

  return (
    <div
      ref={rootRef}
      className="space-y-2"
      onBlur={(event) => {
        if (!rootRef.current?.contains(event.relatedTarget)) setOpen(false)
      }}
    >
      <div className="flex items-end justify-between gap-3">
        <Label htmlFor={id}>{label}</Label>
        {maxSelections !== undefined ? (
          <span id={statusId} className="text-xs text-muted-foreground">
            Выбрано {value.length} из {maxSelections}
          </span>
        ) : null}
      </div>

      {selectedOptions.length > 0 ? (
        <div className="flex flex-wrap gap-2" aria-label={`Выбрано: ${selectedOptions.map((option) => option.label).join(', ')}`}>
          {selectedOptions.map((option) => (
            <span key={option.value} className="inline-flex max-w-full items-center gap-1 rounded-lg bg-muted pl-2.5 text-sm font-medium text-foreground">
              <span className="break-words py-1.5">{option.label}</span>
              <button
                type="button"
                className="group grid size-11 shrink-0 place-items-center rounded-lg text-muted-foreground outline-none hover:text-foreground"
                aria-label={`Убрать ${option.label}`}
                onClick={() => remove(option)}
              >
                <span className="grid size-8 place-items-center rounded-md transition-colors group-hover:bg-background group-focus-visible:ring-2 group-focus-visible:ring-ring">
                  <X className="size-3.5" aria-hidden="true" />
                </span>
              </button>
            </span>
          ))}
        </div>
      ) : null}

      <div className="relative">
        <div className={cn('flex min-h-12 items-center gap-2 rounded-xl border border-input bg-background px-3 transition-[border-color,box-shadow] focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/35', limitReached && 'bg-muted')}>
            <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <input
              id={id}
              className="min-h-11 min-w-0 flex-1 bg-transparent text-base text-foreground outline-none placeholder:text-muted-foreground/80 disabled:cursor-not-allowed"
              value={query}
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={open}
              aria-controls={listId}
              aria-describedby={maxSelections !== undefined ? statusId : undefined}
              aria-activedescendant={open && filteredOptions[resolvedActiveIndex] ? `${listId}-${resolvedActiveIndex}` : undefined}
              placeholder={selectedOptions.length === 0 ? placeholder : searchPlaceholder}
              disabled={limitReached}
              autoComplete="off"
              onFocus={() => setOpen(true)}
              onChange={(event) => {
                setQuery(event.target.value)
                setActiveIndex(0)
                setOpen(true)
              }}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  setOpen(false)
                  setQuery('')
                  return
                }
                if (!open) setOpen(true)
                if (filteredOptions.length === 0) return
                if (event.key === 'ArrowDown') {
                  event.preventDefault()
                  setActiveIndex((current) => (current + 1) % filteredOptions.length)
                } else if (event.key === 'ArrowUp') {
                  event.preventDefault()
                  setActiveIndex((current) => (current - 1 + filteredOptions.length) % filteredOptions.length)
                } else if (event.key === 'Enter') {
                  event.preventDefault()
                  const option = filteredOptions[resolvedActiveIndex]
                  if (option && (selected.has(option.value) || !limitReached)) toggle(option)
                }
              }}
            />
        </div>

        {open ? (
          <div
            id={listId}
            role="listbox"
            aria-multiselectable="true"
            className="absolute z-30 mt-1.5 grid max-h-64 w-full gap-1 overflow-y-auto rounded-lg border bg-popover p-1.5 text-popover-foreground shadow-lg"
          >
            {filteredOptions.length === 0 ? (
              <p className="px-3 py-2 text-sm text-muted-foreground">Ничего не найдено</p>
            ) : filteredOptions.map((option, index) => {
              const isSelected = selected.has(option.value)
              const isDisabled = !isSelected && limitReached
              return (
                <button
                  key={option.value}
                  id={`${listId}-${index}`}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  aria-disabled={isDisabled}
                  className={cn(
                    'flex min-h-10 w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm outline-none transition-colors',
                    index === resolvedActiveIndex ? 'bg-accent text-accent-foreground' : 'hover:bg-accent',
                    isDisabled && 'cursor-not-allowed opacity-45',
                  )}
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseMove={() => setActiveIndex(index)}
                  onClick={() => { if (!isDisabled) toggle(option) }}
                >
                  <span className={cn('grid size-5 shrink-0 place-items-center rounded border', isSelected ? 'border-primary bg-primary text-primary-foreground' : 'border-input')}>
                    {isSelected ? <Check className="size-3.5" aria-hidden="true" /> : null}
                  </span>
                  <span className="break-words">{option.label}</span>
                </button>
              )
            })}
          </div>
        ) : null}
      </div>
      {limitReached ? <p className="text-xs leading-5 text-muted-foreground">Достигнут лимит: {maxSelections}. Удалите выбранное значение, чтобы добавить другое.</p> : null}
    </div>
  )
}
