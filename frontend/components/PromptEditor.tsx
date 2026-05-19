'use client'

import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { prompts as promptsApi } from '@/lib/api'

const PINNED_KEY = 'bf_pinned_models'

const STAGES = [
  { key: 'outline',          label: 'Outline',          desc: 'How the AI plans your book structure' },
  { key: 'chapter',          label: 'Writing chapters',  desc: 'How the AI writes each chapter' },
  { key: 'chapter_revision', label: 'Revising',          desc: 'How the AI rewrites after your feedback' },
  { key: 'summary',          label: 'Summarising',       desc: 'How the AI summarises chapters for continuity' },
]

// Model families mapped to model name fragments for matching
const FAMILY_FRAGMENTS: Record<string, string[]> = {
  claude:   ['claude'],
  gpt:      ['gpt', 'openai'],
  gemini:   ['gemini', 'google'],
  deepseek: ['deepseek'],
}

function modelFamily(modelId: string): string {
  const lower = modelId.toLowerCase()
  for (const [family, fragments] of Object.entries(FAMILY_FRAGMENTS)) {
    if (fragments.some(f => lower.includes(f))) return family
  }
  return 'defaults'
}

function getPinned(): string[] {
  try { return JSON.parse(localStorage.getItem(PINNED_KEY) ?? '[]') } catch { return [] }
}

interface DropdownModel {
  model_id: string
  name: string
  tier?: string
}

