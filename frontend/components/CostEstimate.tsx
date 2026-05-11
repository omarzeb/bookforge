'use client'

import { useEffect, useState } from 'react'
import { models as modelsApi } from '@/lib/api'
import type { CostEstimate } from '@/lib/types'

interface Props { modelId: string; chapters: number }

export function CostEstimate({ modelId, chapters }: Props) {
  const [est, setEst] = useState<CostEstimate | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!modelId || !chapters) return
    setLoading(true)
    modelsApi.estimate(modelId, chapters)
      .then(setEst).catch(() => setEst(null))
      .finally(() => setLoading(false))
  }, [modelId, chapters])

  if (loading) return <p className="text-xs animate-pulse" style={{ color: 'var(--text-muted)' }}>Estimating…</p>
  if (!est || est.low_usd === null) return (
    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Pricing unavailable — sync models first</p>
  )

  return (
    <p className="text-xs" style={{ color: 'var(--text-sub)' }}>
      Estimated cost:{' '}
      <span className="font-medium font-mono" style={{ color: 'var(--accent)' }}>
        ${est.low_usd.toFixed(3)}–${est.high_usd?.toFixed(3)}
      </span>
      {' '}for {chapters} chapters
      {est.note && <span className="ml-2" style={{ color: 'var(--accent)' }}>· {est.note}</span>}
    </p>
  )
}
