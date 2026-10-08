import { z } from 'zod'

function hasRussianEmailDomain(email: string): boolean {
  const domain = email.split('@').at(-1)?.toLowerCase() ?? ''
  return ['ru', 'su', 'рф', 'xn--p1ai'].some(
    (ending) => domain === ending || domain.endsWith(`.${ending}`),
  )
}

export const registerSchema = z.object({
  fullName: z.string().trim().max(255, 'Не более 255 символов'),
  email: z
    .email('Введите корректную почту')
    .transform((email) => email.trim().toLowerCase())
    .refine(hasRussianEmailDomain, 'Используйте почту в домене .ru, .su или .рф'),
  password: z
    .string()
    .min(8, 'Не менее 8 символов')
    .max(128, 'Не более 128 символов')
    .refine((value) => /\p{L}/u.test(value) && /\d/.test(value), 'Добавьте буквы и цифры'),
})

export type RegisterValues = z.infer<typeof registerSchema>
