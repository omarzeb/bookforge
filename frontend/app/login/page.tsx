'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { auth } from '@/lib/api'
import { setToken } from '@/lib/auth'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const { access_token } = await auth.login(email, password)
      setToken(access_token)
      router.push('/books')
    } catch (err: any) {
      toast.error(err.message ?? 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4"
      style={{ background: 'var(--bg)' }}>

      {/* Back to landing */}
      <Link href="/" className="mb-8 flex items-center gap-2 text-sm transition-opacity hover:opacity-70"
        style={{ color: 'var(--text-sub)' }}>
        ← Back to BookForge
      </Link>

      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <Link href="/" className="font-display text-2xl" style={{ color: 'var(--text)' }}>BookForge</Link>
          <p className="text-sm mt-2" style={{ color: 'var(--text-sub)' }}>Welcome back</p>
        </div>

        <div className="card space-y-5">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-sub)' }}>Email</label>
              <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com" className="input" />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-sub)' }}>Password</label>
              <input type="password" required value={password} onChange={e => setPassword(e.target.value)}
                placeholder="••••••••" className="input" />
            </div>
            <button type="submit" disabled={loading} className="btn-primary w-full justify-center py-2.5">
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <div className="pt-1 border-t text-center" style={{ borderColor: 'var(--border)' }}>
            <p className="text-sm" style={{ color: 'var(--text-sub)' }}>
              No account yet?{' '}
              <Link href="/register" className="font-medium underline" style={{ color: 'var(--accent)' }}>
                Create one free
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
