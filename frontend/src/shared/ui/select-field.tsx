import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/ui/select'

export type SelectOption = { value: string; label: string }

const emptyValue = '__benefit_empty_select_value__'

export function SelectField({
  value,
  onValueChange,
  options,
  placeholder = 'Выберите значение',
  id,
  disabled,
  className,
  invalid,
  ariaLabel,
  ariaDescribedBy,
}: {
  value: string
  onValueChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  id?: string
  disabled?: boolean
  className?: string
  invalid?: boolean
  ariaLabel?: string
  ariaDescribedBy?: string
}) {
  const hasEmptyOption = options.some((option) => option.value === '')
  return (
    <Select
      value={value || (hasEmptyOption ? emptyValue : undefined)}
      onValueChange={(next) => onValueChange(next === emptyValue ? '' : next)}
      disabled={disabled}
    >
      <SelectTrigger
        id={id}
        className={className}
        aria-invalid={invalid || undefined}
        aria-label={ariaLabel}
        aria-describedby={ariaDescribedBy}
      >
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value || emptyValue} value={option.value || emptyValue}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
