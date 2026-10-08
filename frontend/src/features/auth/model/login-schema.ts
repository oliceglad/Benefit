import { z } from 'zod'

export const loginSchema = z.object({
  email: z.email('Введите корректную почту'),
  password: z.string().min(1, 'Введите пароль').max(128, 'Пароль слишком длинный'),
})

export type LoginValues = z.infer<typeof loginSchema>
