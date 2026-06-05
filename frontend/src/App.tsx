import { useEffect, useMemo, useState } from 'react'
import './styles.css'
import { fetchArticles, fetchSources, fetchSummary, ingestNow, updateArticleStatus } from './api'
import type { Article, ArticleStatus, Source, Summary } from './types'

const statuses: Array<ArticleStatus | 'all'> = ['all', 'new', 'saved', 'read', 'skipped', 'archived']
const categories = ['all', 'python', 'ai-llm', 'agents', 'cloud-infra', 'engineering', 'trending', 'repositories']

function fmt(value?: string | null) {
  if (!value) return 'unknown'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString()
}

function statusLabel(status: ArticleStatus | 'all') {
  return status === 'all' ? 'All' : status[0].toUpperCase() + status.slice(1)
}

function tagList(tags: string) {
  return tags.split(',').map((tag) => tag.trim()).filter(Boolean)
}

function ArticleCard({ article, onStatus }: { article: Article; onStatus: (id: number, status: ArticleStatus) => Promise<void> }) {
  return (
    <article className="card article">
      <div className="cardTop">
        <span className={`pill ${article.category}`}>{article.category}</span>
        <span className={`status ${article.status}`}>{article.status}</span>
      </div>
      <h3><a href={article.url} target="_blank" rel="noreferrer">{article.title}</a></h3>
      <p className="meta">{article.source_name} · {fmt(article.published_at ?? article.discovered_at)} · score {article.importance_score}</p>
      <p className="summary">{article.summary || article.reason}</p>
      <p className="reason">{article.reason}</p>
      {tagList(article.tags).length > 0 ? (
        <div className="tags">{tagList(article.tags).map((tag) => <span key={tag}>#{tag}</span>)}</div>
      ) : null}
      <div className="actions">
        <button onClick={() => onStatus(article.id, 'read')}>Read</button>
        <button onClick={() => onStatus(article.id, 'saved')}>Save</button>
        <button onClick={() => onStatus(article.id, 'skipped')}>Skip</button>
        <button onClick={() => onStatus(article.id, 'archived')}>Archive</button>
      </div>
    </article>
  )
}

function SourcesPanel({ sources }: { sources: Source[] }) {
  const grouped = useMemo(() => {
    return sources.reduce<Record<string, Source[]>>((acc, source) => {
      acc[source.category] = [...(acc[source.category] ?? []), source]
      return acc
    }, {})
  }, [sources])

  return (
    <section>
      <h2>Sources</h2>
      <div className="sourceGrid">
        {Object.entries(grouped).map(([category, items]) => (
          <article className="card" key={category}>
            <h3>{category}</h3>
            <ul>
              {items.map((source) => (
                <li key={source.slug}>
                  <a href={source.url} target="_blank" rel="noreferrer">{source.name}</a>
                  <span className="sourceKind">{source.kind}</span>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </section>
  )
}

function App() {
  const [articles, setArticles] = useState<Article[]>([])
  const [sources, setSources] = useState<Source[]>([])
  const [summary, setSummary] = useState<Summary>({ byStatus: {}, byCategory: {} })
  const [status, setStatus] = useState<ArticleStatus | 'all'>('new')
  const [category, setCategory] = useState('all')
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    try {
      const [nextArticles, nextSources, nextSummary] = await Promise.all([
        fetchArticles(status, category),
        fetchSources(),
        fetchSummary(),
      ])
      setArticles(nextArticles)
      setSources(nextSources)
      setSummary(nextSummary)
      setMessage(null)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [status, category])

  async function runIngest() {
    setMessage('Ingesting feeds…')
    const result = await ingestNow()
    setMessage(`Ingest complete: ${result.inserted} new item(s)`)
    await load()
  }

  async function changeStatus(id: number, nextStatus: ArticleStatus) {
    await updateArticleStatus(id, nextStatus)
    await load()
  }

  return (
    <main className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">news.lihor.ro · private</p>
          <h1>Ioachim's News Inbox</h1>
          <p className="lead">Python, AI/LLM, agents, infrastructure, trending stories, and repositories — collected by Clau for reading history and later summaries.</p>
        </div>
        <button className="primary" onClick={runIngest}>Fetch now</button>
      </header>

      <section className="stats">
        {statuses.filter((item) => item !== 'all').map((item) => (
          <article className="stat card" key={item}>
            <span>{statusLabel(item)}</span>
            <strong>{summary.byStatus[item] ?? 0}</strong>
          </article>
        ))}
      </section>

      <section className="toolbar card">
        <div>
          <label>Status</label>
          <select value={status} onChange={(event) => setStatus(event.target.value as ArticleStatus | 'all')}>
            {statuses.map((item) => <option key={item} value={item}>{statusLabel(item)}</option>)}
          </select>
        </div>
        <div>
          <label>Category</label>
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            {categories.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </div>
        <div className="toolbarMeta">{loading ? 'Loading…' : `${articles.length} item(s)`}</div>
      </section>

      {message ? <p className="message">{message}</p> : null}

      <section>
        <h2>{category === 'repositories' ? 'Trending repositories' : 'Inbox'}</h2>
        <div className="articleGrid">
          {articles.map((article) => <ArticleCard key={article.id} article={article} onStatus={changeStatus} />)}
          {!loading && articles.length === 0 ? <p className="empty">No articles for this filter yet. Run ingestion or wait for the cron job.</p> : null}
        </div>
      </section>

      <SourcesPanel sources={sources} />
    </main>
  )
}

export default App
