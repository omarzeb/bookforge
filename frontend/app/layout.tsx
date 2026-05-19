import type { Metadata } from 'next'
import { Toaster } from 'react-hot-toast'
import { ThemeInit } from '@/components/ThemeInit'
import './globals.css'

export const metadata: Metadata = {
  title: 'BookForge — AI book generation',
  description: 'Generate full-length books with AI. Bring your own OpenRouter key.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ThemeInit />
        {children}
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: 'var(--bg-card)',
              color: 'var(--text)',
              border: '1px solid var(--border)',
              borderRadius: '10px',
              fontSize: '14px',
            },
          }}
        />
      </body>
    </html>
  )
}
