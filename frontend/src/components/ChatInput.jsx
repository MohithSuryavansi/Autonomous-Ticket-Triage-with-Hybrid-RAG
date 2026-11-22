// src/components/ChatInput.jsx
// Floating glassmorphic input — fully theme-aware via CSS vars

import { useRef, useCallback } from 'react';
import { Paperclip, Mic, ArrowRight } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

export default function ChatInput({ onSubmit, loading }) {
  const ref = useRef(null);
  const { isDark } = useTheme();

  const submit = useCallback(() => {
    const text = ref.current?.value?.trim();
    if (!text || loading) return;
    ref.current.value = '';
    ref.current.style.height = 'auto';
    onSubmit(text);
  }, [loading, onSubmit]);

  const handleKey = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
  }, [submit]);

  const autoResize = useCallback((e) => {
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
  }, []);

  return (
    <div style={{ padding: '0 1rem 1.25rem', maxWidth: '800px', width: '100%', margin: '0 auto' }}>
      <div className="glass-input" style={{ borderRadius: '1.5rem', padding: '.625rem', display: 'flex', flexDirection: 'column', gap: '.5rem' }}>
        <textarea
          ref={ref}
          rows={2}
          placeholder="Describe an incident, issue, or paste log telemetry… (Enter to send)"
          onKeyDown={handleKey}
          onInput={autoResize}
          disabled={loading}
          style={{
            width: '100%', background: 'transparent',
            border: 'none', outline: 'none',
            fontSize: '.875rem', color: 'var(--text-primary)',
            fontFamily: 'Inter, sans-serif',
            lineHeight: 1.6, resize: 'none', padding: '.25rem .75rem',
          }}
        />

        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '.375rem .5rem 0',
          borderTop: `1px solid ${isDark ? 'rgba(99,102,241,0.14)' : 'rgba(226,232,240,.4)'}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '.25rem' }}>
            <IconBtn title="Attach log file"><Paperclip size={16} strokeWidth={2} /></IconBtn>
            <IconBtn title="Voice input"><Mic size={16} strokeWidth={2} /></IconBtn>
            <span style={{ height: '0.875rem', width: '1px', background: 'var(--border-divider)', margin: '0 .25rem' }} />
            <span style={{ fontSize: '.6875rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>
              Grounding: BM25 • BGE • Qwen3
            </span>
          </div>

          <button
            onClick={submit}
            disabled={loading}
            className="btn-flow"
            style={{
              padding: '.5rem 1rem', borderRadius: '.875rem',
              display: 'flex', alignItems: 'center', gap: '.375rem',
              opacity: loading ? .6 : 1, cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? (
              <>
                <span style={{ display: 'flex', gap: '3px' }}>
                  <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
                </span>
                <span>Analyzing</span>
              </>
            ) : (
              <>
                <span>Analyze Query</span>
                <ArrowRight size={14} strokeWidth={2.5} />
              </>
            )}
          </button>
        </div>
      </div>

      <div style={{
        display: 'flex', justifyContent: 'space-between',
        fontSize: '.6875rem', color: 'var(--text-muted)', padding: '.375rem 1rem 0',
      }}>
        <span>AURA AI processes against historical incidents with hybrid RAG</span>
        <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>Shift+Enter for newline</span>
      </div>
    </div>
  );
}

function IconBtn({ children, title }) {
  return (
    <button
      title={title}
      style={{
        padding: '.375rem', borderRadius: '.625rem', border: 'none',
        background: 'transparent', cursor: 'pointer',
        color: 'var(--text-muted)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-btn-hover)'; e.currentTarget.style.color = 'var(--text-brand)'; }}
      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-muted)'; }}
    >
      {children}
    </button>
  );
}
