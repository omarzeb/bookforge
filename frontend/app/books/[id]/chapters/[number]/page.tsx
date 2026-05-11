'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import useSWR from 'swr'
import toast from 'react-hot-toast'
import { chapters as chaptersApi } from '@/lib/api'
import type { Chapter } from '@/lib/types'

function wordCount(text: string | null) {
  if (!text) return 0
  return text.trim().split(/\s+/).length
}

export default function ChapterPage() {
  const { id, number } = useParams<{ id: string; number: string }>()
  const num = parseInt(number)
  const { data: chapter, mutate } = useSWR<Chapter>(
    `chapter-${id}-${num}`,
    () => chaptersApi.get(id, num)
  )

  const [showRevise, setShowRevise] = useState(false)
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (!chapter) return <p className="text-gray-400">Loading…</p>

  async function handleApprove() {
    try {
      await chaptersApi.approve(id, num)
      toast.success('Chapter approved')
      mutate()
    } catch (err: any) {
      toast.error(err.message)
    }
  }

  async function handleRevise() {
    if (!notes.trim()) return
    setSubmitting(true)
    try {
      await chaptersApi.revise(id, num, notes)
      toast.success('Revision notes saved — advance the book to regenerate')
      setShowRevise(false)
      setNotes('')
      mutate()
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <Link href={`/books/${id}`} className="text-sm text-gray-400 hover:text-gray-600">
          ← Book
        </Link>
        <h1 className="text-xl font-bold text-gray-900 mt-1">
          Chapter {chapter.number}: {chapter.title}
        </h1>
        <div className="flex items-center gap-3 mt-1">
          {chapter.approved && (
            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">✓ Approved</span>
          )}
          {chapter.revision_notes && (
            <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">Revision pending</span>
          )}
          {chapter.content && (
            <span className="text-xs text-gray-400">{wordCount(chapter.content).toLocaleString()} words</span>
          )}
        </div>
      </div>

      {!chapter.content && (
        <div className="bg-gray-50 rounded-xl p-8 text-center text-gray-400">
          <p>This chapter hasn't been generated yet.</p>
          <p className="text-sm mt-1">Go back to the book and click Advance.</p>
        </div>
      )}

      {chapter.content && (
        <>
          <div className="bg-white border border-gray-200 rounded-xl p-6">
            <div className="prose prose-sm max-w-none text-gray-700 leading-relaxed whitespace-pre-wrap">
              {chapter.content}
            </div>
          </div>

          {chapter.summary && (
            <details className="bg-gray-50 border border-gray-200 rounded-xl p-4">
              <summary className="text-sm font-medium text-gray-600 cursor-pointer">Summary (for context chaining)</summary>
              <p className="text-sm text-gray-500 mt-2">{chapter.summary}</p>
            </details>
          )}

          {!chapter.approved && (
            <div className="flex gap-3">
              <button
                onClick={handleApprove}
                className="bg-green-600 hover:bg-green-700 text-white text-sm font-medium px-4 py-2 rounded-lg"
              >
                Approve chapter
              </button>
              <button
                onClick={() => setShowRevise(s => !s)}
                className="border border-gray-300 hover:border-gray-400 text-sm font-medium px-4 py-2 rounded-lg text-gray-700"
              >
                Request revision
              </button>
            </div>
          )}

          {showRevise && (
            <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
              <label className="block text-sm font-medium text-gray-700">Revision notes</label>
              <textarea
                rows={4}
                value={notes}
                onChange={e => setNotes(e.target.value)}
                placeholder="What should be changed or improved? Be specific."
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <div className="flex gap-3">
                <button
                  onClick={handleRevise}
                  disabled={submitting || !notes.trim()}
                  className="bg-brand-600 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50"
                >
                  {submitting ? 'Saving…' : 'Save revision notes'}
                </button>
                <button onClick={() => setShowRevise(false)} className="text-sm text-gray-500 px-4 py-2">
                  Cancel
                </button>
              </div>
            </div>
          )}

          {chapter.revision_notes && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <p className="text-sm font-medium text-amber-800">Pending revision notes:</p>
              <p className="text-sm text-amber-700 mt-1">{chapter.revision_notes}</p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
