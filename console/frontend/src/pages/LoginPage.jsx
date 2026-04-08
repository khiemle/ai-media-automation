import { useState } from 'react'
import { authApi, setToken } from '../api/client.js'
import { Button, Input } from '../components/index.jsx'

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState(null)
  const [loading, setLoading]   = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await authApi.login(username, password)
      onLogin(res.access_token, res.user)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0d0d0f] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="w-10 h-10 rounded-xl bg-[#7c6af7] flex items-center justify-center">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="white">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          <div>
            <div className="font-bold text-[#e8e8f0] text-lg leading-none">AI Media Console</div>
            <div className="text-xs text-[#9090a8] font-mono mt-0.5">Management Dashboard</div>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-[#1c1c22] border border-[#2a2a32] rounded-2xl p-6 flex flex-col gap-4">
          <h1 className="text-sm font-semibold text-[#e8e8f0] text-center">Sign in</h1>

          <Input
            label="Username"
            value={username}
            onChange={e => setUsername(e.target.value)}
            placeholder="admin"
            autoFocus
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="••••••••"
          />

          {error && (
            <div className="text-xs text-[#f87171] bg-[#1e0a0a] border border-[#3a1010] rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <Button type="submit" variant="primary" loading={loading} className="w-full justify-center mt-1">
            Sign in
          </Button>
        </form>
      </div>
    </div>
  )
}
