import { z } from 'zod'

import { normalizePhone, normalizeTelegram } from '@/features/candidate-profile/model/form-values'

const optionalEmail = z
  .string()
  .trim()
  .max(254, 'Не более 254 символов')
  .refine((value) => value === '' || z.email().safeParse(value).success, 'Введите корректную почту')

function validPhone(value: string): boolean {
  if (value === '') return true
  return /^\+\d{10,15}$/.test(normalizePhone(value))
}

function validTelegram(value: string): boolean {
  if (value === '') return true
  const handle = normalizeTelegram(value).slice(1)
  return /^[A-Za-z][A-Za-z0-9_]{4,31}$/.test(handle)
}

export const contactSchema = z.object({
  phone: z
    .string()
    .trim()
    .max(64, 'Не более 64 символов')
    .refine(validPhone, 'Введите номер из 10–15 цифр'),
  contactEmail: optionalEmail,
  telegram: z
    .string()
    .trim()
    .max(64, 'Не более 64 символов')
    .refine(validTelegram, 'Укажите username из 5–32 латинских букв, цифр или _'),
})

export type ContactValues = z.infer<typeof contactSchema>
