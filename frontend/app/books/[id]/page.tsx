'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import useSWR from 'swr'
import toast from 'react-hot-toast'
import { books as booksApi, chapters as chaptersApi } from '@/lib/api'
import { JobProgress } from '@/components/JobProgress'
import type { Book, Chapter } from '@/lib/types'

const STATUS_ACTIONS: Record<string, { label: string; desc: string }> = {
  INPUT_RECEIVED:      { label: 'Generate outline',      desc: 'Ask the AI to create a chapter structure for your book' },
  OUTLINE_REVIEW:      { label: 'Approve & write chapters', desc: 'Happy with the outline? Start writing the chapters' },
  CHAPTERS_GENERATING: { label: 'Write next chapter',    desc: 'Generate the next chapter in your book' },
  CHAPTER_REVIEW:      { label: 'Write remaining chapters', desc: 'Continue writing chapters' },
  FINAL_REVIEW:        { label: 'Compile my book',       desc: 'All chapters approved — put the book together' },
}


// Parse outline text into a map of chapter number → description
function parseOutlineDescriptions(outlineRaw: string | null): Record<number, string> {
  if (!outlineRaw) return {}
  const map: Record<number, string> = {}
  for (const line of outlineRaw.split('\n')) {
    const match = line.match(/^Chapter\s+(\d+)[:.)-]\s*([^-]+)(?:\s*[-–—]\s*(.+))?/i)
    if (match) {
      const num = parseInt(match[1])
      const description = match[3]?.trim() ?? ''
      map[num] = description
    }
  }
  return map
}

