import { useEffect, useMemo, useState } from 'react'
import './styles.css'
import { fetchArticles, fetchSources, fetchSummary, ingestNow, searchArticles, updateArticleStatus } from './api'
import type { Article, ArticleStatus, Source, Summary } from './types'

type ActiveTab = 'inbox' | 'saved' | 'read' | 'skipped' | 'archived' | 'sources'

const TAB_STATUS: Record<Exclude<ActiveTab, 'sources'>, ArticleStatus> = {
  inbox: 'new',
  saved: 'saved',
  read: 'read',
  skipped: 'skipped',
  archived: 'archived',
}

const TABS: { id: ActiveTab; label: string }[] = [
  { id: 'inbox',    label: 'Inbox'    },
  { id: 'saved',    label: 'Saved'    },
  { id: 'read',     label: 'Read'     },
  { id: 'skipped',  label: 'Skipped'  },
  { id: 'archived', label: 'Archived' },
  { id: 'sources',  label: 'Sources'  },
]

const CATEGORIES = [
  'all', 'python', 'ai-llm', 'agents', 'cloud-infra', 'engineering', 'trending', 'repositories',
]

const STATUS_NEXT: Record<ArticleStatus, ArticleStatus[]> = {
  new:      ['read', 'saved', 'skipped'],
  saved:    ['read', 'skipped', 'archived'],
  read:     ['saved', 'archived'],
  skipped:  ['read', 'archived'],
  archived: ['read'],
}

const ACTION_LABELS: Record<ArticleStatus, string> = {
  new:      '↩ Restore',
  read:     '✓ Read',
  saved:    '♡ Save',
  skipped:  '✕ Skip',
  archived: '⊠ Archive',
}

