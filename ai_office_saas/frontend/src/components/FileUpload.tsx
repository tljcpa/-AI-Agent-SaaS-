import { ChangeEvent, useState } from 'react'
import api from '../api/client'

interface Props {
  onUploaded: () => void
}

export default function FileUpload({ onUploaded }: Props) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const form = new FormData()
    form.append('file', file)

    setUploading(true)
    setError('')
    try {
      await api.post('/files/upload', form)
      onUploaded()
    } catch (e: any) {
      setError(e.response?.data?.detail || '上传失败')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="p-3 border-b bg-white">
      <label className="block text-sm font-medium text-slate-700 mb-2">上传文件</label>
      <input type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.txt" onChange={handleUpload} className="w-full text-sm" />
      {uploading && <p className="text-xs text-blue-600 mt-1">上传中...</p>}
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  )
}
