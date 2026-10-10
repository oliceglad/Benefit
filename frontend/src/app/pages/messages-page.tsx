import { MessagesPage as ChatWorkspace } from '@/features/chat/ui/messages-page'
import { InvitationInbox } from '@/features/invitations/ui/invitation-inbox'

export function MessagesPage() {
  return <ChatWorkspace invitationsPanel={<InvitationInbox />} />
}
