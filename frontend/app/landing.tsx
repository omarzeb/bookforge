'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { isAuthenticated } from '@/lib/auth'

const STEPS = [
  { n: '1', title: 'Tell us about your book', desc: 'Give your book a title and describe what it should cover. A sentence or two is enough to get started.', bg: 'from-amber-950/30 to-slate-950' },
  { n: '2', title: 'Review the outline', desc: "We'll suggest a chapter structure. Read it, request changes, or approve it when you're happy.", bg: 'from-blue-950/30 to-slate-950' },
  { n: '3', title: "Read each chapter as it's written", desc: 'Chapters are written one by one. You can revise any chapter before moving on.', bg: 'from-purple-950/30 to-slate-950' },
  { n: '4', title: 'Download your finished book', desc: "When you've approved everything, download your complete book as a Word document.", bg: 'from-green-950/30 to-slate-950' },
]

const FEATURES = [
  { icon: '✍️', title: 'Your idea, fully written', desc: "Describe what you want to write. BookForge creates a structured outline, then writes each chapter — one at a time, at your pace." },
  { icon: '👁️', title: 'You stay in control', desc: "Read every chapter before it becomes part of your book. Ask for changes, give notes, or approve it and move on." },
  { icon: '🔐', title: 'Your content is private', desc: "Your writing never trains anyone's AI. Your account details are encrypted and never shared." },
  { icon: '📥', title: 'Ready to publish or print', desc: 'Download your finished book as a Word document or plain text — ready for editing, publishing, or sharing.' },
]

