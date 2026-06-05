import type { Article, ArticleStatus, Source, Summary } from './types'

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

export async function fetchArticles(status?: ArticleStatus | 'all', category?: string): Promise<Article[]> {
  const params = new URLSearchParams()
  if (status && status !== 'all') params.set('status', status)
  if (category && category !== 'all') params.set('category', category)
  const suffix = params.toString() ? `?${params.toString()}` : ''
  const data = await requestJson<{ items: Article[] }>(`/api/articles${suffix}`)
  return data.items
}

export async function fetchSources(): Promise<Source[]> {
  const data = await requestJson<{ items: Source[] }>('/api/sources')
  return data.items
}

export async function fetchSummary(): Promise<Summary> {
  return requestJson<Summary>('/api/summary')
}

export async function ingestNow(): Promise<{ inserted: number; results: Record<string, number> }> {
  return requestJson('/api/ingest', { method: 'POST' })
}

export async function updateArticleStatus(id: number, status: ArticleStatus): Promise<Article> {
  return requestJson<Article>(`/api/articles/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
}