function relativeTime(value?: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const ms = Date.now() - date.getTime()
  const h = Math.floor(ms / 3600000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  if (d < 7) return `${d}d ago`
  if (d < 30) return `${Math.floor(d / 7)}w ago`
  return date.toLocaleDateString()
}

function parseTags(tags: string): string[] {
  return tags.split(',').map((t) => t.trim()).filter(Boolean)
}

interface ArticleCardProps {
  article: Article
  onStatus: (id: number, status: ArticleStatus) => Promise<void>
}

function ArticleCard({ article, onStatus }: ArticleCardProps) {
  const [pending, setPending] = useState<ArticleStatus | null>(null)
  const tags = parseTags(article.tags)
  const date = article.published_at ?? article.discovered_at
  const actions = STATUS_NEXT[article.status] ?? ['read', 'saved', 'skipped']

  async function handle(status: ArticleStatus) {
    setPending(status)
    try {
      await onStatus(article.id, status)
    } finally {
      setPending(null)
    }
  }

  const showReason = article.reason
    && article.reason !== article.summary
    && !article.reason.startsWith('Tracked under')

  return (
    <article className="article-card">
      <div className="card-header">
        <span className={`badge cat-${article.category}`}>
          {article.category.replace(/-/g, '​-')}
        </span>
        <span className={`badge status-${article.status}`}>{article.status}</span>
        <span className="card-date">{relativeTime(date)}</span>
      </div>
      <h3 className="card-title">
        <a href={article.url} target="_blank" rel="noreferrer">{article.title}</a>
      </h3>
      <p className="card-source">{article.source_name}</p>
      {article.summary ? <p className="card-summary">{article.summary}</p> : null}
      {showReason ? <p className="card-reason">{article.reason}</p> : null}
      {tags.length > 0 && (
        <div className="card-tags">
          {tags.map((tag) => <span key={tag} className="tag">#{tag}</span>)}
        </div>
      )}
      <div className="card-actions">
        {actions.map((action) => (
          <button
            key={action}
            className={`action-btn action-${action}`}
            onClick={() => handle(action)}
            disabled={pending !== null}
            title={ACTION_LABELS[action]}
          >
            {pending === action ? '…' : ACTION_LABELS[action]}
          </button>
        ))}
      </div>
    </article>
  )
}

function SkeletonCard() {
  return (
    <div className="skeleton-card" aria-hidden="true">
      <div style={{ display: 'flex', gap: 6 }}>
        <div className="skeleton sk-h" style={{ width: 70 }} />
        <div className="skeleton sk-h" style={{ width: 48 }} />
        <div className="skeleton sk-h" style={{ width: 44, marginLeft: 'auto' }} />
      </div>
      <div className="skeleton sk-h" />
      <div className="skeleton sk-h-sm" />
      <div className="skeleton sk-line" />
      <div className="skeleton sk-line-sm" />
      <div className="skeleton sk-line-xs" />
      <div style={{ display: 'flex', gap: 6 }}>
        <div className="skeleton sk-bar" style={{ flex: 1 }} />
        <div className="skeleton sk-bar" style={{ flex: 1 }} />
        <div className="skeleton sk-bar" style={{ flex: 1 }} />
      </div>
    </div>
  )
}

function SourceHealthBadge({ source }: { source: Source }) {
  const hoursSince = (iso?: string | null): number | null => {
    if (!iso) return null
    const ms = Date.now() - new Date(iso).getTime()
    return Math.floor(ms / 3600000)
  }

  if (source.last_error) {
    return <span className="source-health error">● error</span>
  }
  const h = hoursSince(source.last_success_at ?? source.last_checked_at)
  if (h === null) return null
  if (h > 48) return <span className="source-health stale">● stale ({Math.floor(h / 24)}d)</span>
  return <span className="source-health healthy">● ok</span>
}

function SourcesContent({ sources }: { sources: Source[] }) {
  const grouped = useMemo(() => {
    return sources.reduce<Record<string, Source[]>>((acc, s) => {
      if (!acc[s.category]) acc[s.category] = []
      acc[s.category].push(s)
      return acc
    }, {})
  }, [sources])

  function kindClass(kind: string): string {
    if (kind.startsWith('github')) return 'kind-github'
    if (kind.startsWith('trending')) return 'kind-trending'
    if (kind.startsWith('scraped')) return 'kind-scraped'
    return 'kind-rss'
  }
  function kindLabel(kind: string): string {
    return kind.replace(/_/g, ' ').replace('feed', '').trim() || 'rss'
  }

  return (
    <div className="sources-grid">
      {Object.entries(grouped).map(([cat, items]) => (
        <article className="source-card" key={cat}>
          <h3 className="source-category">{cat.replace(/-/g, ' ')}</h3>
          <ul className="source-list">
            {items.map((source) => (
              <li key={source.slug} className="source-item">
                <div className="source-main">
                  <a href={source.url} target="_blank" rel="noreferrer">{source.name}</a>
                  <span className={`badge ${kindClass(source.kind)}`}>{kindLabel(source.kind)}</span>
                </div>
                <div className="source-meta">
                  {source.last_checked_at && (
                    <span className="source-checked">checked {relativeTime(source.last_checked_at)}</span>
                  )}
                  <SourceHealthBadge source={source} />
                </div>
                {source.last_error && (
                  <p className="source-error-msg" title={source.last_error}>
                    {source.last_error.length > 80 ? source.last_error.slice(0, 80) + '…' : source.last_error}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  )
}

/** #28 — Sources panel: bottom sheet on mobile, sidebar on desktop */
function SourcesPanel({ sources }: { sources: Source[] }) {
  const [sheetOpen, setSheetOpen] = useState(false)

  // Prevent body scroll while sheet is open
  useEffect(() => {
    if (sheetOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [sheetOpen])

  const categories = useMemo(() => {
    return Array.from(new Set(sources.map((s) => s.category)))
  }, [sources])

  const [activeCategory, setActiveCategory] = useState<string | null>(null)

  const filteredSources = activeCategory
    ? sources.filter((s) => s.category === activeCategory)
    : sources

  return (
    <>
      {/* ── Mobile: toggle button + bottom sheet ── */}
      <button
        className="sources-toggle-btn"
        onClick={() => setSheetOpen(true)}
        aria-expanded={sheetOpen}
        aria-controls="sources-sheet"
      >
        <span>📋</span>
        <span>View all {sources.length} sources</span>
        <span style={{ marginLeft: 'auto', fontSize: 18 }}>›</span>
      </button>

      {/* Overlay */}
      <div
        className={`sources-sheet-overlay${sheetOpen ? ' open' : ''}`}
        onClick={() => setSheetOpen(false)}
        aria-hidden="true"
      />

      {/* Bottom sheet */}
      <div
        id="sources-sheet"
        className={`sources-sheet${sheetOpen ? ' open' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label="News sources"
      >
        <div className="sources-sheet-handle" aria-hidden="true" />
        <div className="sources-sheet-header">
          <span className="sources-sheet-title">News Sources ({sources.length})</span>
          <button
            className="sources-sheet-close"
            onClick={() => setSheetOpen(false)}
            aria-label="Close sources panel"
          >
            ×
          </button>
        </div>
        <div className="sources-sheet-content">
          <SourcesContent sources={sources} />
        </div>
      </div>

      {/* ── Desktop: sidebar + main grid ── */}
      <div className="sources-desktop-layout">
        <aside className="sources-sidebar" aria-label="Filter by category">
          <div className="sources-sidebar-title">Categories</div>
          <button
            className={`sources-sidebar-btn${activeCategory === null ? ' active' : ''}`}
            onClick={() => setActiveCategory(null)}
          >
            All sources
            <span style={{ marginLeft: 'auto', color: 'var(--text-3)', fontSize: 11 }}>{sources.length}</span>
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              className={`sources-sidebar-btn${activeCategory === cat ? ' active' : ''}`}
              onClick={() => setActiveCategory(cat)}
            >
              {cat.replace(/-/g, ' ')}
              <span style={{ marginLeft: 'auto', color: 'var(--text-3)', fontSize: 11 }}>
                {sources.filter((s) => s.category === cat).length}
              </span>
            </button>
          ))}
        </aside>
        <div className="sources-main">
          <SourcesContent sources={filteredSources} />
        </div>
      </div>
    </>
  )
}

export default function App() {
  const [articles, setArticles] = useState<Article[]>([])
  const [sources, setSources] = useState<Source[]>([])
  const [summary, setSummary] = useState<Summary>({ byStatus: {}, byCategory: {} })
  const [activeTab, setActiveTab] = useState<ActiveTab>('inbox')
  const [category, setCategory] = useState('all')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [ingesting, setIngesting] = useState(false)
  const [message, setMessage] = useState<{ text: string; kind: 'info' | 'success' | 'error' } | null>(null)

  const currentStatus: ArticleStatus | undefined =
    activeTab !== 'sources' ? TAB_STATUS[activeTab] : undefined

  async function load(opts: { preserveMessage?: boolean } = {}) {
    setLoading(true)
    try {
      const [nextArticles, nextSources, nextSummary] = await Promise.all([
        activeTab !== 'sources'
          ? fetchArticles(currentStatus, category !== 'all' ? category : undefined)
          : Promise.resolve<Article[]>([]),
        fetchSources(),
        fetchSummary(),
      ])
      setArticles(nextArticles)
      setSources(nextSources)
      setSummary(nextSummary)
      if (!opts.preserveMessage) setMessage(null)
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'Failed to load', kind: 'error' })
    } finally {
      setLoading(false)
    }
  }

  // Re-load when tab or category changes
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [activeTab, category])

  async function runIngest() {
    setIngesting(true)
    setMessage({ text: 'Fetching feeds — this may take a minute.', kind: 'info' })
    try {
      const result = await ingestNow()
      const failed = Object.values(result.results).filter((v) => v < 0).length
      setMessage({
        text: `Done: ${result.inserted} new article(s).${failed ? ` ${failed} source(s) failed.` : ''}`,
        kind: failed ? 'info' : 'success',
      })
      await load({ preserveMessage: true })
    } catch (err) {
      setMessage({ text: err instanceof Error ? `Ingest failed: ${err.message}` : 'Ingest failed', kind: 'error' })
    } finally {
      setIngesting(false)
    }
  }

  async function changeStatus(id: number, next: ArticleStatus) {
    await updateArticleStatus(id, next)
    await load()
  }

  // Client-side search filter (also triggers backend search when in Search mode)
  const filteredArticles = useMemo(() => {
    if (!search.trim()) return articles
    const q = search.toLowerCase()
    return articles.filter(
      (a) =>
        a.title.toLowerCase().includes(q) ||
        a.summary.toLowerCase().includes(q) ||
        a.source_name.toLowerCase().includes(q) ||
        a.tags.toLowerCase().includes(q),
    )
  }, [articles, search])

  // Search across all statuses when a search term is typed
  const [searchResults, setSearchResults] = useState<Article[] | null>(null)
  const [searchLoading, setSearchLoading] = useState(false)

  useEffect(() => {
    if (!search.trim() || activeTab === 'sources') {
      setSearchResults(null)
      return
    }
    const timer = setTimeout(async () => {
      setSearchLoading(true)
      try {
        const results = await searchArticles(search)
        setSearchResults(results)
      } catch {
        setSearchResults(null)
      } finally {
        setSearchLoading(false)
      }
    }, 350)
    return () => clearTimeout(timer)
  }, [search, activeTab])

  const displayedArticles = searchResults !== null ? searchResults : filteredArticles
  const isSearchMode = searchResults !== null

  function tabCount(tab: ActiveTab): number {
    if (tab === 'sources') return sources.length
    const s = TAB_STATUS[tab as Exclude<ActiveTab, 'sources'>]
    return (summary.byStatus as Record<string, number>)[s] ?? 0
  }

  const sectionTitle = activeTab === 'sources'
    ? 'News Sources'
    : activeTab === 'inbox'
    ? 'Inbox'
    : activeTab.charAt(0).toUpperCase() + activeTab.slice(1)

  return (
    <div className="page">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="topbar-brand">
            <div className="topbar-title">Ioachim's Inbox</div>
            <div className="topbar-sub">news.lihor.ro · private</div>
          </div>

          {activeTab !== 'sources' && (
            <div className="topbar-search">
              <span className="topbar-search-icon" aria-hidden>⌕</span>
              <input
                type="search"
                placeholder="Search all articles…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                aria-label="Search articles"
              />
            </div>
          )}

          <button className="fetch-btn" onClick={runIngest} disabled={ingesting} aria-label="Fetch feeds now">
            <span className="fetch-btn-icon">{ingesting ? '⟳' : '↻'}</span>
            <span className="fetch-btn-label">{ingesting ? 'Fetching…' : 'Fetch now'}</span>
          </button>
        </div>
      </header>

      <nav className="tabs-wrap" aria-label="Sections">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`tab${activeTab === tab.id ? ' active' : ''}`}
            onClick={() => { setActiveTab(tab.id); setSearch('') }}
            aria-current={activeTab === tab.id ? 'page' : undefined}
          >
            {tab.label}
            <span className="tab-count">{tabCount(tab.id)}</span>
          </button>
        ))}
      </nav>

      {/* #29: filter bar — responsive, no overflow, safe-area handled in CSS */}
      {activeTab !== 'sources' && (
        <div className="filter-bar" role="toolbar" aria-label="Category filter">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              className={`filter-pill${category === cat ? ' active' : ''}`}
              onClick={() => setCategory(cat)}
              aria-pressed={category === cat}
            >
              {cat === 'all' ? 'All' : cat.replace(/-/g, ' ')}
            </button>
          ))}
          <span className="filter-meta">
            {loading || searchLoading
              ? 'Loading…'
              : isSearchMode
              ? `${displayedArticles.length} result${displayedArticles.length !== 1 ? 's' : ''} across all tabs`
              : `${filteredArticles.length} article${filteredArticles.length !== 1 ? 's' : ''}`}
          </span>
        </div>
      )}

      {message && (
        <div className={`message-banner ${message.kind}`} role="status">
          <span>{message.text}</span>
          <button className="dismiss" onClick={() => setMessage(null)} aria-label="Dismiss">×</button>
        </div>
      )}

      <main>
        {activeTab === 'sources' ? (
          <>
            <div className="section-header">
              <h2 className="section-title">{sectionTitle}</h2>
            </div>
            {/* #28: SourcesPanel renders bottom-sheet on mobile, sidebar on desktop */}
            <SourcesPanel sources={sources} />
          </>
        ) : (
          <>
            <div className="section-header">
              <h2 className="section-title">
                {isSearchMode ? `Search: "${search}"` : sectionTitle}
              </h2>
            </div>
            {/* #26: CSS Grid, 1-col mobile / 2-col desktop */}
            <div className="articles-grid">
              {(loading && !isSearchMode) || searchLoading ? (
                Array.from({ length: 6 }, (_, i) => <SkeletonCard key={i} />)
              ) : displayedArticles.length === 0 ? (
                <div className="empty-state">
                  <p>
                    {search
                      ? `No results for "${search}". Try different keywords.`
                      : 'Nothing here yet. Click Fetch now or wait for the cron job.'}
                  </p>
                </div>
              ) : (
                displayedArticles.map((a) => (
                  <ArticleCard key={a.id} article={a} onStatus={changeStatus} />
                ))
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
