'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import useSWR from 'swr'
import toast from 'react-hot-toast'
import { books as booksApi } from '@/lib/api'
import { getToken } from '@/lib/auth'
import { JobProgress } from '@/components/JobProgress'
import type { Book } from '@/lib/types'

export default function CompilePage() {
  const { id } = useParams<{ id: string }>()
  const { data: book, mutate } = useSWR<Book>(`book-${id}`, () => booksApi.get(id))
  const [format, setFormat] = useState<'docx' | 'txt'>('docx')
  const [compiling, setCompiling] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)

  if (!book) return <p className="text-gray-400">Loading…</p>

  async function handleCompile() {
    setCompiling(true)
    try {
      const resp = await booksApi.compile(id, format)
      if (resp.job_id) setJobId(resp.job_id)
      toast.success('Compilation started')
      mutate()
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setCompiling(false)
    }
  }

  async function handleDownload() {
    const token = getToken()
    const url = booksApi.downloadUrl(id)
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) { toast.error('Download failed'); return }
    const blob = await res.blob()
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${book.title}.${book.output_format ?? format}`
    a.click()
  }

  return (
    <div className="space-y-6 max-w-lg">
      <div>
        <Link href={`/books/${id}`} className="text-sm text-gray-400 hover:text-gray-600">← Book</Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-1">Compile & Download</h1>
        <p className="text-sm text-gray-500 mt-1">{book.title}</p>
      </div>

      {book.status !== 'COMPLETE' && !jobId && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Output format</label>
            <div className="flex gap-3">
              {(['docx', 'txt'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setFormat(f)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium border transition ${
                    format === f
                      ? 'bg-brand-600 text-white border-brand-600'
                      : 'border-gray-300 text-gray-700 hover:border-gray-400'
                  }`}
                >
                  .{f}
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={handleCompile}
            disabled={compiling}
            className="bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-6 py-2 rounded-lg disabled:opacity-50"
          >
            {compiling ? 'Starting…' : 'Compile book'}
          </button>
        </div>
      )}

      {jobId && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h3 className="text-sm font-medium text-gray-700 mb-4">Compilation progress</h3>
          <JobProgress
            jobId={jobId}
            onDone={() => { mutate(); setJobId(null) }}
            onFailed={(err) => toast.error(err)}
          />
        </div>
      )}

      {book.status === 'COMPLETE' && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl">✅</span>
            <div>
              <p className="font-medium text-green-900">Your book is ready</p>
              <p className="text-sm text-green-700">Compiled as .{book.output_format ?? 'docx'}</p>
            </div>
          </div>
          <button
            onClick={handleDownload}
            className="bg-green-600 hover:bg-green-700 text-white text-sm font-medium px-6 py-2 rounded-lg"
          >
            Download {book.title}.{book.output_format ?? 'docx'}
          </button>
        </div>
      )}
    </div>
  )
}
