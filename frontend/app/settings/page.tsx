'use client'

import { useState } from 'react'
import toast from 'react-hot-toast'
import { PromptEditor } from '@/components/PromptEditor'
import { models as modelsApi } from '@/lib/api'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080'

const KEY_STEPS = [
  {
    n: '1',
    title: 'Create a free account',
    desc: "Go to openrouter.ai and sign up. It's free — no credit card needed just to register.",
    link: { href: 'https://openrouter.ai', label: 'Go to openrouter.ai →' },
  },
  {
    n: '2',
    title: 'Add a small amount of credits',
    desc: 'Go to Settings → Credits and add $5 or so. Most AI models cost pennies per book — $5 will get you hundreds of chapters.',
    link: { href: 'https://openrouter.ai/settings/credits', label: 'Add credits →' },
  },
  {
    n: '3',
    title: 'Create an API key',
    desc: 'Go to Settings → Keys and click "Create Key". Give it any name (e.g. "BookForge"). Copy the full key — it starts with sk-or-v1-…',
    link: { href: 'https://openrouter.ai/settings/keys', label: 'Create my key →' },
  },
  {
    n: '4',
    title: 'Paste it below and click Save',
    desc: "Paste the key into the field below. We'll make a quick test call to confirm it works before saving.",
    link: null,
  },
]

export default function SettingsPage() {
  const [apiKey, setApiKey]         = useState('')
  const [saving, setSaving]         = useState(false)
  const [syncing, setSyncing]       = useState(false)
  const [tab, setTab]               = useState<'key' | 'prompts'>('key')
  const [showGuide, setShowGuide]   = useState(false)

  async function handleSaveKey(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      const { getToken } = await import('@/lib/auth')
      const res = await fetch(`${API_BASE}/api/v1/settings/openrouter-key`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ api_key: apiKey }),
      })
      if (!res.ok) throw new Error((await res.json()).detail ?? 'Failed')
      toast.success('Key saved and validated ✓')
      setApiKey('')
      setShowGuide(false)
    } catch (err: any) { toast.error(err.message) }
    finally { setSaving(false) }
  }

  async function handleSync() {
    setSyncing(true)
    try {
      await modelsApi.sync()
      toast.success('Model list updated ✓')
    } catch (err: any) { toast.error(err.message) }
    finally { setSyncing(false) }
  }

  return (
    <div className="space-y-8 animate-fade-in max-w-3xl">
      <div>
        <h1 className="font-display text-3xl" style={{ color: 'var(--text)' }}>Settings</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-sub)' }}>
          Manage your API key and customise how the AI writes.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl w-fit"
        style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
        {([['key', 'API Key'], ['prompts', 'Prompt Editor']] as const).map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            className="px-4 py-1.5 rounded-lg text-sm transition-all"
            style={{
              background: tab === k ? 'var(--bg-card)' : 'transparent',
              color: tab === k ? 'var(--text)' : 'var(--text-sub)',
              fontWeight: tab === k ? '500' : '400',
              border: tab === k ? '1px solid var(--border)' : '1px solid transparent',
            }}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'key' && (
        <div className="space-y-6 animate-fade-in">

          {/* API Key card */}
          <div className="card space-y-5">
            <div>
              <h2 className="font-display text-xl" style={{ color: 'var(--text)' }}>OpenRouter API Key</h2>
              <p className="text-sm mt-1" style={{ color: 'var(--text-sub)' }}>
                BookForge uses OpenRouter to access AI writing models.
                You need a free account and an API key to get started.
              </p>
            </div>

            {/* Guide toggle */}
            {!showGuide ? (
              <button
                onClick={() => setShowGuide(true)}
                className="flex items-center gap-2.5 text-sm w-fit group"
                style={{ color: 'var(--accent)' }}
              >
                <span
                  className="w-6 h-6 rounded-full border-2 flex items-center justify-center text-xs font-bold shrink-0 transition-all group-hover:bg-[var(--accent)] group-hover:text-white"
                  style={{ borderColor: 'var(--accent)', color: 'var(--accent)' }}
                >
                  ?
                </span>
                <span className="underline underline-offset-2">How do I get an API key?</span>
              </button>
            ) : (
              <div className="rounded-xl overflow-hidden border"
                style={{ borderColor: 'var(--accent)' }}>
                {/* Guide header */}
                <div className="flex items-center justify-between px-4 py-3"
                  style={{ background: 'var(--accent-bg)', borderBottom: '1px solid var(--accent)' }}>
                  <div className="flex items-center gap-2">
                    <span className="text-base">🗝️</span>
                    <span className="text-sm font-medium" style={{ color: 'var(--accent)' }}>
                      How to get your API key — 4 easy steps
                    </span>
                  </div>
                  <button
                    onClick={() => setShowGuide(false)}
                    className="text-xs px-2 py-1 rounded hover:bg-black/10 transition-all"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    ✕ Close
                  </button>
                </div>

                {/* Steps */}
                <div className="p-4 space-y-5" style={{ background: 'var(--bg-card)' }}>
                  {KEY_STEPS.map((step, i) => (
                    <div key={step.n} className="flex gap-3">
                      <div
                        className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5"
                        style={{ background: 'var(--accent)', color: '#fff' }}
                      >
                        {step.n}
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-medium" style={{ color: 'var(--text)' }}>
                          {step.title}
                        </p>
                        <p className="text-xs mt-1 leading-relaxed" style={{ color: 'var(--text-sub)' }}>
                          {step.desc}
                        </p>
                        {step.link && (
                          <a
                            href={step.link.href}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-xs mt-1.5 underline underline-offset-2 font-medium"
                            style={{ color: 'var(--accent)' }}
                          >
                            {step.link.label}
                          </a>
                        )}
                      </div>
                    </div>
                  ))}

                  {/* Cost tip */}
                  <div className="rounded-lg p-3 text-xs leading-relaxed"
                    style={{ background: 'var(--bg-subtle)', color: 'var(--text-sub)', border: '1px solid var(--border)' }}>
                    💡 <strong style={{ color: 'var(--text)' }}>Cost tip:</strong>{' '}
                    Start with $5 of credits. GPT-4o Mini costs about $0.02 per full book —
                    that's 250 books for $5. Most books end up costing less than a cup of coffee.
                  </div>
                </div>
              </div>
            )}

            {/* Key input */}
            <form onSubmit={handleSaveKey} className="space-y-3">
              <div className="flex gap-3">
                <input
                  type="password"
                  required
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  placeholder="sk-or-v1-…"
                  className="input flex-1 font-mono text-sm"
                />
                <button type="submit" disabled={saving} className="btn-primary shrink-0">
                  {saving ? 'Checking key…' : 'Save key'}
                </button>
              </div>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                🔒 Your key is encrypted before storage and never logged or shared.
              </p>
            </form>
          </div>

          {/* Model sync card */}
          <div className="card space-y-4">
            <div>
              <h2 className="font-display text-xl" style={{ color: 'var(--text)' }}>Update Model List</h2>
              <p className="text-sm mt-1" style={{ color: 'var(--text-sub)' }}>
                Fetch the latest AI models and pricing from OpenRouter.
                Run this after saving your key — it loads which models are available and what they cost per book.
              </p>
            </div>
            <button onClick={handleSync} disabled={syncing} className="btn-secondary">
              {syncing ? 'Updating…' : '🔄 Update model list & pricing'}
            </button>
          </div>
        </div>
      )}

      {tab === 'prompts' && (
        <div className="card animate-fade-in">
          <PromptEditor />
        </div>
      )}
    </div>
  )
}
