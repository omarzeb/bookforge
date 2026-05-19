import { getToken } from './auth'
import type {
  AdvanceResponse, Book, Chapter, CostEstimate,
  CuratedModel, Job, PromptOverride, TokenResponse,
} from './types'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080'

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken()
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body.detail ?? res.statusText)
  }

  if (res.status === 204) return undefined as T
  return res.json()
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export const auth = {
  register: (email: string, password: string) =>
    request<TokenResponse>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  login: (email: string, password: string) => {
    const form = new URLSearchParams({ username: email, password })
    return request<TokenResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: form.toString(),
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
  },
}

// ── Books ─────────────────────────────────────────────────────────────────────
export const books = {
  list: () => request<Book[]>('/api/v1/books'),

  get: (id: string) => request<Book>(`/api/v1/books/${id}`),

  create: (title: string, notes_before: string, selected_model?: string, chapter_count: number = 10) =>
    request<Book>('/api/v1/books', {
      method: 'POST',
      body: JSON.stringify({ title, notes_before, selected_model, chapter_count }),
    }),

  delete: (id: string) =>
    request<void>(`/api/v1/books/${id}`, { method: 'DELETE' }),

  advance: (id: string, notes_before = '') =>
    request<AdvanceResponse>(`/api/v1/books/${id}/advance`, {
      method: 'POST',
      body: JSON.stringify({ notes_before }),
    }),

  approveOutline: (id: string) =>
    request<Book>(`/api/v1/books/${id}/outline/approve`, { method: 'POST' }),

  reviseOutline: (id: string, revision_notes: string) =>
    request<AdvanceResponse>(`/api/v1/books/${id}/outline/revise`, {
      method: 'POST',
      body: JSON.stringify({ revision_notes }),
    }),

  approveFinalReview: (id: string) =>
    request<AdvanceResponse>(`/api/v1/books/${id}/final-review/approve`, { method: 'POST' }),

  compile: (id: string, output_format: 'docx' | 'txt' = 'docx') =>
    request<AdvanceResponse>(`/api/v1/books/${id}/compile?output_format=${output_format}`, {
      method: 'POST',
    }),

  downloadUrl: (id: string) => `${BASE}/api/v1/books/${id}/download`,
}

// ── Chapters ──────────────────────────────────────────────────────────────────
export const chapters = {
  list: (bookId: string) => request<Chapter[]>(`/api/v1/books/${bookId}/chapters`),

  get: (bookId: string, number: number) =>
    request<Chapter>(`/api/v1/books/${bookId}/chapters/${number}`),

  approve: (bookId: string, number: number) =>
    request<Chapter>(`/api/v1/books/${bookId}/chapters/${number}/approve`, { method: 'POST' }),

  revise: (bookId: string, number: number, notes: string) =>
    request<Chapter>(`/api/v1/books/${bookId}/chapters/${number}/revise`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    }),
}

// ── Jobs ──────────────────────────────────────────────────────────────────────
export const jobs = {
  get: (id: string) => request<Job>(`/api/v1/jobs/${id}`),
  streamUrl: (id: string) => `${BASE}/api/v1/jobs/${id}/stream`,
}

// ── Models ────────────────────────────────────────────────────────────────────
export const models = {
  curated: () => request<CuratedModel[]>('/api/v1/models/curated'),

  estimate: (model_id: string, chapters: number) =>
    request<CostEstimate>(
      `/api/v1/models/estimate?model_id=${encodeURIComponent(model_id)}&chapters=${chapters}`
    ),

  all: () => request<any[]>('/api/v1/models'),

  sync: async () => {
    const token = getToken()
    const res = await fetch(`${BASE}/api/v1/models/sync`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token ?? ''}` },
    })
    if (!res.ok) throw new ApiError(res.status, 'Sync failed')
    return res.json()
  },
}

// ── Prompts ───────────────────────────────────────────────────────────────────
export const prompts = {
  list: () => request<PromptOverride[]>('/api/v1/prompts'),

  get: (stage: string) => request<PromptOverride>(`/api/v1/prompts/${stage}`),

  getDefault: (stage: string) =>
    request<{ stage: string; system_prompt: string }>(`/api/v1/prompts/defaults/${stage}`),

  save: (stage: string, prompt_text: string) =>
    request<PromptOverride>(`/api/v1/prompts/${stage}`, {
      method: 'PUT',
      body: JSON.stringify({ prompt_text }),
    }),

  delete: (stage: string) =>
    request<void>(`/api/v1/prompts/${stage}`, { method: 'DELETE' }),
}

export { ApiError }
