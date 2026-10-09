import { useMemo } from 'react'

import { SelectField, type SelectOption } from '@/shared/ui/select-field'

const months: SelectOption[] = [
  { value: '01', label: 'Январь' },
  { value: '02', label: 'Февраль' },
  { value: '03', label: 'Март' },
  { value: '04', label: 'Апрель' },
  { value: '05', label: 'Май' },
  { value: '06', label: 'Июнь' },
  { value: '07', label: 'Июль' },
  { value: '08', label: 'Август' },
  { value: '09', label: 'Сентябрь' },
  { value: '10', label: 'Октябрь' },
  { value: '11', label: 'Ноябрь' },
  { value: '12', label: 'Декабрь' },
]

function parseMonth(value: string): { year: string; month: string } {
  const match = /^(\d{4})-(\d{2})$/.exec(value)
  if (match) return { year: match[1], month: match[2] }
  const partialYear = /^(\d{4})-$/.exec(value)
  if (partialYear) return { year: partialYear[1], month: '' }
  const partialMonth = /^-(\d{2})$/.exec(value)
  return partialMonth ? { year: '', month: partialMonth[1] } : { year: '', month: '' }
}

export function MonthPicker({
  id,
  value,
  onValueChange,
  disabled = false,
  invalid = false,
  minYear = 1900,
  max = new Date().toISOString().slice(0, 7),
}: {
  id: string
  value: string
  onValueChange: (value: string) => void
  disabled?: boolean
  invalid?: boolean
  minYear?: number
  max?: string
}) {
  const parsedValue = parseMonth(value)
  const parsedMax = parseMonth(max)
  const maxYear = Number(parsedMax.year)
  const { year, month } = parsedValue

  const yearOptions = useMemo(
    () => Array.from(
      { length: Math.max(0, maxYear - minYear + 1) },
      (_, index) => {
        const option = String(maxYear - index)
        return { value: option, label: option }
      },
    ),
    [maxYear, minYear],
  )
  const monthOptions = year === parsedMax.year
    ? months.filter((option) => option.value <= parsedMax.month)
    : months

  function update(nextYear: string, nextMonth: string): void {
    onValueChange(nextYear || nextMonth ? `${nextYear}-${nextMonth}` : '')
  }

  return (
    <div className="grid gap-2 sm:grid-cols-2">
      <SelectField
        id={`${id}-month`}
        value={month}
        onValueChange={(nextMonth) => update(year, nextMonth)}
        options={monthOptions}
        placeholder="Месяц"
        ariaLabel="Месяц"
        disabled={disabled}
        invalid={invalid}
      />
      <SelectField
        id={`${id}-year`}
        value={year}
        onValueChange={(nextYear) => {
          const nextMonth = nextYear === parsedMax.year && month > parsedMax.month ? '' : month
          update(nextYear, nextMonth)
        }}
        options={yearOptions}
        placeholder="Год"
        ariaLabel="Год"
        disabled={disabled}
        invalid={invalid}
      />
    </div>
  )
}
