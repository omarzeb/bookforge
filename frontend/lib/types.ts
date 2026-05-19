// API response types — mirroring backend schemas

export type BookStatus =
  | 'INPUT_RECEIVED'
  | 'OUTLINE_GENERATING'
  | 'OUTLINE_REVIEW'
  | 'CHAPTERS_GENERATING'
  | 'CHAPTER_REVIEW'
  | 'FINAL_REVIEW'
  | 'COMPILING'
  | 'COMPLETE'
  | 'FAILED'

export type JobStatus = 'QUEUED' | 'RUNNING' | 'DONE' | 'FAILED'
export type OutputFormat = 'docx' | 'txt'

export interface Book {
  id: string
  title: string
  status: BookStatus
  selected_model: string | null
  outline_raw: string | null
  outline_approved: boolean
  compiled_path: string | null
  output_format: OutputFormat | null
  created_at: string
  updated_at: string
}

export interface Chapter {
  id: string
  book_id: string
  number: number
  title: string
  content: string | null
  summary: string | null
  approved: boolean
  revision_notes: string | null
  created_at: string
  updated_at: string
}

export interface Job {
  id: string
  book_id: string
  task_name: string
  status: JobStatus
  streamed_output: string | null
  error_message: string | null
}

export interface AdvanceResponse {
  book: Book
  job_id: string | null
  message: string
}

export interface CuratedModel {
  model_id: string
  name: string
  tier: 'Recommended' | 'Budget' | 'Premium' | 'Other'
  context_k: number
  notes: string
  prompt_price_per_1k: number | null
  completion_price_per_1k: number | null
}

export interface CostEstimate {
  model_id: string
  chapters: number
  low_usd: number | null
  high_usd: number | null
  note: string
}

export interface PromptOverride {
  stage: string
  prompt_text: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}
