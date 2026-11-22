// src/components/Sidebar.jsx
// Left sidebar: Collapsible mini-rail with multi-field search, instant filter & highlight

import React, { useState, useRef, useEffect } from 'react';
import { Plus, Search, Clock, PanelLeftClose, PanelLeftOpen, Trash2, X } from 'lucide-react';
import ProjectLogo from './ProjectLogo';
import { useTheme } from '../context/ThemeContext';

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function HighlightMatch({ text, query }) {
  if (!query || !text) return text;
  const safeQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const parts = String(text).split(new RegExp(`(${safeQuery})`, 'gi'));
  return (
    <>
      {parts.map((part, i) =>
        part.toLowerCase() === query.toLowerCase() ? (
          <mark
            key={i}
            style={{
              backgroundColor: 'rgba(99, 102, 241, 0.28)',
              color: 'var(--text-link)',
              padding: '0 2px',
              borderRadius: '2px',
              fontWeight: 700,
            }}
          >
            {part}
          </mark>
        ) : (
          part
        )
      )}
    </>
  );
}

export default function Sidebar({
  isOpen, onToggle, history, loadingHistory,
  onNewSession, onSelectHistory, onDeleteHistory, onQuickPrompt, activeHistoryId,
}) {
  const [search, setSearch] = useState('');
  const [isLogoHovered, setIsLogoHovered] = useState(false);
  const inputRef = useRef(null);
  const { isDark } = useTheme();

  const trimmedSearch = search.trim().toLowerCase();

  const filtered = (history || []).filter(h => {
    if (!trimmedSearch) return true;
    const titleMatch = (h.title || '').toLowerCase().includes(trimmedSearch);
    const queryMatch = (h.query_text || '').toLowerCase().includes(trimmedSearch);
    const teamMatch = (h.predicted_team || '').toLowerCase().includes(trimmedSearch);
    const priorityMatch = (h.predicted_priority || '').toLowerCase().includes(trimmedSearch);
    const responseMatch = (h.llm_response || '').toLowerCase().includes(trimmedSearch);
    const idMatch = (h.id || '').toLowerCase().includes(trimmedSearch);
    return titleMatch || queryMatch || teamMatch || priorityMatch || responseMatch || idMatch;
  });

  const handleSearchButtonClick = () => {
    if (!isOpen) {
      onToggle();
      setTimeout(() => inputRef.current?.focus(), 150);
    } else {
      inputRef.current?.focus();
    }
  };

  return (
    <aside
      className="glass-sidebar"
      style={{
        width: isOpen ? '280px' : '60px',
        flexShrink: 0,
        display: 'flex', flexDirection: 'column',
        height: '100%', zIndex: 20,
        transition: 'width 0.35s cubic-bezier(0.4,0,0.2,1)',
        overflow: 'hidden', position: 'relative',
        borderRight: '1px solid var(--border-sidebar)',
      }}
    >
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div style={{
        padding: '0.875rem 0.75rem',
        borderBottom: '1px solid var(--border-sidebar)',
        display: 'flex', alignItems: 'center',
        justifyContent: isOpen ? 'space-between' : 'center',
        minHeight: '3.75rem',
      }}>
        {isOpen ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', overflow: 'hidden' }}>
            <div
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, cursor: 'pointer' }}
              onMouseEnter={() => setIsLogoHovered(true)}
              onMouseLeave={() => setIsLogoHovered(false)}
            >
              <ProjectLogo size={32} />
            </div>
            <div style={{ overflow: 'hidden' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <span style={{ fontWeight: 800, fontSize: '0.875rem', color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
                  AURA
                </span>
                <span style={{
                  fontSize: '0.5625rem', fontWeight: 700,
                  color: 'var(--text-brand)', background: 'var(--bg-inset)',
                  border: '1px solid var(--border-card)',
                  padding: '0.05rem 0.35rem', borderRadius: '4px',
                  letterSpacing: '0.05em',
                }}>
                  v2.0
                </span>
              </div>
              <div style={{ fontSize: '0.625rem', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                Incident Intelligence
              </div>
            </div>
          </div>
        ) : (
          <div
            onClick={onToggle}
            style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            title="Expand Sidebar"
            onMouseEnter={() => setIsLogoHovered(true)}
            onMouseLeave={() => setIsLogoHovered(false)}
          >
            <ProjectLogo size={28} />
          </div>
        )}

        {isOpen && (
          <button
            onClick={onToggle}
            title="Collapse sidebar"
            style={{
              background: 'transparent', border: 'none', cursor: 'pointer',
              color: 'var(--text-muted)', display: 'flex', alignItems: 'center',
              padding: '0.25rem', borderRadius: '0.375rem',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.background = 'var(--bg-btn-hover)'; }}
            onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.background = 'transparent'; }}
          >
            <PanelLeftClose size={16} strokeWidth={2} />
          </button>
        )}
      </div>

      {/* ── New Session & Search ────────────────────────────────────────────── */}
      <div style={{ padding: isOpen ? '0.75rem' : '0.5rem 0.35rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {/* New Chat button */}
        <button
          onClick={onNewSession}
          className="btn-flow"
          title="New Investigation (⌘N)"
          style={{
            width: '100%',
            padding: isOpen ? '0.6rem 0.875rem' : '0.6rem 0',
            borderRadius: '0.625rem',
            display: 'flex', alignItems: 'center',
            justifyContent: isOpen ? 'flex-start' : 'center',
            gap: '0.5rem',
          }}
        >
          <Plus size={16} strokeWidth={2.5} style={{ flexShrink: 0 }} />
          {isOpen && (
            <>
              <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>New Session</span>
              <span style={{
                marginLeft: 'auto', fontFamily: 'JetBrains Mono, monospace',
                fontSize: '0.5625rem', color: 'var(--text-muted)',
                background: 'var(--bg-inset)',
                padding: '0.1rem 0.3rem', borderRadius: '3px',
              }}>⌘N</span>
            </>
          )}
        </button>

        {/* Search */}
        {isOpen ? (
          <div style={{ position: 'relative' }}>
            <span style={{ position: 'absolute', left: '0.625rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', pointerEvents: 'none' }}>
              <Search size={14} strokeWidth={2.4} />
            </span>
            <input
              ref={inputRef}
              value={search}
              onChange={e => setSearch(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Escape') setSearch('');
              }}
              placeholder="Search investigations..."
              style={{
                width: '100%',
                paddingLeft: '1.85rem',
                paddingRight: search ? '1.85rem' : '0.625rem',
                paddingTop: '0.42rem',
                paddingBottom: '0.42rem',
                background: 'var(--bg-inset)',
                border: '1px solid var(--border-card)',
                borderRadius: '0.5rem',
                fontSize: '0.71875rem',
                color: 'var(--text-primary)',
                fontFamily: 'Inter, sans-serif',
                outline: 'none',
                transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
              }}
              onFocus={e => {
                e.target.style.borderColor = 'var(--border-strong)';
                e.target.style.boxShadow = '0 0 0 2px rgba(99,102,241,0.12)';
              }}
              onBlur={e => {
                e.target.style.borderColor = 'var(--border-card)';
                e.target.style.boxShadow = 'none';
              }}
            />
            {search && (
              <button
                onClick={() => {
                  setSearch('');
                  inputRef.current?.focus();
                }}
                title="Clear search"
                style={{
                  position: 'absolute',
                  right: '0.5rem',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  padding: '0.15rem',
                  borderRadius: '50%',
                }}
                onMouseEnter={e => e.currentTarget.style.color = 'var(--text-primary)'}
                onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
              >
                <X size={12} strokeWidth={2.4} />
              </button>
            )}
          </div>
        ) : (
          <button
            onClick={handleSearchButtonClick}
            title="Search investigations"
            style={{
              width: '100%', padding: '0.55rem 0', borderRadius: '0.625rem',
              background: 'var(--bg-btn)', border: '1px solid var(--border-btn)',
              cursor: 'pointer', color: 'var(--text-secondary)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-btn-hover)'; e.currentTarget.style.color = 'var(--text-brand)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'var(--bg-btn)'; e.currentTarget.style.color = 'var(--text-secondary)'; }}
          >
            <Search size={15} strokeWidth={2.4} />
          </button>
        )}
      </div>

      {/* ── History ────────────────────────────────────────────────────────── */}
      <div style={{
        flex: 1, overflowY: 'auto', overflowX: 'hidden',
        padding: isOpen ? '0.5rem 0.75rem' : '0.5rem 0.35rem',
        display: 'flex', flexDirection: 'column', gap: '0.35rem',
      }}>
        {isOpen && (
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '0.2rem 0.375rem', fontSize: '0.59375rem', fontWeight: 700,
            textTransform: 'uppercase', letterSpacing: '0.075em', color: 'var(--text-muted)',
          }}>
            <span>{trimmedSearch ? `Results (${filtered.length})` : 'Recent Investigations'}</span>
            {trimmedSearch && (
              <button
                onClick={() => setSearch('')}
                style={{
                  background: 'none', border: 'none', color: 'var(--text-link)',
                  fontSize: '0.59375rem', cursor: 'pointer', padding: 0, fontWeight: 600,
                }}
              >
                Clear
              </button>
            )}
          </div>
        )}

        {loadingHistory && [0, 1, 2, 3].map(i => (
          <div key={i} className="shimmer" style={{ height: isOpen ? '3.25rem' : '2.25rem', borderRadius: '0.625rem' }} />
        ))}

        {!loadingHistory && filtered.length === 0 && isOpen && (
          <div style={{ fontSize: '0.71875rem', color: 'var(--text-muted)', padding: '1rem 0.5rem', textAlign: 'center', lineHeight: 1.5 }}>
            {trimmedSearch ? (
              <>
                <div>No investigations match <strong>"{search}"</strong></div>
                <button
                  onClick={() => setSearch('')}
                  style={{
                    marginTop: '0.5rem', background: 'var(--bg-btn)',
                    border: '1px solid var(--border-btn)', borderRadius: '0.375rem',
                    padding: '0.25rem 0.6rem', fontSize: '0.625rem',
                    color: 'var(--text-link)', cursor: 'pointer',
                  }}
                >
                  Clear search filter
                </button>
              </>
            ) : (
              'No investigations yet'
            )}
          </div>
        )}

        {!loadingHistory && filtered.map((h, index) => (
          <HistoryItem
            key={h.id}
            item={h}
            isOpen={isOpen}
            index={index}
            searchQuery={trimmedSearch}
            active={h.id === activeHistoryId}
            onClick={() => onSelectHistory(h.id)}
            onDelete={onDeleteHistory}
          />
        ))}
      </div>

      {/* ── Footer: User ───────────────────────────────────────────────────── */}
      <div style={{
        padding: isOpen ? '0.75rem 0.875rem' : '0.75rem 0.5rem',
        borderTop: '1px solid var(--border-sidebar)',
        background: isDark ? 'rgba(8,13,26,0.5)' : 'rgba(255,255,255,0.35)',
        display: 'flex', alignItems: 'center',
        justifyContent: isOpen ? 'flex-start' : 'center',
      }}>
        <div
          title="SRE On-Call Lead (prod-us-east-1)"
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}
          onClick={!isOpen ? onToggle : undefined}
        >
          <div style={{ position: 'relative', flexShrink: 0 }}>
            <div style={{
              width: '1.9rem', height: '1.9rem', borderRadius: '50%',
              background: isDark
                ? 'linear-gradient(135deg, #1e293b, #334155)'
                : 'linear-gradient(135deg, #e2e8f0, #cbd5e1)',
              border: isDark ? '1.5px solid rgba(99,102,241,0.3)' : '1.5px solid rgba(226,232,240,0.8)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '0.625rem', fontWeight: 800, color: 'var(--text-primary)',
              boxShadow: 'none',
            }}>
              SRE
            </div>
            <span style={{
              position: 'absolute', bottom: 0, right: 0,
              width: '0.5rem', height: '0.5rem',
              background: '#10b981', borderRadius: '50%',
              border: isDark ? '1.5px solid #080D1A' : '1.5px solid #fff',
            }} />
          </div>
          {isOpen && (
            <div style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}>
              <div style={{ fontSize: '0.71875rem', fontWeight: 700, color: 'var(--text-primary)' }}>SRE On-Call Lead</div>
              <div style={{ fontSize: '0.59375rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>prod-us-east-1</div>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

function HistoryItem({ item, isOpen, active, index = 0, searchQuery = '', onClick, onDelete }) {
  const [hovered, setHovered] = useState(false);
  const latency = item.latency_ms ? `${item.latency_ms}ms` : '';
  const { isDark } = useTheme();
  const displayTitle = item.title || item.query_text;

  const p = (item.predicted_priority || '').toLowerCase();
  const dotColor = p.includes('critical') || /^1/.test(p) ? '#dc2626'
    : p.includes('high') || /^2/.test(p) ? '#ea580c'
      : p.includes('medium') || /^3/.test(p) ? '#ca8a04'
        : p.includes('low') || /^4/.test(p) ? '#16a34a'
          : '#6366f1';

  const animDelay = `${Math.min(index * 0.04, 0.3)}s`;

  const handleDelete = (e) => {
    e.stopPropagation();
    if (onDelete) onDelete(item.id);
  };

  const titleMatched = (item.title || '').toLowerCase().includes(searchQuery.toLowerCase());
  const queryMatched = (item.query_text || '').toLowerCase().includes(searchQuery.toLowerCase());

  if (!isOpen) {
    return (
      <div
        onClick={onClick}
        title={`${displayTitle} (${item.predicted_priority || 'Incident'})`}
        className="glass-card sidebar-flow-item"
        style={{
          width: '2.25rem', height: '2.25rem', margin: '0 auto',
          borderRadius: '0.5rem', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: active ? (isDark ? 'rgba(79,70,229,0.20)' : 'rgba(238,242,255,0.95)') : undefined,
          borderColor: active ? 'var(--border-strong)' : undefined,
          animationDelay: animDelay,
        }}
      >
        <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: dotColor, display: 'inline-block', boxShadow: `0 0 6px ${dotColor}88` }} />
      </div>
    );
  }

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="glass-card sidebar-flow-item"
      style={{
        padding: '0.55rem 0.65rem', borderRadius: '0.625rem',
        cursor: 'pointer', position: 'relative', overflow: 'hidden',
        background: active ? (isDark ? 'rgba(79,70,229,0.18)' : 'rgba(255,255,255,0.95)') : undefined,
        borderColor: active ? 'var(--border-strong)' : undefined,
        boxShadow: active ? '0 3px 10px rgba(99,102,241,0.10)' : undefined,
        animationDelay: animDelay,
      }}
    >
      {active && <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: '3px', background: '#6366f1', borderRadius: '0 2px 2px 0' }} />}

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
        <div
          className="sidebar-flow-text"
          title={`${displayTitle}\nQuery: ${item.query_text}`}
          style={{
            fontWeight: 600, fontSize: '0.71875rem',
            color: active ? 'var(--text-brand)' : 'var(--text-primary)',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            flex: 1, minWidth: 0, marginRight: '0.25rem',
          }}
        >
          <HighlightMatch text={displayTitle} query={searchQuery} />
        </div>

        {/* Delete action button */}
        <button
          onClick={handleDelete}
          title="Delete investigation"
          style={{
            padding: '0.15rem 0.25rem', borderRadius: '0.35rem', border: 'none',
            background: 'transparent', cursor: 'pointer',
            color: 'var(--text-muted)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            opacity: hovered || active ? 0.75 : 0,
            transition: 'opacity 0.15s ease, color 0.15s ease, background 0.15s ease',
            flexShrink: 0,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.opacity = '1';
            e.currentTarget.style.color = '#ef4444';
            e.currentTarget.style.background = 'rgba(239, 68, 68, 0.15)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.opacity = '0.75';
            e.currentTarget.style.color = 'var(--text-muted)';
            e.currentTarget.style.background = 'transparent';
          }}
        >
          <Trash2 size={11} strokeWidth={2} />
        </button>
      </div>

      {/* If search matched query text instead of title, display query snippet */}
      {searchQuery && !titleMatched && queryMatched && (
        <div style={{
          fontSize: '0.5625rem', color: 'var(--text-secondary)',
          marginBottom: '0.2rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          fontStyle: 'italic',
        }}>
          ↳ <HighlightMatch text={item.query_text} query={searchQuery} />
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.59375rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <Clock size={10} strokeWidth={2.2} />
          {timeAgo(item.created_at)}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: dotColor, display: 'inline-block' }} title={item.predicted_priority} />
          {item.predicted_team && (
            <span style={{ color: 'var(--text-link)', maxWidth: '85px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              <HighlightMatch text={item.predicted_team} query={searchQuery} />
            </span>
          )}
          {!item.predicted_team && latency && <span style={{ color: 'var(--text-link)' }}>{latency}</span>}
        </div>
      </div>
    </div>
  );
}
