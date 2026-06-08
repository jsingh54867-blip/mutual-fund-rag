import { useState, useRef, useEffect } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || ''

const EXAMPLE_QUERIES = [
  'What is the expense ratio of Motilal Oswal Small Cap Fund?',
  'What is the minimum SIP amount?',
  'What is the exit load for Motilal Oswal Defence Index Fund?',
]

function BotMessage({ data }) {
  if (data.error) {
    return <div className="error">{data.error}</div>
  }
  return (
    <>
      <div className="answer">{data.answer}</div>
      {data.source_link && (
        <div className="source">
          Source:{' '}
          <a href={data.source_link} target="_blank" rel="noopener noreferrer">
            {data.source_link}
          </a>
        </div>
      )}
      {data.last_updated_from_sources && (
        <div className="last-updated">
          Last updated from sources: {data.last_updated_from_sources}
        </div>
      )}
      {data.response_type && (
        <span className={`response-type badge-${data.response_type}`}>
          {data.response_type}
        </span>
      )}
    </>
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

  return (
    <div className="container">
      <header>
        <h1>Mutual Fund Facts Chatbot</h1>
        <p className="subtitle">
          Ask me factual questions about mutual funds. Facts-only. No investment advice.
        </p>
      </header>

      <div className="examples">
        <span className="examples-label">Try asking:</span>
        {EXAMPLE_QUERIES.map((ex, i) => (
          <button key={i} className="example-btn" onClick={() => send(ex)}>
            {ex}
          </button>
        ))}
      </div>

      <div className="chat-area" ref={chatRef}>
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {msg.role === 'user' ? msg.text : <BotMessage data={msg.data} />}
          </div>
        ))}
        {loading && (
          <div className="message bot">
            <div className="loading">Thinking...</div>
          </div>
        )}
      </div>

      <form className="input-area" onSubmit={handleSubmit}>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Ask a factual question about mutual funds..."
          autoComplete="off"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !query.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}
