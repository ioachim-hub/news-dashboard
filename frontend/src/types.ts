export type ArticleStatus = 'new' | 'read' | 'saved' | 'skipped' | 'archived'

export interface Article {
  id: number
  url: string
  title: string
  source_name: string
  category: string
  kind: string
  published_at?: string | null
  discovered_at: string
  status: ArticleStatus
  importance_score: number
  summary: string
  reason: string
  tags: string
}

export interface Source {
  slug: string
  name: string
  url: string
  category: string
  kind: string
  priority: number
  enabled: number
  last_checked_at?: string | null
}

export interface Summary {
  byStatus: Record<string, number>
  byCategory: Record<string, number>
}
