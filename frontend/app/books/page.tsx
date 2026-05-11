'use client'

import { useState } from 'react'
import useSWR from 'swr'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { books as booksApi } from '@/lib/api'
import { ModelDropdown } from '@/components/ModelDropdown'
import { CostEstimate } from '@/components/CostEstimate'
import type { Book } from '@/lib/types'

const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  INPUT_RECEIVED:      { label: 'Not started',       cls: 'badge-subtle' },
  OUTLINE_GENERATING:  { label: 'Generating outline', cls: 'badge-amber' },
  OUTLINE_REVIEW:      { label: 'Outline ready',      cls: 'badge-amber' },
  CHAPTERS_GENERATING: { label: 'Writing chapters',   cls: 'badge-blue' },
  CHAPTER_REVIEW:      { label: 'Review chapters',    cls: 'badge-blue' },
  FINAL_REVIEW:        { label: 'Final review',       cls: 'badge-blue' },
  COMPILING:           { label: 'Compiling',          cls: 'badge-amber' },
  COMPLETE:            { label: 'Complete',           cls: 'badge-green' },
  FAILED:              { label: 'Failed',             cls: 'badge-red' },
}

export default function BooksPage() {
  const { data: bookList, mutate } = useSWR<Book[]>('books', booksApi.list)
  const [showCreate, setShowCreate] = useState(false)
  const [title, setTitle]   = useState('')
  const [notes, setNotes]   = useState('')
  const [model, setModel]   = useState('anthropic/claude-3.5-sonnet')
  const [chapters, setChapters] = useState(10)
  const [creating, setCreating] = useState(false)

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreating(true)
    try {
      await booksApi.create(title, notes, model, chapters)
      toast.success('Book created')
      setShowCreate(false); setTitle(''); setNotes('')
      mutate()
    } catch (err: any) { toast.error(err.message) }
    finally { setCreating(false) }
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this book and all its content?')) return
    try { await booksApi.delete(id); mutate() }
    catch (err: any) { toast.error(err.message) }
  }

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl" style={{ color: 'var(--text)' }}>My Books</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-sub)' }}>
            {bookList?.length ?? 0} book{bookList?.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button onClick={() => setShowCreate(s => !s)} className="btn-primary">
          + New Book
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <form onSubmit={handleCreate} className="card space-y-5 animate-slide-up">
          <h2 className="font-display text-xl" style={{ color: 'var(--text)' }}>Create a new book</h2>

          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-sub)' }}>Title</label>
              <input required value={title} onChange={e => setTitle(e.target.value)}
                placeholder="The Art of Deep Work" className="input" />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-sub)' }}>
                Outline guidance
              </label>
              <textarea required rows={3} value={notes} onChange={e => setNotes(e.target.value)}
                placeholder="What should this book cover? Who is the audience? What's the core argument?"
                className="input resize-none" />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-sub)' }}>Model</label>
              <ModelDropdown value={model} onChange={setModel} showAll />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-sub)' }}>
                Expected chapters
              </label>
              <input type="number" min={1} max={40} value={chapters}
                onChange={e => setChapters(Number(e.target.value))} className="input" />
            </div>
            <div className="col-span-2">
              <CostEstimate modelId={model} chapters={chapters} />
            </div>
          </div>

          <div className="flex gap-3 pt-1">
            <button type="submit" disabled={creating} className="btn-primary">
              {creating ? 'Creating…' : 'Create book'}
            </button>
            <button type="button" onClick={() => setShowCreate(false)} className="btn-ghost">
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Book list */}
      {!bookList && (
        <div className="space-y-3">
          {[1,2,3].map(i => (
            <div key={i} className="card h-16 animate-pulse" style={{ background: 'var(--bg-subtle)' }} />
          ))}
        </div>
      )}

      {bookList?.length === 0 && !showCreate && (
        <div className="card text-center py-16">
          <p className="text-4xl mb-3">📖</p>
          <p className="font-display text-xl" style={{ color: 'var(--text)' }}>No books yet</p>
          <p className="text-sm mt-1" style={{ color: 'var(--text-sub)' }}>Create one to get started.</p>
        </div>
      )}

      <div className="space-y-2">
        {bookList?.map(book => {
          const cfg = STATUS_CONFIG[book.status] ?? { label: book.status, cls: 'badge-subtle' }
          return (
            <div key={book.id}
              className="card flex items-center justify-between gap-4 py-3.5 px-5 transition-all hover:border-[var(--accent)]"
            >
              <Link href={`/books/${book.id}`} className="flex-1 min-w-0 flex items-center gap-4">
                <div className="min-w-0">
                  <p className="font-medium truncate" style={{ color: 'var(--text)' }}>{book.title}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`badge ${cfg.cls}`}>{cfg.label}</span>
                    {book.selected_model && (
                      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        {book.selected_model.split('/').pop()}
                      </span>
                    )}
                  </div>
                </div>
              </Link>
              <button onClick={() => handleDelete(book.id)}
                className="btn-ghost text-lg shrink-0 opacity-40 hover:opacity-100 hover:text-red-400 transition-opacity">
                ×
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
