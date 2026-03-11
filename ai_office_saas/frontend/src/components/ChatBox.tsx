import { useEffect, useMemo, useRef, useState } from 'react'

type WSMessage = {
  type: string
  message: string
  session_id?: string
  payload?: { action?: string }
}

interface Props {
  token: string
}

const MAX_MESSAGES = 200

export default function ChatBox({ token }: Props) {
  const [sessionId] = useState<string>(() => {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID()
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`
  })
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<WSMessage[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttemptsRef = useRef<number>(0)
  const reconnectTimerRef = useRef<number | null>(null)
  const isManualCloseRef = useRef<boolean>(false)

  const pushMessage = (data: WSMessage) => {
    setMessages((prev) => {
      const next = [...prev, data]
      return next.length > MAX_MESSAGES ? next.slice(next.length - MAX_MESSAGES) : next
    })
  }

  const wsUrl = useMemo(() => {
    const sid = sessionId ? `?session_id=${sessionId}` : ''
    const wsBase = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000'
    return `${wsBase}/api/chat/ws${sid}`
  }, [sessionId])

  useEffect(() => {
    if (!token) return
    isManualCloseRef.current = false

    const connect = () => {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        reconnectAttemptsRef.current = 0
        ws.send(JSON.stringify({ type: 'auth', token }))
      }

      ws.onmessage = (ev) => {
        const data: WSMessage = JSON.parse(ev.data)
        pushMessage(data)
      }

      ws.onerror = () => {
        pushMessage({ type: 'error', message: 'WebSocket 连接异常' })
      }

      ws.onclose = () => {
        wsRef.current = null
        if (isManualCloseRef.current) return
        if (reconnectAttemptsRef.current >= 5) {
          pushMessage({ type: 'error', message: '连接已断开，重连次数已达上限，请刷新页面重试。' })
          return
        }

        reconnectAttemptsRef.current += 1
        const attempt = reconnectAttemptsRef.current
        const delay = Math.min(1000 * 2 ** (attempt - 1), 30000)
        pushMessage({ type: 'system', message: `连接已断开，正在第 ${attempt} 次重连...` })
        reconnectTimerRef.current = window.setTimeout(() => {
          connect()
        }, delay)
      }
    }

    connect()

    return () => {
      isManualCloseRef.current = true
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [token, wsUrl])

  const sendStart = () => {
    if (!input.trim()) return
    wsRef.current?.send(JSON.stringify({ type: 'start', message: input.trim() }))
    pushMessage({ type: 'user', message: input.trim() })
    setInput('')
  }

  const replyAction = (action: string, value: string) => {
    wsRef.current?.send(JSON.stringify({ type: 'user_action', action, value }))
    pushMessage({ type: 'user', message: `动作 ${action}: ${value}` })
  }

  return (
    <div className="flex flex-col h-full bg-white">
      <div className="flex-1 overflow-auto p-4 space-y-3">
        {messages.map((m, idx) => (
          <div key={idx} className={m.type === 'user' ? 'text-right' : 'text-left'}>
            <div className="inline-block max-w-[80%] rounded px-3 py-2 bg-slate-100 text-sm">
              <p className="font-semibold text-xs mb-1">{m.type}</p>
              <p>{m.message}</p>
              {m.type === 'action_ask_user' && m.payload?.action && (
                <div className="mt-2">
                  <button className="px-2 py-1 bg-blue-600 text-white rounded" onClick={() => replyAction(m.payload!.action!, '已上传')}>
                    已上传，继续
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      <div className="p-3 border-t flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) sendStart()
          }}
          placeholder="描述任务，例如：请分析这个季度报表并生成总结"
          className="flex-1 border rounded px-3 py-2 text-sm"
        />
        <button onClick={sendStart} className="px-3 py-2 bg-indigo-600 text-white rounded text-sm">
          发送
        </button>
      </div>
    </div>
  )
}
