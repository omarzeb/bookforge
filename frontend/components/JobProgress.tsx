'use client'

import { useJobStream } from '@/hooks/useJobStream'
import clsx from 'clsx'

interface Props {
  jobId: string
  onDone?: () => void
  onFailed?: (error: string) => void
  showOutput?: boolean
}

export function JobProgress({ jobId, onDone, onFailed, showOutput = false }: Props) {
  const { status, output, error, done } = useJobStream(jobId)

  if (done && status === 'DONE' && onDone) setTimeout(onDone, 600)
  if (done && status === 'FAILED' && onFailed && error) setTimeout(() => onFailed(error), 300)

  const steps = [
    { key: 'QUEUED',  label: 'Queued' },
    { key: 'RUNNING', label: 'Running' },
    { key: 'DONE',    label: 'Done' },
  ]
  const idx = status === 'QUEUED' ? 0 : status === 'RUNNING' ? 1 : 2

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Steps */}
      <div className="flex items-center gap-3">
        {steps.map((step, i) => {
          const past    = i < idx
          const current = i === idx && status !== 'FAILED'
          const failed  = status === 'FAILED' && i === idx
          return (
            <div key={step.key} className="flex items-center gap-2">
              <div
                className={clsx(
                  'w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium transition-all',
                  past    && 'text-white',
                  current && 'ring-2',
                  failed  && 'ring-2',
                  !past && !current && !failed && 'text-[var(--text-muted)]'
                )}
                style={{
                  background: past ? 'var(--accent)' : current ? 'var(--accent-bg)' : failed ? 'var(--red-bg)' : 'var(--bg-subtle)',
                  ringColor: current ? 'var(--accent)' : 'var(--red)',
                  color: past ? '#fff' : current ? 'var(--accent)' : failed ? 'var(--red)' : 'var(--text-muted)',
                }}
              >
                {past ? '✓' : failed ? '!' : i + 1}
              </div>
              <span className="text-sm" style={{ color: current ? 'var(--text)' : 'var(--text-muted)', fontWeight: current ? '500' : '400' }}>
                {step.label}
              </span>
              {i < steps.length - 1 && (
                <div className="w-8 h-px" style={{ background: past ? 'var(--accent)' : 'var(--border)' }} />
              )}
            </div>
          )
        })}

        {status === 'RUNNING' && (
          <div className="flex gap-1 ml-2">
            {[0, 1, 2].map(i => (
              <span key={i} className="w-1.5 h-1.5 rounded-full animate-pulse-dot"
                style={{ background: 'var(--accent)', animationDelay: `${i * 0.2}s` }} />
            ))}
          </div>
        )}
      </div>

      {/* Error */}
      {status === 'FAILED' && (
        <div className="rounded-xl px-4 py-3 text-sm" style={{ background: 'var(--red-bg)', color: 'var(--red)', border: '1px solid var(--red)' }}>
          <strong>Failed:</strong> {error ?? 'Unknown error'}
        </div>
      )}

      {/* Streaming output */}
      {showOutput && output && (
        <div className="rounded-xl p-4 text-xs font-mono leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto"
          style={{ background: 'var(--slate-950, #080f1a)', color: '#a3e635' }}>
          {output}
          {status === 'RUNNING' && <span className="inline-block w-1.5 h-4 bg-green-400 ml-0.5 animate-pulse" />}
        </div>
      )}
    </div>
  )
}