export default function LandingPage() {
  const [loggedIn, setLoggedIn] = useState(false)

  useEffect(() => {
    setLoggedIn(isAuthenticated())
    const saved = localStorage.getItem('theme')
    document.documentElement.classList.toggle('dark', saved !== 'light')
  }, [])

  return (
    <div className="dark" style={{ background: '#0a0f1a', color: '#e8e2d9' }}>

      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b backdrop-blur-xl"
        style={{ borderColor: 'rgba(255,255,255,0.06)', background: 'rgba(10,15,26,0.8)' }}>
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <span className="font-display text-xl" style={{ color: '#e8e2d9' }}>BookForge</span>
          <div className="flex items-center gap-3">
            {loggedIn ? (
              <Link href="/books"
                className="px-4 py-2 rounded-lg text-sm font-medium transition-all hover:scale-105"
                style={{ background: '#f59e0b', color: '#fff' }}>
                My books →
              </Link>
            ) : (
              <>
                <Link href="/login" className="text-sm px-3 py-2 rounded-lg transition-all hover:bg-white/5"
                  style={{ color: '#8a9ab5' }}>
                  Sign in
                </Link>
                <Link href="/register"
                  className="px-4 py-2 rounded-lg text-sm font-medium transition-all hover:scale-105"
                  style={{ background: '#f59e0b', color: '#fff' }}>
                  Start writing
                </Link>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* Section 1 — Hero */}
      <section className="relative min-h-screen flex flex-col items-center justify-center text-center px-6 overflow-hidden">
        {/* Gradient orbs */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full opacity-20 blur-[120px]"
            style={{ background: 'radial-gradient(circle, #f59e0b 0%, transparent 70%)' }} />
          <div className="absolute top-1/3 left-1/4 w-96 h-96 rounded-full opacity-10 blur-[80px]"
            style={{ background: '#7c3aed' }} />
          <div className="absolute top-1/3 right-1/4 w-64 h-64 rounded-full opacity-10 blur-[80px]"
            style={{ background: '#2563eb' }} />
        </div>

        <div className="relative max-w-3xl animate-fade-in">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium mb-10"
            style={{ background: 'rgba(245,158,11,0.1)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)' }}>
            ✦ AI-powered book writing
          </div>

          <h1 className="font-display font-light leading-none tracking-tight mb-6"
            style={{ fontSize: 'clamp(3rem, 8vw, 5.5rem)', color: '#f0ebe3' }}>
            From idea to finished book,<br />
            <span style={{ color: '#f59e0b' }}>chapter by chapter.</span>
          </h1>

          <p className="text-lg max-w-lg mx-auto leading-relaxed mb-10" style={{ color: '#8a9ab5' }}>
            Describe the book you want to write. BookForge writes it with you —
            drafting each chapter while you read, revise, and give feedback along the way.
          </p>

          <Link href="/register"
            className="inline-flex items-center gap-2 px-8 py-4 rounded-xl text-lg font-medium transition-all duration-300 hover:scale-105 hover:shadow-2xl"
            style={{ background: '#f59e0b', color: '#0a0f1a', boxShadow: '0 0 40px rgba(245,158,11,0.3)' }}>
            Start writing your book →
          </Link>

          <p className="text-sm mt-5" style={{ color: '#4a5a72' }}>
            Already have an account?{' '}
            <Link href="/login" className="underline" style={{ color: '#f59e0b' }}>Sign in</Link>
          </p>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2"
          style={{ color: '#4a5a72' }}>
          <span className="text-xs uppercase tracking-widest">Scroll to explore</span>
          <div className="w-5 h-8 rounded-full border flex items-start justify-center pt-1.5"
            style={{ borderColor: '#4a5a72' }}>
            <div className="w-1 h-2 rounded-full animate-bounce" style={{ background: '#f59e0b' }} />
          </div>
        </div>
      </section>

      {/* Section 2 — Steps */}
      <section className="py-32 px-6" style={{ background: '#0d1420' }}>
        <div className="max-w-5xl mx-auto">
          <p className="text-center text-xs font-medium uppercase tracking-widest mb-4"
            style={{ color: '#f59e0b' }}>How it works</p>
          <h2 className="font-display font-light text-center mb-20"
            style={{ color: '#f0ebe3', fontSize: '2.8rem' }}>
            Simple from start to finish
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-12">
            {STEPS.map((step, i) => (
              <div key={step.n} className="space-y-4 group">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center text-base font-medium transition-all group-hover:scale-110"
                  style={{ background: 'rgba(245,158,11,0.1)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.25)' }}>
                  {step.n}
                </div>
                <h3 className="font-display font-light text-xl leading-snug" style={{ color: '#e8e2d9' }}>
                  {step.title}
                </h3>
                <p className="text-sm leading-relaxed" style={{ color: '#6a7a92' }}>{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Section 3 — Features */}
      <section className="py-32 px-6" style={{ background: '#0a0f1a' }}>
        <div className="max-w-5xl mx-auto">
          <p className="text-center text-xs font-medium uppercase tracking-widest mb-4"
            style={{ color: '#f59e0b' }}>Why BookForge</p>
          <h2 className="font-display font-light text-center mb-16"
            style={{ color: '#f0ebe3', fontSize: '2.8rem' }}>
            Writing that works the way you do
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {FEATURES.map(f => (
              <div key={f.title}
                className="rounded-xl p-6 flex gap-5 transition-all duration-300 hover:translate-y-[-2px]"
                style={{ background: '#141d2e', border: '1px solid #1e2b3d' }}>
                <span className="text-3xl shrink-0">{f.icon}</span>
                <div>
                  <h3 className="font-display font-light text-xl mb-2" style={{ color: '#e8e2d9' }}>{f.title}</h3>
                  <p className="text-sm leading-relaxed" style={{ color: '#6a7a92' }}>{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Section 4 — Final CTA */}
      <section className="py-40 px-6 text-center relative overflow-hidden"
        style={{ background: '#0d1420' }}>
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] opacity-15 blur-[100px]"
            style={{ background: 'radial-gradient(ellipse, #f59e0b 0%, transparent 70%)' }} />
        </div>
        <div className="relative max-w-xl mx-auto">
          <h2 className="font-display font-light mb-5"
            style={{ color: '#f0ebe3', fontSize: '3rem' }}>
            Your book is waiting to be written
          </h2>
          <p className="text-base mb-10 leading-relaxed" style={{ color: '#8a9ab5' }}>
            Join writers turning their ideas into complete books. Free to get started.
          </p>
          <Link href="/register"
            className="inline-flex items-center gap-2 px-8 py-4 rounded-xl text-lg font-medium transition-all duration-300 hover:scale-105"
            style={{ background: '#f59e0b', color: '#0a0f1a', boxShadow: '0 0 60px rgba(245,158,11,0.25)' }}>
            Write my book →
          </Link>
          <p className="text-xs mt-10" style={{ color: '#2a3a52' }}>
            © 2026 BookForge · Your words, your book
          </p>
        </div>
      </section>
    </div>
  )
}
