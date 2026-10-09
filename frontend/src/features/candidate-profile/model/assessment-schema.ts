import { z } from 'zod'

import { parseLocalizedNumber } from '@/features/candidate-profile/model/form-values'
import { Grade, Industry, ITRole } from '@/shared/api/generated/assessments/models'

export const assessmentStartSchema = z.object({
  industry: z.enum(Industry, 'Выберите отрасль'),
  specialization: z.enum(ITRole, 'Выберите специализацию'),
  targetGrade: z.enum(Grade, 'Выберите грейд'),
  yearsOfExperience: z.string().refine((value) => {
    if (!/^(?:\d+(?:[.,]\d*)?|[.,]\d+)$/.test(value)) return false
    const parsed = parseLocalizedNumber(value)
    return Number.isFinite(parsed) && parsed >= 0 && parsed <= 50
  }, 'Укажите стаж от 0 до 50 лет, например 1,5'),
})

export type AssessmentStartValues = z.infer<typeof assessmentStartSchema>
