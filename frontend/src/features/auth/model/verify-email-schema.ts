import { z } from 'zod'

export const verifyEmailSchema = z.object({
  email: z.email('Введите корректную почту').transform((email) => email.trim().toLowerCase()),
  code: z.string().regex(/^\d{6}$/, 'Введите шестизначный код'),
})

export type VerifyEmailValues = z.infer<typeof verifyEmailSchema>
