import { Eye, EyeOff } from 'lucide-react'
import { useState, type ComponentProps } from 'react'

import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'

export function PasswordInput(props: ComponentProps<typeof Input>) {
  const [isVisible, setIsVisible] = useState(false)

  return (
    <div className="relative">
      <Input type={isVisible ? 'text' : 'password'} className="pr-12" {...props} />
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="absolute right-1 top-1/2 -translate-y-1/2"
        aria-label={isVisible ? 'Скрыть пароль' : 'Показать пароль'}
        aria-pressed={isVisible}
        onClick={() => setIsVisible((visible) => !visible)}
      >
        {isVisible ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
      </Button>
    </div>
  )
}
