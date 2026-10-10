import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useState } from 'react'
import { z } from 'zod'
import { chatKeys } from '@/features/chat/api/chat'

const eventSchema = z.object({
  type: z.string(),
  conversation_id: z.string().optional(),
  message: z.object({ conversation_id: z.string() }).optional(),
  conversation: z.object({ id: z.string() }).optional(),
})

export function useChatConnection(userId: string) {
  const client = useQueryClient()
  const [status, setStatus] = useState<'connecting' | 'live' | 'polling'>('connecting')
  const [revision, setRevision] = useState(0)
  const reconnect = useCallback(() => setRevision((value) => value + 1), [])

  useEffect(() => {
    let disposed = false
    let socket: WebSocket | undefined
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined
    let handshakeTimer: ReturnType<typeof setTimeout> | undefined
    let failures = 0
    const url = new URL(`${(import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? ''}/api/v1/chat/ws`, window.location.origin)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'

    function connect() {
      if (disposed) return
      setStatus('connecting')
      socket = new WebSocket(url)
      handshakeTimer = setTimeout(() => socket?.close(), 10_000)
      socket.onmessage = (event: MessageEvent<unknown>) => {
        if (disposed || typeof event.data !== 'string') return
        let data: unknown
        try { data = JSON.parse(event.data) as unknown } catch { return }
        const parsed = eventSchema.safeParse(data)
        if (!parsed.success) return
        const value = parsed.data
        if (value.type === 'ready') {
          clearTimeout(handshakeTimer)
          failures = 0
          setStatus('live')
          void client.invalidateQueries({ queryKey: chatKeys.all(userId) })
          return
        }
        if (!['message.created', 'conversation.read', 'conversation.updated'].includes(value.type)) return
        void client.invalidateQueries({ queryKey: chatKeys.conversations(userId) })
        const id = value.conversation_id ?? value.message?.conversation_id ?? value.conversation?.id
        if (id) {
          void client.invalidateQueries({ queryKey: chatKeys.conversation(userId, id) })
          if (value.type === 'message.created') void client.invalidateQueries({ queryKey: chatKeys.messages(userId, id) })
        }
      }
      socket.onclose = (event) => {
        clearTimeout(handshakeTimer)
        if (disposed) return
        setStatus('polling')
        // REST can refresh cookies; explicit reconnect avoids repeatedly opening an unauthorized socket.
        if (event.code === 4401 || event.code === 4403) return
        const delay = event.code === 4429 ? 30_000 : Math.min(30_000, 2000 * 2 ** Math.min(failures++, 4))
        reconnectTimer = setTimeout(connect, delay)
      }
      socket.onerror = () => socket?.close()
    }
    connect()
    return () => {
      disposed = true
      clearTimeout(handshakeTimer)
      clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [client, userId, revision])

  return { status, reconnect }
}
