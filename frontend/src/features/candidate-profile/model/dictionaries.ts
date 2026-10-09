import { z } from 'zod'

const optionSchema = z.object({ id: z.string(), title: z.string() })

export const profileDictionariesSchema = z.object({
  grades: z.array(optionSchema),
  roles: z.array(optionSchema),
  skill_levels: z.array(optionSchema),
  language_levels: z.array(optionSchema),
  languages: z.array(z.string()),
  employment_types: z.array(optionSchema),
  work_formats: z.array(optionSchema),
  job_search_statuses: z.array(optionSchema),
  education_levels: z.array(optionSchema),
  link_types: z.array(optionSchema),
  soft_skills: z.array(z.string()),
})

export type DictionaryOption = z.infer<typeof optionSchema>
export type ProfileDictionaries = z.infer<typeof profileDictionariesSchema>
