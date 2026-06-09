import { useState, useRef, useEffect } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE || ''

const SUGGESTED_QUERIES = [
  'What is the 3Y return of MO Midcap Fund?',
  'Top holdings of Motilal Oswal Flexi Cap?',
  'Current NAV of MO Large and Midcap Fund?',
]

const FACTUAL_TYPES = new Set(['factual'])

function TypingDots() {
  return (
    <div className="typing-dots">
      <span /><span /><span />
    </div>
  )
}

function BotMessage({ data }) {
  const isFactual = FACTUAL_TYPES.has(data.response_type)

  if (data.error) {
    return <div className="bot-answer error-text">{data.error}</div>
  }

  return (
    <div className="bot-content">
      <div className="bot-answer">{data.answer}</div>

      {isFactual && data.source_link && (
        <div className="bot-meta">
          <a
            href={data.source_link}
            target="_blank"
            rel="noopener noreferrer"
            className="source-link"
          >
            ↗ View Source
          </a>
        </div>
      )}

      {isFactual && data.last_updated_from_sources && (
        <div className="last-updated">
          Updated: {data.last_updated_from_sources}
        </div>
      )}

      {isFactual && (
        <span className="badge-factual">FACTUAL</span>
      )}
    </div>
  )
}

export default function App() {
  const [messages, setMessages] = useState([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const chatRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight
    }
  }, [messages, loading])

  async function send(q) {
    const text = (q || query).trim()
    if (!text || loading) return

    setMessages(prev => [...prev, { role: 'user', text }])
    setQuery('')
    setLoading(true)

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text }),
      })
      const data = await res.json()
      setMessages(prev => [...prev, { role: 'bot', data }])
    } catch (err) {
      setMessages(prev => [
        ...prev,
        { role: 'bot', data: { error: `Network error: ${err.message}` } },
      ])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  function handleSubmit(e) {
    e.preventDefault()
    send()
  }

  const isEmpty = messages.length === 0 && !loading

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="header-left">
            <div className="logo-placeholder">MO</div>
            <span className="header-title">Motilal Oswal Fund Assistant</span>
          </div>
          <span className="header-badge">Fact-based · No Investment Advice</span>
        </div>
      </header>

      <main className="chat-area" ref={chatRef}>
        {isEmpty && (
          <div className="empty-state">
            <div className="empty-greeting">
              What would you like to know about Motilal Oswal Funds?
            </div>
            <div className="suggestion-chips">
              {SUGGESTED_QUERIES.map((q, i) => (
                <button key={i} className="chip" onClick={() => send(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`message-row ${msg.role}`}
          >
            {msg.role === 'user' ? (
              <div className="user-bubble">{msg.text}</div>
            ) : (
              <div className="bot-card">
                <BotMessage data={msg.data} />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="message-row bot">
            <div className="bot-card">
              <TypingDots />
            </div>
          </div>
        )}
      </main>

      <div className="input-footer">
        <div className="disclaimer">
          For informational purposes only. Not investment advice. Consult a SEBI-registered advisor.
        </div>
        <div className="input-bar">
          <form className="input-form" onSubmit={handleSubmit}>
            <input
              ref={inputRef}
              type="text"
              className="input-field"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Ask about NAV, fund performance, holdings..."
              autoComplete="off"
              disabled={loading}
            />
            <button
              type="submit"
              className="send-btn"
              disabled={loading || !query.trim()}
              aria-label="Send"
            >
              ↑
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
