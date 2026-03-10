import { useEffect, useState } from 'react'
import api from '../api/client'
import ChatBox from '../components/ChatBox'
import FileUpload from '../components/FileUpload'

export default function Dashboard() {
  const [files, setFiles] = useState<string[]>([])
  const token = localStorage.getItem('token') || ''

  const loadFiles = async () => {
    const res = await api.get('/files')
    setFiles(res.data.items)
  }

  useEffect(() => {
    loadFiles()
  }, [])

  return (
    <div className="h-screen flex">
      <aside className="w-72 border-r bg-slate-50 flex flex-col">
        <FileUpload onUploaded={loadFiles} />
        <div className="p-3 overflow-auto">
          <h2 className="font-semibold mb-2">文件列表</h2>
          <ul className="space-y-1 text-sm">
            {files.map((name) => (
              <li key={name} className="bg-white rounded px-2 py-1 border">
                {name}
              </li>
            ))}
          </ul>
        </div>
      </aside>
      <main className="flex-1">
        <ChatBox token={token} />
      </main>
    </div>
  )
}
