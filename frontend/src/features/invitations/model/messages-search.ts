import { z } from 'zod'

export const messagesSearchSchema = z.object({
  section: z.literal('invitations').optional().catch(undefined),
  invitation: z.uuid().optional().catch(undefined),
})
