'use client'

import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { models as modelsApi } from '@/lib/api'

const PINNED_KEY = 'bf_pinned_models'

function getCostLabel(per1k: number | null, hasPricing: boolean) {
  if (!hasPricing || per1k === null) return null
  const perBook = per1k * 30
  if (perBook < 0.05)  return { signs: '$',     label: 'Free to run',  desc: `~$${perBook.toFixed(2)}/book`, tier: 1 }
  if (perBook < 0.20)  return { signs: '$',     label: 'Very cheap',   desc: `~$${perBook.toFixed(2)}/book`, tier: 1 }
  if (perBook < 0.60)  return { signs: '$$',    label: 'Affordable',   desc: `~$${perBook.toFixed(2)}/book`, tier: 2 }
  if (perBook < 1.50)  return { signs: '$$$',   label: 'Mid-range',    desc: `~$${perBook.toFixed(2)}/book`, tier: 3 }
  if (perBook < 4.00)  return { signs: '$$$$',  label: 'Pricier',      desc: `~$${perBook.toFixed(2)}/book`, tier: 4 }
  return               { signs: '$$$$$', label: 'Premium',      desc: `~$${perBook.toFixed(2)}/book`, tier: 5 }
}

const SIGN_COLORS = ['', '#4ade80', '#86efac', '#fbbf24', '#f97316', '#f87171']

const QUALITY: Record<string, { icon: string; label: string; rank: number }> = {
  Recommended: { icon: '⭐', label: 'Great all-rounder', rank: 1 },
  Premium:     { icon: '✨', label: 'Highest quality',   rank: 2 },
  Budget:      { icon: '💰', label: 'Best value',        rank: 3 },
  Other:       { icon: '🔧', label: 'Specific use cases',rank: 4 },
}

const CONTEXT_LABEL = (k: number) =>
  k > 200 ? 'Extremely long books ✓' :
  k > 100 ? 'Very long books ✓' :
  k > 32  ? 'Standard length ✓' : 'Shorter books'

function getPinned(): string[] {
  try { return JSON.parse(localStorage.getItem(PINNED_KEY) ?? '[]') } catch { return [] }
}
function savePinned(ids: string[]) { localStorage.setItem(PINNED_KEY, JSON.stringify(ids)) }

type SortPrice = 'asc' | 'desc' | null
type SortQuality = 'best' | 'budget' | null

