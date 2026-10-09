import { forwardRef, type ComponentPropsWithoutRef } from 'react'
import { IMaskInput, type IMask } from 'react-imask'

import { cn } from '@/shared/lib/cn'
import { inputClassName } from '@/shared/ui/input-styles'

const phoneMasks = [
  { mask: '+{7} (000) 000-00-00' },
  { mask: '+000000000000000' },
]

type DynamicPhoneMask = InstanceType<typeof IMask.MaskedDynamic>
type PhoneMask = InstanceType<typeof IMask.Masked>

function preparePhoneInput(appended: string, masked: PhoneMask): string {
  if (masked.value === '' && appended.startsWith('8')) return `7${appended.slice(1)}`
  return appended
}

function dispatchPhoneMask(appended: string, masked: DynamicPhoneMask) {
  const digits = `${masked.value}${appended}`.replace(/\D/g, '')
  return digits.startsWith('7') ? masked.compiledMasks[0] : masked.compiledMasks[1]
}

type PhoneInputProps = Omit<ComponentPropsWithoutRef<'input'>, 'onChange' | 'value'> & {
  value: string
  onValueChange: (value: string) => void
}

export const PhoneInput = forwardRef<HTMLInputElement, PhoneInputProps>(function PhoneInput(
  { className, onValueChange, ...props },
  ref,
) {
  return (
    <IMaskInput
      {...props}
      inputRef={ref}
      mask={phoneMasks}
      prepare={preparePhoneInput}
      dispatch={dispatchPhoneMask}
      lazy
      overwrite={false}
      unmask={false}
      className={cn(inputClassName, className)}
      onAccept={(value) => onValueChange(value)}
    />
  )
})
