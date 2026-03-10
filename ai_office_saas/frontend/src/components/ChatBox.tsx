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

export default function ChatBox({ token }: Props) {
  const [sessionId, setSessionId] = useState<string>('')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<WSMessage[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  const wsUrl = useMemo(() => {
    const sid = sessionId ? `&session_id=${sessionId}` : ''
    return `ws://localhost:8000/api/chat/ws?token=${token}${sid}`
  }, [token, sessionId])

  useEffect(() => {
    if (!token) return
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onmessage = (ev) => {
      const data: WSMessage = JSON.parse(ev.data)
      if (data.session_id) {
        setSessionId((prev) => prev || data.session_id || '')
      }
      setMessages((prev) => [...prev, data])
    }

    ws.onerror = () => {
      setMessages((prev) => [...prev, { type: 'error', message: 'WebSocket 连接异常' }])
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [token, wsUrl])

  const sendStart = () => {
    if (!input.trim()) return
    wsRef.current?.send(JSON.stringify({ type: 'start', message: input.trim() }))
    setMessages((prev) => [...prev, { type: 'user', message: input.trim() }])
    setInput('')
  }

  const replyAction = (action: string, value: string) => {
    wsRef.current?.send(JSON.stringify({ type: 'user_action', action, value }))
    setMessages((prev) => [...prev, { type: 'user', message: `动作 ${action}: ${value}` }])
  }

  return (
    <div className="flex flex-col h-full bg-white">
      <div className="flex-1 overflow-auto p-4 space-y-3">
        {messages.map((m, idx) => (
          <div key={idx} className={m.type === 'user' ? 'text-right' : 'text-left'}>
            <div className="inline-block max-w-[80%] rounded px-3 py-2 bg-slate-100 text-sm">
              <p className="font-semibold text-xs mb-1">{m.type}</p>
              <p>{m.message}</p>
              {m.type === 'action_confirm' && m.payload?.action && (
                <div className="mt-2 space-x-2">
                  <button className="px-2 py-1 bg-green-600 text-white rounded" onClick={() => replyAction(m.payload!.action!, 'confirm')}>
                    确认
                  </button>
                  <button className="px-2 py-1 bg-red-500 text-white rounded" onClick={() => replyAction(m.payload!.action!, 'cancel')}>
                    取消
                  </button>
                </div>
              )}
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