export default function ModelsPage() {
  const [curated, setCurated]     = useState<any[]>([])
  const [allModels, setAllModels] = useState<any[]>([])
  const [pinned, setPinnedState]  = useState<string[]>([])
  const [search, setSearch]       = useState('')
  const [syncing, setSyncing]     = useState(false)
  const [loading, setLoading]     = useState(true)
  const [view, setView]           = useState<'my' | 'all'>('my')
  const [sortPrice, setSortPrice]     = useState<SortPrice>(null)
  const [sortQuality, setSortQuality] = useState<SortQuality>(null)

  useEffect(() => {
    setPinnedState(getPinned())
    Promise.all([modelsApi.curated(), modelsApi.all()])
      .then(([c, a]) => { setCurated(c); setAllModels(a) })
      .finally(() => setLoading(false))
  }, [])

  function togglePin(modelId: string) {
    const current = getPinned()
    const next = current.includes(modelId)
      ? current.filter(id => id !== modelId)
      : [...current, modelId]
    savePinned(next)
    setPinnedState(next)
    toast.success(current.includes(modelId) ? 'Removed from your list' : 'Added to your list ✓')
  }

  async function handleSync() {
    setSyncing(true)
    try {
      await modelsApi.sync()
      const [c, a] = await Promise.all([modelsApi.curated(), modelsApi.all()])
      setCurated(c); setAllModels(a)
      toast.success('Pricing loaded ✓')
    } catch (err: any) { toast.error(err.message) }
    finally { setSyncing(false) }
  }

  const curatedIds = new Set(curated.map((m: any) => m.model_id))
  const myModels = [
    ...curated,
    ...allModels.filter((m: any) => pinned.includes(m.model_id) && !curatedIds.has(m.model_id)),
  ]

  const hasPricingData = allModels.some((m: any) => m.completion_price_per_1k != null)

  let displayList = view === 'my' ? myModels : allModels

  // When pricing is loaded, hide models with no pricing data
  if (hasPricingData) {
    displayList = displayList.filter((m: any) => m.completion_price_per_1k != null)
  }

  // Filter by search
  if (search) {
    displayList = displayList.filter((m: any) =>
      (m.name ?? m.model_id).toLowerCase().includes(search.toLowerCase())
    )
  }

  // Sort
  if (sortPrice) {
    displayList = [...displayList].sort((a, b) => {
      const pa = a.completion_price_per_1k ?? Infinity
      const pb = b.completion_price_per_1k ?? Infinity
      return sortPrice === 'asc' ? pa - pb : pb - pa
    })
  } else if (sortQuality) {
    displayList = [...displayList].sort((a, b) => {
      const ra = QUALITY[a.tier]?.rank ?? 99
      const rb = QUALITY[b.tier]?.rank ?? 99
      return sortQuality === 'best' ? ra - rb : rb - ra
    })
  }

  function togglePriceSort() {
    setSortQuality(null)
    setSortPrice(p => p === 'asc' ? 'desc' : p === 'desc' ? null : 'asc')
  }
  function toggleQualitySort() {
    setSortPrice(null)
    setSortQuality(q => q === 'best' ? 'budget' : q === 'budget' ? null : 'best')
  }

  const priceSortLabel = sortPrice === 'asc' ? '💰 Cheapest first ↑' : sortPrice === 'desc' ? '💰 Priciest first ↓' : '💰 Sort by price'
  const qualSortLabel  = sortQuality === 'best' ? '✨ Best quality first' : sortQuality === 'budget' ? '💡 Budget first' : '⭐ Sort by quality'

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl" style={{ color: 'var(--text)' }}>AI Models</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-sub)' }}>
            Choose which AI writers appear when you create a book.
          </p>
        </div>
        <button onClick={handleSync} disabled={syncing} className="btn-secondary text-sm shrink-0">
          {syncing ? 'Loading…' : '💰 Get pricing'}
        </button>
      </div>

      {/* Explainer */}
      <div className="card flex gap-4 items-start py-4"
        style={{ background: 'var(--accent-bg)', borderColor: 'var(--accent)' }}>
        <span className="text-2xl shrink-0">💡</span>
        <div>
          <p className="text-sm font-medium" style={{ color: 'var(--text)' }}>What are AI models?</p>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-sub)' }}>
            Think of them as different AI writers — each with their own writing style, quality, and cost per book.
            We include the best ones by default, but you can add more from the full list.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex gap-1 p-1 rounded-xl"
          style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
          {([['my', `⭐ My writers (${myModels.length})`], ['all', `🌐 All available (${allModels.length || '?'})`]] as const).map(([k, label]) => (
            <button key={k} onClick={() => { setView(k); setSearch(''); setSortPrice(null); setSortQuality(null) }}
              className="px-4 py-1.5 rounded-lg text-sm transition-all"
              style={{
                background: view === k ? 'var(--bg-card)' : 'transparent',
                color: view === k ? 'var(--text)' : 'var(--text-sub)',
                border: view === k ? '1px solid var(--border)' : '1px solid transparent',
                fontWeight: view === k ? '500' : '400',
              }}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Filters — only shown for "All" */}
      {view === 'all' && (
        <div className="flex items-center gap-2 flex-wrap">
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search models…" className="input w-48 text-sm py-1.5" />

          <button onClick={togglePriceSort}
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
            style={{
              background: sortPrice ? 'var(--accent)' : 'var(--bg-subtle)',
              color: sortPrice ? '#fff' : 'var(--text-sub)',
              border: '1px solid var(--border)',
            }}>
            {priceSortLabel}
          </button>

          <button onClick={toggleQualitySort}
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
            style={{
              background: sortQuality ? 'var(--accent)' : 'var(--bg-subtle)',
              color: sortQuality ? '#fff' : 'var(--text-sub)',
              border: '1px solid var(--border)',
            }}>
            {qualSortLabel}
          </button>

          {(search || sortPrice || sortQuality) && (
            <button onClick={() => { setSearch(''); setSortPrice(null); setSortQuality(null) }}
              className="text-xs px-2 py-1 rounded" style={{ color: 'var(--text-muted)' }}>
              ✕ Clear
            </button>
          )}
        </div>
      )}

      {/* Model cards */}
      {loading ? (
        <div className="space-y-3">
          {[1,2,3].map(i => <div key={i} className="card h-20 animate-pulse" style={{ background: 'var(--bg-subtle)' }} />)}
        </div>
      ) : displayList.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-3xl mb-3">🔍</p>
          <p className="font-display text-xl" style={{ color: 'var(--text)' }}>
            {view === 'all' && allModels.length === 0 ? 'No models loaded yet' : 'Nothing found'}
          </p>
          {view === 'all' && allModels.length === 0 && (
            <div className="mt-4">
              <button onClick={handleSync} disabled={syncing} className="btn-primary">
                {syncing ? 'Loading…' : '💰 Load models & pricing'}
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {displayList.map((m: any) => {
            const isCurated = curatedIds.has(m.model_id)
            const isPinned  = pinned.includes(m.model_id)
            const cost      = getCostLabel(m.completion_price_per_1k ?? null, hasPricingData)
            const quality   = QUALITY[m.tier]

            return (
              <div key={m.model_id}
                className="card flex items-center gap-4 py-3.5 px-5 transition-all hover:border-[var(--accent)]">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium text-sm" style={{ color: 'var(--text)' }}>
                      {m.name ?? m.model_id.split('/').pop()}
                    </span>
                    {isCurated && <span className="badge badge-green text-xs">✓ Included</span>}
                    {isPinned && !isCurated && <span className="badge badge-blue text-xs">✓ Added by you</span>}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 text-xs flex-wrap" style={{ color: 'var(--text-muted)' }}>
                    {quality && <span>{quality.icon} {quality.label}</span>}
                    {m.context_k && <span>· {CONTEXT_LABEL(m.context_k)}</span>}
                  </div>
                </div>

                {/* Cost */}
                <div className="shrink-0 text-right hidden sm:block min-w-[120px]">
                  {cost ? (
                    <>
                      <div className="font-mono font-bold text-sm" style={{ color: SIGN_COLORS[cost.tier] }}>
                        {cost.signs}
                        <span className="font-normal text-xs ml-1" style={{ color: 'var(--text-sub)' }}>
                          {cost.label}
                        </span>
                      </div>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{cost.desc}</p>
                    </>
                  ) : hasPricingData ? (
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>No pricing data</span>
                  ) : (
                    <button onClick={handleSync} disabled={syncing}
                      className="text-xs underline" style={{ color: 'var(--accent)' }}>
                      {syncing ? 'Loading…' : 'Get pricing'}
                    </button>
                  )}
                </div>

                {/* Action */}
                <div className="shrink-0">
                  {isCurated ? (
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Always available</span>
                  ) : (
                    <button onClick={() => togglePin(m.model_id)}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                      style={{
                        background: isPinned ? 'var(--red-bg)' : 'var(--bg-subtle)',
                        color: isPinned ? 'var(--red)' : 'var(--accent)',
                        border: `1px solid ${isPinned ? 'var(--red)' : 'var(--accent)'}`,
                      }}>
                      {isPinned ? '✕ Remove' : '+ Add to my list'}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
