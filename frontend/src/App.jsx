// src/App.jsx
// Root component: orchestrates layout, state, and API calls

import { useState, useCallback, useEffect, useRef } from 'react';
import { Bot, PanelRight, Moon, Sun } from 'lucide-react';
import AmbientBackground from './components/AmbientBackground';
import Sidebar from './components/Sidebar';
import ChatInput from './components/ChatInput';
import HeroState from './components/HeroState';
import MessageFeed from './components/MessageFeed';
import DossierPanel from './components/DossierPanel';
import { ThemeProvider, useTheme } from './context/ThemeContext';
import { searchIncidents, fetchHistory, fetchHistoryById, deleteHistoryById } from './api';

let msgIdCounter = 0;
function newId() { return ++msgIdCounter; }

const THINKING_STEPS = [
  'Preprocessing query & classifying intent…',
  'Running hybrid retrieval (Dense + BM25)…',
  'Applying RRF fusion across candidate pools…',
  'Cross-encoder reranking top candidates…',
  'Synthesizing answer via Qwen3:8b…',
];

/* ── Applies/removes .dark on <html> whenever theme changes ─────────────── */
function ThemeRoot({ children }) {
  const { isDark } = useTheme();
  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDark);
  }, [isDark]);
  return children;
}

/* ── Inner App (has ThemeContext access) ───────────────────────────────────── */
function AppInner() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastResponse, setLastResponse] = useState(null);
  const [showDossier, setShowDossier] = useState(false);
  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [activeHistoryId, setActiveHistoryId] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const hasMessages = messages.length > 0;

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    try { setHistory(await fetchHistory(50)); } catch { }
    finally { setLoadingHistory(false); }
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);


  const handleSubmit = useCallback(async (text) => {
    if (loading) return;
    const userMsgId = newId();
    const loadingMsgId = newId();
    let stepIdx = 0;

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', text },
      { id: loadingMsgId, role: 'ai', loading: true, step: THINKING_STEPS[0] },
    ]);
    setLoading(true);

    const stepTimer = setInterval(() => {
      stepIdx = (stepIdx + 1) % THINKING_STEPS.length;
      setMessages(prev => prev.map(m =>
        m.id === loadingMsgId ? { ...m, step: THINKING_STEPS[stepIdx] } : m
      ));
    }, 1800);

    try {
      const data = await searchIncidents(text);
      clearInterval(stepTimer);
      const aiMsg = {
        id: loadingMsgId, role: 'ai', loading: false,
        answer: data.answer, incidents: data.incidents,
        dense_ids: data.dense_ids, sparse_ids: data.sparse_ids,
        rrf_ids: data.rrf_ids, reranked_ids: data.reranked_ids,
        latency_ms: data.latency_ms, hyde_used: data.hyde_used,
        predicted_team: data.predicted_team ?? '',
        predicted_priority: data.predicted_priority ?? '',
        routing_justification: data.routing_justification ?? '',
        incident_attribution: data.incident_attribution ?? [],
      };
      setMessages(prev => prev.map(m => m.id === loadingMsgId ? aiMsg : m));
      setLastResponse(data);
      setShowDossier(true);
      loadHistory();
    } catch (err) {
      clearInterval(stepTimer);
      setMessages(prev => prev.map(m =>
        m.id === loadingMsgId
          ? {
            id: loadingMsgId, role: 'ai', loading: false,
            answer: `**Error:** ${err.message}`,
            incidents: [], latency_ms: 0, hyde_used: false,
            reranked_ids: [], dense_ids: [], sparse_ids: [], rrf_ids: []
          }
          : m
      ));
    } finally { setLoading(false); }
  }, [loading, loadHistory]);

  const handleNewSession = useCallback(() => {
    setMessages([]); setLastResponse(null);
    setShowDossier(false); setActiveHistoryId(null);
  }, []);

  const handleSelectHistory = useCallback(async (id) => {
    setActiveHistoryId(id);
    try {
      const data = await fetchHistoryById(id);
      const incs = data.incidents || [];
      setMessages([
        { id: newId(), role: 'user', text: data.query_text },
        {
          id: newId(), role: 'ai', loading: false,
          answer: data.llm_response,
          incidents: incs,
          dense_ids: data.dense_ids,
          sparse_ids: data.sparse_ids,
          rrf_ids: data.rrf_fused_ids,
          reranked_ids: data.reranked_ids,
          latency_ms: data.latency_ms,
          hyde_used: data.hyde_used,
          predicted_team: data.predicted_team ?? '',
          predicted_priority: data.predicted_priority ?? '',
          routing_justification: data.routing_justification ?? '',
          incident_attribution: data.incident_attribution ?? [],
        },
      ]);
      setLastResponse({
        answer: data.llm_response,
        incidents: incs,
        dense_ids: data.dense_ids,
        sparse_ids: data.sparse_ids,
        rrf_ids: data.rrf_fused_ids,
        reranked_ids: data.reranked_ids,
        latency_ms: data.latency_ms,
        hyde_used: data.hyde_used,
        predicted_team: data.predicted_team ?? '',
        predicted_priority: data.predicted_priority ?? '',
        routing_justification: data.routing_justification ?? '',
        incident_attribution: data.incident_attribution ?? [],
      });
      setShowDossier(true);
    } catch { }
  }, []);


  const handleDeleteHistory = useCallback(async (id) => {
    try {
      await deleteHistoryById(id);
      setHistory(prev => prev.filter(item => item.id !== id));
      if (activeHistoryId === id) {
        handleNewSession();
      }
    } catch (err) {
      console.error('Failed to delete history item:', err);
    }
  }, [activeHistoryId, handleNewSession]);

  return (
    <div style={{ position: 'relative', height: '100%', width: '100%', display: 'flex', overflow: 'hidden' }}>
      <AmbientBackground />
      <div style={{ position: 'relative', zIndex: 10, display: 'flex', height: '100%', width: '100%', overflow: 'hidden' }}>
        <Sidebar
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen(v => !v)}
          history={history}
          loadingHistory={loadingHistory}
          onNewSession={handleNewSession}
          onSelectHistory={handleSelectHistory}
          onDeleteHistory={handleDeleteHistory}
          onQuickPrompt={handleSubmit}
          activeHistoryId={activeHistoryId}
        />

        <main style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', minWidth: 0 }}>
          <TopBar
            showDossier={showDossier}
            onToggleDossier={() => setShowDossier(v => !v)}
          />
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {!hasMessages ? <HeroState onQuickPrompt={handleSubmit} /> : <MessageFeed messages={messages} />}
          </div>
          <ChatInput onSubmit={handleSubmit} loading={loading} />
        </main>
        {lastResponse && (
          <DossierPanel
            isOpen={showDossier}
            response={lastResponse}
            onClose={() => setShowDossier(false)}
          />
        )}
      </div>
    </div>
  );
}


