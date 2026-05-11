'use client'

import { useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import Link from 'next/link'
import { isAuthenticated, clearToken } from '@/lib/auth'
import { ThemeToggle } from '@/components/ThemeToggle'

const NAV = [
  { href: '/books',    label: 'My Books',  icon: '📚' },
  { href: '/models',   label: 'Models',    icon: '🤖' },
  { href: '/settings', label: 'Settings',  icon: '⚙️' },
]

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router   = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    const saved = localStorage.getItem('theme')
    document.documentElement.classList.toggle('dark', saved !== 'light')
  }, [])

  useEffect(() => {
    if (!isAuthenticated()) router.push('/login')
  }, [pathname, router])

  return (
    // Full height, no overflow on outer container
    <div className="flex h-screen overflow-hidden">

      {/* Sidebar — fixed height, never scrolls */}
      <aside
        className="w-56 shrink-0 border-r flex flex-col h-screen"
        style={{ background: 'var(--bg-subtle)', borderColor: 'var(--border)' }}
      >
        {/* Logo */}
        <Link
          href="/books"
          className="px-5 py-5 border-b block hover:opacity-80 transition-opacity shrink-0"
          style={{ borderColor: 'var(--border)' }}
        >
          <span className="font-display text-xl" style={{ color: 'var(--text)' }}>BookForge</span>
        </Link>

        {/* Nav links */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(item => {
            const active = pathname.startsWith(item.href)
            return (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150"
                style={{
                  background:  active ? 'var(--bg-card)' : 'transparent',
                  color:       active ? 'var(--text)'    : 'var(--text-sub)',
                  border:      active ? '1px solid var(--border)' : '1px solid transparent',
                  fontWeight:  active ? '500' : '400',
                }}
              >
                <span>{item.icon}</span>
                {item.label}
              </Link>
            )
          })}
        </nav>

        {/* Bottom bar */}
        <div
          className="px-3 py-4 border-t flex items-center justify-between shrink-0"
          style={{ borderColor: 'var(--border)' }}
        >
          <ThemeToggle />
          <button
            onClick={() => { clearToken(); router.push('/') }}
            className="btn-ghost text-xs"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content — scrolls independently */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-8 py-8">
          {children}
        </div>
      </main>
    </div>
  )
}
