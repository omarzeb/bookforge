'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { models as modelsApi } from '@/lib/api'
import type { CuratedModel } from '@/lib/types'

const PINNED_KEY = 'bf_pinned_models'
const TIER_DOT: Record<string, string> = {
  Recommended: 'bg-green-400',
  Budget:      'bg-blue-400',
  Premium:     'bg-amber-400',
  Other:       'bg-gray-400',
}

function getPinned(): string[] {
  try { return JSON.parse(localStorage.getItem(PINNED_KEY) ?? '[]') }
  catch { return [] }
}

interface Props {
  value: string
  onChange: (id: string) => void
  disabled?: boolean
}

export function ModelDropdown({ value, onChange, disabled }: Props) {
  const [curated, setCurated]   = useState<CuratedModel[]>([])
  const [allModels, setAll]     = useState<any[]>([])
  const [pinned, setPinned]     = useState<string[]>([])
  const [open, setOpen]         = useState(false)
  const [search, setSearch]     = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setPinned(getPinned())
    modelsApi.curated().then(setCurated).catch(() => {})
    modelsApi.all().then(setAll).catch(() => {})
  }, [])

  // Refresh pinned list when dropdown opens (user may have changed it on models page)
  useEffect(() => {
    if (open) setPinned(getPinned())
  }, [open])

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Build the list: curated + pinned extras
  const curatedIds = new Set(curated.map(m => m.model_id))
  const pinnedExtras = allModels.filter(m => pinned.includes(m.model_id) && !curatedIds.has(m.model_id))
  const hasPricing = allModels.some((m: any) => m.completion_price_per_1k != null)
  const allItems: any[] = [...curated, ...pinnedExtras.map(m => ({ ...m, tier: m.tier ?? 'Other' }))]
  // Hide models without pricing once pricing data is available
  const dropdownList = hasPricing
    ? allItems.filter(m => m.completion_price_per_1k != null)
    : allItems

  const filtered = dropdownList.filter(m =>
    !search ||
    m.name?.toLowerCase().includes(search.toLowerCase()) ||
    m.model_id?.toLowerCase().includes(search.toLowerCase())
  )

  const selected = dropdownList.find(m => m.model_id === value)

  function formatPrice(m: any) {
    if (!m.completion_price_per_1k) return '—'
    return `$${Number(m.completion_price_per_1k).toFixed(4)}/1k`
  }

  return (
    <div ref={ref} className="relative">
      {/* Trigger */}
      <button type="button" disabled={disabled} onClick={() => setOpen(o => !o)}
        className="input flex items-center justify-between cursor-pointer text-left">
        <div className="flex items-center gap-2 min-w-0">
          {selected ? (
            <>
              <span className={`w-2 h-2 rounded-full shrink-0 ${TIER_DOT[selected.tier] ?? 'bg-gray-400'}`} />
              <span className="truncate text-sm">{selected.name}</span>
            </>
          ) : (
            <span className="text-sm" style={{ color: 'var(--text-muted)' }}>Select a model…</span>
          )}
        </div>
        <span className="ml-2 shrink-0 text-xs" style={{ color: 'var(--text-muted)' }}>▾</span>
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 mt-1.5 w-full rounded-xl border shadow-2xl animate-fade-in overflow-hidden"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', maxHeight: '360px', display: 'flex', flexDirection: 'column' }}>

          {/* Search */}
          <div className="p-2 border-b" style={{ borderColor: 'var(--border)' }}>
            <input autoFocus value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search models…" className="input text-xs py-1.5" />
          </div>

          {/* Model list */}
          <div className="overflow-y-auto flex-1">
            {filtered.length === 0 && (
              <p className="text-sm text-center py-6" style={{ color: 'var(--text-muted)' }}>No models found</p>
            )}
            {filtered.map(m => (
              <button key={m.model_id} type="button"
                onClick={() => { onChange(m.model_id); setOpen(false); setSearch('') }}
                className="w-full flex items-center justify-between px-3 py-2.5 text-left transition-all duration-100"
                style={{ background: m.model_id === value ? 'var(--accent-bg)' : 'transparent', color: 'var(--text)' }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-subtle)')}
                onMouseLeave={e => (e.currentTarget.style.background = m.model_id === value ? 'var(--accent-bg)' : 'transparent')}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${TIER_DOT[m.tier] ?? 'bg-gray-400'}`} />
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{m.name}</div>
                    <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{m.context_k}k ctx · {m.tier}</div>
                  </div>
                </div>
                <span className="text-xs ml-3 shrink-0 font-mono" style={{ color: 'var(--text-muted)' }}>
                  {formatPrice(m)}
                </span>
              </button>
            ))}
          </div>

          {/* Footer — link to model library */}
          <div className="border-t p-2" style={{ borderColor: 'var(--border)', background: 'var(--bg-subtle)' }}>
            <Link href="/models" onClick={() => setOpen(false)}
              className="flex items-center justify-center gap-1.5 text-xs py-1.5 rounded-lg transition-all hover:underline"
              style={{ color: 'var(--accent)' }}>
              🌐 Browse & pin more models →
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
