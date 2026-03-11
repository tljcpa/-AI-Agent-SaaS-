import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const submit = async () => {
    setError('')
    try {
      const endpoint = mode === 'login' ? '/auth/login' : '/auth/register'
      const res = await api.post(endpoint, { username, password })
      localStorage.setItem('token', res.data.access_token)
      navigate('/dashboard')
    } catch (e: any) {
      setError(e.response?.data?.detail || '请求失败，请重试')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100">
      <div className="bg-white p-6 rounded shadow w-96 space-y-3">
        <h1 className="text-xl font-bold">AI Office SaaS</h1>
        <input
          className="w-full border rounded px-3 py-2"
          placeholder="用户名"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') submit() }}
        />
        <input
          className="w-full border rounded px-3 py-2"
          type="password"
          placeholder="密码"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') submit() }}
        />
        {error && <p className="text-red-500 text-sm">{error}</p>}
        <button className="w-full bg-indigo-600 text-white rounded py-2" onClick={submit}>
          {mode === 'login' ? '登录' : '注册'}
        </button>
        <button className="text-sm text-slate-600" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
          切换到 {mode === 'login' ? '注册' : '登录'}
        </button>
      </div>
    </div>
  )
}