export function PromptEditor() {
  const [activeStage, setActiveStage]   = useState('outline')
  const [activeModel, setActiveModel]   = useState('__all__')
  const [mode, setMode]                 = useState<'simple' | 'advanced'>('simple')
  const [customText, setCustomText]     = useState('')
  const [defaultText, setDefaultText]   = useState('')
  const [hasOverride, setHasOverride]   = useState(false)
  const [loading, setLoading]           = useState(false)
  const [saving, setSaving]             = useState(false)
  const [dropdownModels, setDropdownModels] = useState<DropdownModel[]>([])

  // Load curated + pinned models for the model selector
  useEffect(() => {
    async function load() {
      try {
        const { models: modelsApi } = await import('@/lib/api')
        const [curated, all] = await Promise.all([modelsApi.curated(), modelsApi.all()])
        const curatedIds = new Set(curated.map((m: any) => m.model_id))
        const pinned = getPinned()
        const extras = all.filter((m: any) => pinned.includes(m.model_id) && !curatedIds.has(m.model_id))
        setDropdownModels([...curated, ...extras])
      } catch {}
    }
    load()
  }, [])

  // Compute stage key: if a specific model is selected, use model-family prefix
  const stageKey = activeModel === '__all__'
    ? activeStage
    : `${modelFamily(activeModel)}_${activeStage}`

  // Display family name
  const selectedModel = dropdownModels.find(m => m.model_id === activeModel)
  const familyName = activeModel === '__all__' ? null : modelFamily(activeModel)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadStage() }, [activeStage, activeModel])

  async function loadStage() {
    setLoading(true)
    try {
      const [def, cur] = await Promise.allSettled([
        promptsApi.getDefault(activeStage),
        promptsApi.get(stageKey),
      ])
      if (def.status === 'fulfilled') setDefaultText(def.value.system_prompt)
      if (cur.status === 'fulfilled') {
        setCustomText(cur.value.prompt_text)
        setHasOverride(true)
      } else {
        setCustomText('')
        setHasOverride(false)
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    if (!customText.trim()) return
    setSaving(true)
    try {
      await promptsApi.save(stageKey, customText)
      setHasOverride(true)
      toast.success('Saved ✓')
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleReset() {
    if (!confirm('Remove your custom prompt and go back to the default?')) return
    try {
      await promptsApi.delete(stageKey)
      setCustomText('')
      setHasOverride(false)
      toast.success('Reset to default')
    } catch (err: any) {
      toast.error(err.message)
    }
  }

  const stage = STAGES.find(s => s.key === activeStage)!

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-xl" style={{ color: 'var(--text)' }}>Prompt Editor</h2>
        <p className="text-sm mt-1" style={{ color: 'var(--text-sub)' }}>
          Customise how the AI writes at each stage. Changes only affect future generations.
        </p>
      </div>

      <div className="grid grid-cols-[200px_1fr] gap-6">
        {/* Left sidebar */}
        <div className="space-y-5">
          {/* Stage */}
          <div>
            <p className="text-xs font-medium uppercase tracking-wider mb-2"
              style={{ color: 'var(--text-muted)' }}>Stage</p>
            <div className="space-y-1">
              {STAGES.map(s => (
                <button key={s.key} onClick={() => setActiveStage(s.key)}
                  className="w-full text-left px-3 py-2 rounded-lg text-sm transition-all"
                  style={{
                    background: activeStage === s.key ? 'var(--accent-bg)' : 'transparent',
                    color: activeStage === s.key ? 'var(--accent)' : 'var(--text-sub)',
                    border: activeStage === s.key ? '1px solid var(--accent)' : '1px solid transparent',
                  }}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Model */}
          <div>
            <p className="text-xs font-medium uppercase tracking-wider mb-2"
              style={{ color: 'var(--text-muted)' }}>AI Model</p>
            <div className="space-y-1">
              {/* All models option */}
              <button onClick={() => setActiveModel('__all__')}
                className="w-full text-left px-3 py-2 rounded-lg text-xs transition-all"
                style={{
                  background: activeModel === '__all__' ? 'var(--bg-card)' : 'transparent',
                  color: activeModel === '__all__' ? 'var(--text)' : 'var(--text-muted)',
                  border: activeModel === '__all__' ? '1px solid var(--border)' : '1px solid transparent',
                  fontWeight: activeModel === '__all__' ? '500' : '400',
                }}>
                🌐 All models (default)
              </button>

              {/* Individual models from dropdown */}
              {dropdownModels.map(m => (
                <button key={m.model_id} onClick={() => setActiveModel(m.model_id)}
                  className="w-full text-left px-3 py-2 rounded-lg text-xs transition-all"
                  title={m.model_id}
                  style={{
                    background: activeModel === m.model_id ? 'var(--bg-card)' : 'transparent',
                    color: activeModel === m.model_id ? 'var(--text)' : 'var(--text-muted)',
                    border: activeModel === m.model_id ? '1px solid var(--border)' : '1px solid transparent',
                    fontWeight: activeModel === m.model_id ? '500' : '400',
                  }}>
                  {m.name.split(' ').slice(0, 3).join(' ')}
                </button>
              ))}

              {dropdownModels.length === 0 && (
                <p className="text-xs px-3 py-2" style={{ color: 'var(--text-muted)' }}>
                  Add models in the Models page to customise per-model prompts.
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Editor */}
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-sm font-medium" style={{ color: 'var(--text)' }}>
                {stage.label}
                {selectedModel && familyName && (
                  <span className="ml-2 badge badge-blue text-xs">{selectedModel.name}</span>
                )}
              </h3>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                {activeModel === '__all__'
                  ? 'Applies to all AI models unless you set a model-specific prompt below.'
                  : `Applies only when using ${selectedModel?.name ?? activeModel}.`}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {hasOverride && <span className="badge badge-amber text-xs">Custom</span>}
              <div className="flex rounded-lg overflow-hidden border" style={{ borderColor: 'var(--border)' }}>
                {(['simple', 'advanced'] as const).map(m => (
                  <button key={m} onClick={() => setMode(m)}
                    className="px-3 py-1 text-xs transition-all"
                    style={{
                      background: mode === m ? 'var(--accent)' : 'var(--bg-subtle)',
                      color: mode === m ? '#fff' : 'var(--text-sub)',
                    }}>
                    {m === 'simple' ? 'Simple' : 'Advanced'}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {loading ? (
            <div className="h-40 rounded-xl animate-pulse" style={{ background: 'var(--bg-subtle)' }} />
          ) : (
            <>
              {mode === 'simple' && (
                <div className="space-y-2">
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    Describe the writing style you want. A few sentences is plenty.
                  </p>
                  <textarea rows={5} value={customText} onChange={e => setCustomText(e.target.value)}
                    className="input font-sans text-sm resize-none"
                    placeholder="e.g. Write in a warm, encouraging tone. Use short paragraphs. Keep the language accessible to beginners." />
                </div>
              )}

              {mode === 'advanced' && (
                <div className="space-y-3">
                  <div className="rounded-xl overflow-hidden border" style={{ borderColor: 'var(--border)' }}>
                    <div className="flex items-center justify-between px-3 py-2 border-b text-xs"
                      style={{ borderColor: 'var(--border)', background: 'var(--bg-subtle)', color: 'var(--text-muted)' }}>
                      <span>Full system prompt (replaces the default entirely)</span>
                      {defaultText && (
                        <button onClick={() => setCustomText(defaultText)}
                          className="hover:underline" style={{ color: 'var(--accent)' }}>
                          Load default as starting point
                        </button>
                      )}
                    </div>
                    <textarea rows={12} value={customText} onChange={e => setCustomText(e.target.value)}
                      className="w-full px-3 py-3 text-sm font-mono outline-none resize-none"
                      style={{ background: 'var(--bg-card)', color: 'var(--text)' }}
                      placeholder="Enter your complete system prompt…" />
                  </div>
                  {defaultText && (
                    <details className="rounded-xl border overflow-hidden" style={{ borderColor: 'var(--border)' }}>
                      <summary className="px-3 py-2 text-xs cursor-pointer"
                        style={{ background: 'var(--bg-subtle)', color: 'var(--text-muted)' }}>
                        View current default
                      </summary>
                      <pre className="px-3 py-3 text-xs font-mono whitespace-pre-wrap"
                        style={{ color: 'var(--text-sub)', background: 'var(--bg-card)' }}>
                        {defaultText}
                      </pre>
                    </details>
                  )}
                </div>
              )}

              <div className="flex items-center gap-3 pt-1">
                <button onClick={handleSave} disabled={saving || !customText.trim()} className="btn-primary">
                  {saving ? 'Saving…' : 'Save'}
                </button>
                {hasOverride && (
                  <button onClick={handleReset} className="btn-ghost text-sm"
                    style={{ color: 'var(--red)' }}>
                    Reset to default
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
