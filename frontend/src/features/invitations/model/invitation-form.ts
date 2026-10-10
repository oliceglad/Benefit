import { z } from 'zod'

import type { InvitationCreate, InvitationStatus } from '@/shared/api/generated/applications/models'

export const invitationStatusLabels: Record<InvitationStatus, string> = {
  pending: 'Ожидает ответа', accepted: 'Принято', declined: 'Отклонено', withdrawn: 'Отозвано', expired: 'Срок истёк',
}

const amount = z.string().trim().regex(/^\d+$/, 'Укажите целую сумму в рублях').refine((value) => Number.isSafeInteger(Number(value)) && Number(value) <= 100_000_000, 'Сумма — от 0 до 100 000 000 ₽')
export const invitationFormSchema = z.object({
  vacancyId: z.union([z.uuid(), z.literal('')]),
  title: z.string().trim().min(1, 'Укажите должность').max(200, 'Не более 200 символов'),
  companyName: z.string().trim().min(1, 'Укажите компанию').max(200, 'Не более 200 символов'),
  salaryFrom: amount, salaryTo: amount,
  workFormat: z.enum(['', 'office', 'remote', 'hybrid']),
  city: z.string().trim().max(100, 'Не более 100 символов'),
  message: z.string().trim().max(2000, 'Не более 2000 символов'),
}).refine((value) => Number(value.salaryFrom) <= Number(value.salaryTo), { path: ['salaryTo'], message: 'Верхняя граница должна быть не меньше нижней' })

export type InvitationFormValues = z.infer<typeof invitationFormSchema>
export type OfferDefaults = Partial<Pick<InvitationFormValues, 'title' | 'salaryFrom' | 'salaryTo' | 'workFormat' | 'city'>>

export function invitationPayload(candidateId: string, values: InvitationFormValues): InvitationCreate {
  return {
    candidate_id: candidateId,
    vacancy: {
      vacancy_id: values.vacancyId || null, title: values.title, company_name: values.companyName,
      salary_from: Number(values.salaryFrom), salary_to: Number(values.salaryTo), currency: 'RUB',
      work_format: values.workFormat || null, city: values.city || null,
    },
    message: values.message || null,
  }
}