export default function BookDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: book, mutate: mutateBook } = useSWR<Book>(`book-${id}`, () => booksApi.get(id), { refreshInterval: 3000 })
  const { data: chapterList, mutate: mutateChapters } = useSWR<Chapter[]>(
    book?.status !== 'INPUT_RECEIVED' ? `chapters-${id}` : null,
    () => chaptersApi.list(id),
    { refreshInterval: 5000 }
  )

  const [activeJobId, setActiveJobId]         = useState<string | null>(null)
  const [showReviseOutline, setShowReviseOutline] = useState(false)
  const [reviseNotes, setReviseNotes]         = useState('')
  const [reviseChapter, setReviseChapter]     = useState<number | null>(null)
  const [chapterNotes, setChapterNotes]       = useState('')
  const [submitting, setSubmitting]           = useState(false)
  const [advancing, setAdvancing]             = useState(false)

  if (!book) return (
    <div className="space-y-4 animate-pulse">
      <div className="h-8 rounded-lg w-64" style={{ background: 'var(--bg-subtle)' }} />
      <div className="h-48 rounded-xl" style={{ background: 'var(--bg-subtle)' }} />
    </div>
  )

  async function advance() {
    setAdvancing(true)
    try {
      const resp = await booksApi.advance(id)
      if (resp.job_id) setActiveJobId(resp.job_id)
      if (resp.message) toast.success(resp.message)
      mutateBook()
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setAdvancing(false)
    }
  }

  async function approveOutline() {
    setSubmitting(true)
    try {
      await booksApi.approveOutline(id)
      toast.success('Outline approved ✓')
      mutateBook(); mutateChapters()
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  async function submitReviseOutline() {
    if (!reviseNotes.trim()) return
    setSubmitting(true)
    try {
      const resp = await booksApi.reviseOutline(id, reviseNotes)
      if (resp.job_id) setActiveJobId(resp.job_id)
      setShowReviseOutline(false)
      setReviseNotes('')
      toast.success('Revision queued')
      mutateBook()
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  async function submitReviseChapter(num: number) {
    if (!chapterNotes.trim()) return
    setSubmitting(true)
    try {
      await chaptersApi.revise(id, num, chapterNotes)
      toast.success('Revision notes saved — generate next chapter to apply them')
      setReviseChapter(null)
      setChapterNotes('')
      mutateChapters()
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  async function approveChapter(num: number) {
    try {
      await chaptersApi.approve(id, num)
      toast.success('Chapter approved ✓')
      mutateChapters()
    } catch (err: any) {
      toast.error(err.message)
    }
  }

  const actionInfo = STATUS_ACTIONS[book.status]
  const allApproved = chapterList?.length && chapterList.every(c => c.approved)
  const showOutlineActions = book.status === 'OUTLINE_REVIEW'

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link href="/books" className="text-xs hover:underline mb-1 block"
            style={{ color: 'var(--text-muted)' }}>← My Books</Link>
          <h1 className="font-display text-3xl" style={{ color: 'var(--text)' }}>{book.title}</h1>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
              {book.status.replace(/_/g, ' ').toLowerCase()}
            </span>
            {book.selected_model && (
              <span className="badge badge-subtle text-xs">{book.selected_model.split('/').pop()}</span>
            )}
            {book.status === 'COMPLETE' && (
              <span className="badge badge-green">✓ Complete</span>
            )}
          </div>
        </div>

        {/* Primary action */}
        {actionInfo && !activeJobId && (
          <div className="text-right shrink-0">
            <button onClick={advance} disabled={advancing}
              className="btn-primary px-5 py-2.5">
              {advancing ? 'Starting…' : actionInfo.label}
            </button>
            <p className="text-xs mt-1.5" style={{ color: 'var(--text-muted)' }}>{actionInfo.desc}</p>
          </div>
        )}

        {book.status === 'COMPLETE' && (
          <Link href={`/books/${id}/compile`} className="btn-primary px-5 py-2.5">
            Download book →
          </Link>
        )}
      </div>

      {/* Job progress */}
      {activeJobId && (
        <div className="card">
          <p className="text-sm font-medium mb-4" style={{ color: 'var(--text)' }}>Working…</p>
          <JobProgress
            jobId={activeJobId}
            showOutput
            onDone={() => {
              mutateBook(); mutateChapters(); setActiveJobId(null)
              toast.success('Done!')
            }}
            onFailed={(err) => { toast.error(err); setActiveJobId(null) }}
          />
        </div>
      )}

      {/* Outline — full view before approval, collapsed summary after */}
      {book.outline_raw && !book.outline_approved && (
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-xl" style={{ color: 'var(--text)' }}>Outline</h2>
            <span className="badge badge-amber">Awaiting your review</span>
          </div>

          <pre className="text-sm leading-relaxed whitespace-pre-wrap font-sans"
            style={{ color: 'var(--text-sub)' }}>
            {book.outline_raw}
          </pre>

          {showOutlineActions && !showReviseOutline && (
            <div className="flex gap-3 pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
              <button onClick={approveOutline} disabled={submitting} className="btn-primary">
                {submitting ? 'Approving…' : '✓ Approve this outline'}
              </button>
              <button onClick={() => setShowReviseOutline(true)} className="btn-secondary">
                Request changes
              </button>
            </div>
          )}

          {showOutlineActions && showReviseOutline && (
            <div className="space-y-3 pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
              <label className="block text-sm font-medium" style={{ color: 'var(--text)' }}>
                What would you like changed?
              </label>
              <textarea
                autoFocus
                rows={3}
                value={reviseNotes}
                onChange={e => setReviseNotes(e.target.value)}
                placeholder="e.g. Add more chapters on implementation, merge chapters 4 and 5, focus more on practical examples…"
                className="input resize-none text-sm"
                style={{ color: 'var(--text)' }}
              />
              <div className="flex gap-3">
                <button onClick={submitReviseOutline}
                  disabled={submitting || !reviseNotes.trim()} className="btn-primary">
                  {submitting ? 'Queuing…' : 'Submit revision request'}
                </button>
                <button onClick={() => { setShowReviseOutline(false); setReviseNotes('') }}
                  className="btn-ghost">
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* After approval: collapsed outline summary + chapters with descriptions */}
      {book.outline_approved && chapterList && chapterList.length > 0 && (
        <>
          {/* Collapsible full outline */}
          {book.outline_raw && (
            <details className="card" style={{ cursor: 'pointer' }}>
              <summary
                className="flex items-center justify-between list-none"
                style={{ cursor: 'pointer' }}
              >
                <span className="font-display text-lg" style={{ color: 'var(--text)' }}>
                  📋 Full outline
                </span>
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  Click to expand
                </span>
              </summary>
              <pre className="text-sm leading-relaxed whitespace-pre-wrap font-sans mt-4 pt-4 border-t"
                style={{ color: 'var(--text-sub)', borderColor: 'var(--border)' }}>
                {book.outline_raw}
              </pre>
            </details>
          )}
        </>
      )}

      {/* Chapters — show as list once outline approved */}
      {chapterList && chapterList.length > 0 && (() => {
        const descriptions = parseOutlineDescriptions(book.outline_raw)
        return (
        <div className="card space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-xl" style={{ color: 'var(--text)' }}>Chapters</h2>
            <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
              {chapterList.filter(c => c.approved).length} / {chapterList.length} approved
            </span>
          </div>

          <div className="space-y-2">
            {chapterList.map(ch => (
              <div key={ch.id}>
                {/* Chapter row */}
                <div className="flex items-center gap-4 px-4 py-3 rounded-xl transition-all"
                  style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>

                  <span className="text-xs w-5 text-right shrink-0"
                    style={{ color: 'var(--text-muted)' }}>{ch.number}</span>

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium" style={{ color: 'var(--text)' }}>
                      {ch.title}
                    </p>
                    {descriptions[ch.number] && !ch.content && (
                      <p className="text-xs mt-0.5 leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                        {descriptions[ch.number]}
                      </p>
                    )}
                    {ch.content && (
                      <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                        {ch.content.trim().split(/\s+/).length.toLocaleString()} words written
                      </p>
                    )}
                  </div>

                  {/* Status badge */}
                  <div className="shrink-0 flex items-center gap-2">
                    {ch.approved && <span className="badge badge-green text-xs">✓ Approved</span>}
                    {ch.content && !ch.approved && !ch.revision_notes && (
                      <span className="badge badge-blue text-xs">Ready to review</span>
                    )}
                    {ch.revision_notes && <span className="badge badge-amber text-xs">Revision pending</span>}
                    {!ch.content && <span className="badge badge-subtle text-xs">Not written yet</span>}
                  </div>

                  {/* Actions — only if content exists */}
                  {ch.content && !ch.approved && (
                    <div className="flex items-center gap-2 shrink-0">
                      <Link href={`/books/${id}/chapters/${ch.number}`}
                        className="btn-ghost text-xs py-1 px-2">
                        Read →
                      </Link>
                      <button onClick={() => approveChapter(ch.number)}
                        className="text-xs px-2.5 py-1 rounded-lg font-medium transition-all"
                        style={{ background: 'var(--green-bg)', color: 'var(--green)', border: '1px solid var(--green)' }}>
                        Approve
                      </button>
                      <button
                        onClick={() => setReviseChapter(reviseChapter === ch.number ? null : ch.number)}
                        className="text-xs px-2.5 py-1 rounded-lg font-medium transition-all"
                        style={{ background: 'var(--bg-card)', color: 'var(--text-sub)', border: '1px solid var(--border)' }}>
                        Revise
                      </button>
                    </div>
                  )}
                  {ch.approved && (
                    <Link href={`/books/${id}/chapters/${ch.number}`}
                      className="btn-ghost text-xs py-1 px-2 shrink-0">
                      Read →
                    </Link>
                  )}
                </div>

                {/* Inline revise form */}
                {reviseChapter === ch.number && (
                  <div className="mt-1 ml-9 space-y-2 p-3 rounded-xl"
                    style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                    <label className="block text-xs font-medium" style={{ color: 'var(--text)' }}>
                      What should be changed in this chapter?
                    </label>
                    <textarea
                      autoFocus
                      rows={3}
                      value={chapterNotes}
                      onChange={e => setChapterNotes(e.target.value)}
                      placeholder="e.g. Make it more engaging, add more examples, shorten the introduction…"
                      className="input resize-none text-sm w-full"
                      style={{ color: 'var(--text)' }}
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => submitReviseChapter(ch.number)}
                        disabled={submitting || !chapterNotes.trim()}
                        className="btn-primary text-xs py-1.5 px-3">
                        {submitting ? 'Saving…' : 'Submit revision notes'}
                      </button>
                      <button
                        onClick={() => { setReviseChapter(null); setChapterNotes('') }}
                        className="btn-ghost text-xs">
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {allApproved && book.status !== 'COMPLETE' && (
            <div className="pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
              <button onClick={advance} disabled={advancing} className="btn-primary w-full justify-center py-2.5">
                {advancing ? 'Starting…' : '📖 Compile my book'}
              </button>
            </div>
          )}
        </div>
        )
      })()}
    </div>
  )
}
