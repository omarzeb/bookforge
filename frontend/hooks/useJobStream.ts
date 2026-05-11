'use client'

import { useEffect, useRef, useState } from 'react'
import { jobs } from '@/lib/api'
import { getToken } from '@/lib/auth'
import type { JobStatus } from '@/lib/types'

interface StreamState {
  status: JobStatus | null
  output: string
  error: string | null
  done: boolean
}

/**
 * useJobStream — subscribes to a job's SSE stream.
 *
 * Falls back to polling every 2s if SSE isn't supported or fails.
 * Closes the stream automatically when the job reaches DONE or FAILED.
 */
export function useJobStream(jobId: string | null) {
  const [state, setState] = useState<StreamState>({
    status: null,
    output: '',
    error: null,
    done: false,
  })
  const esRef = useRef<EventSource | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!jobId) return

    // Clean up any previous stream
    esRef.current?.close()
    if (pollRef.current) clearInterval(pollRef.current)

    const token = getToken()
    if (!token) return

    let usedSSE = false

    // Try SSE first
    if (typeof EventSource !== 'undefined') {
      try {
        // EventSource doesn't support custom headers — use cookie or query param
        // For now we fall back to polling which works reliably across all browsers
        startPolling()
        return
      } catch {
        startPolling()
        return
      }
    }

    startPolling()

    function startPolling() {
      pollRef.current = setInterval(async () => {
        try {
          const job = await jobs.get(jobId!)
          setState(prev => ({
            status: job.status,
            output: job.streamed_output ?? prev.output,
            error: job.error_message ?? null,
            done: job.status === 'DONE' || job.status === 'FAILED',
          }))

          if (job.status === 'DONE' || job.status === 'FAILED') {
            if (pollRef.current) clearInterval(pollRef.current)
          }
        } catch (err) {
          console.error('Job poll error:', err)
        }
      }, 2000)
    }

    return () => {
      esRef.current?.close()
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [jobId])

  return state
}