export default function App() {
  return (
    <ThemeProvider>
      <ThemeRoot>
        <AppInner />
      </ThemeRoot>
    </ThemeProvider>
  );
}

/* ── Theme Toggle Button ─────────────────────────────────────────────────── */
function ThemeToggleButton() {
  const { isDark, toggle } = useTheme();
  return (
    <button
      id="theme-toggle-btn"
      onClick={toggle}
      title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        width: '2rem', height: '2rem', borderRadius: '0.625rem',
        border: '1px solid var(--border-btn)',
        background: 'var(--bg-btn)',
        cursor: 'pointer',
        color: isDark ? '#a78bfa' : 'var(--text-secondary)',
        flexShrink: 0,
      }}
      onMouseEnter={e => {
        e.currentTarget.style.background = 'var(--bg-btn-hover)';
        e.currentTarget.style.color = 'var(--text-brand)';
        e.currentTarget.style.borderColor = 'var(--border-strong)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = 'var(--bg-btn)';
        e.currentTarget.style.color = isDark ? '#a78bfa' : 'var(--text-secondary)';
        e.currentTarget.style.borderColor = 'var(--border-btn)';
      }}
    >
      {isDark ? <Sun size={15} strokeWidth={2.2} /> : <Moon size={15} strokeWidth={2.2} />}
    </button>
  );
}

/* ── Top navigation bar ─────────────────────────────────────────────────── */
function TopBar({ showDossier, onToggleDossier }) {
  const { isDark } = useTheme();
  return (
    <header className="glass-panel" style={{
      height: '3.5rem',
      borderBottom: '1px solid var(--border-divider)',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 1.5rem', zIndex: 10, flexShrink: 0,
    }}>
      {/* Left — status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
          <div className="ping-dot" />
          <span style={{ fontSize: '.75rem', fontWeight: 500, color: 'var(--text-secondary)' }}>
            Telemetry Stream Active
          </span>
          <span style={{
            fontSize: '.6875rem', fontFamily: 'JetBrains Mono, monospace',
            color: 'var(--text-muted)',
            background: 'var(--bg-inset)',
            padding: '.125rem .5rem', borderRadius: '.375rem',
            border: '1px solid var(--border-card)',
          }}>3,420 eps</span>
        </div>
      </div>

      {/* Right — controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '.625rem' }}>
        {/* Dark/Light toggle — left of model badge */}
        <ThemeToggleButton />

        <div style={{ height: '1rem', width: '1px', background: 'var(--border-divider)' }} />

        {/* Model badge */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '.4rem',
          background: 'var(--bg-badge)',
          border: '1px solid var(--border-btn)',
          borderRadius: '.75rem', padding: '.35rem .7rem',
          fontSize: '.75rem', fontWeight: 500,
          color: 'var(--text-secondary)',
        }}>
          <Bot size={14} strokeWidth={2} style={{ color: 'var(--text-brand)' }} />
          <span>Qwen3:8b</span>
        </div>

        <div style={{ height: '1rem', width: '1px', background: 'var(--border-divider)' }} />

        {/* Dossier toggle */}
        <button
          onClick={onToggleDossier}
          style={{
            display: 'flex', alignItems: 'center', gap: '.4rem',
            padding: '.35rem .7rem', borderRadius: '.75rem', cursor: 'pointer',
            fontSize: '.75rem', fontWeight: 600,
            background: showDossier ? 'var(--bg-btn-hover)' : 'var(--bg-btn)',
            border: showDossier ? '1px solid var(--border-strong)' : '1px solid var(--border-btn)',
            color: showDossier ? 'var(--text-brand)' : 'var(--text-secondary)',
          }}
        >
          <PanelRight size={14} strokeWidth={2} />
          <span>Incident Dossier</span>
        </button>
      </div>
    </header>
  );
}
