import React, { useEffect, useRef } from 'react';
import {
  AlertTriangle, AlertCircle, Users, Lightbulb,
  Sparkles, FileText, Clock, Layers, CheckCircle2,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';


/* ── Markdown renderer ────────────────────────────────────────────────────── */
function renderMarkdown(text) {
  if (!text) return '';
  let html = text
    .replace(/```(\w*)\n?([\s\S]*?)```/g, (_, _lang, code) =>
      `<pre class="md-code"><code>${escHtml(code.trim())}</code></pre>`)
    .replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^## (.+)$/gm, '<h2 class="md-h2">$1</h2>')
    .replace(/^### (.+)$/gm, '<h3 class="md-h3">$1</h3>')
    .replace(/^# (.+)$/gm, '<h1 class="md-h1">$1</h1>')
    .replace(/^(\d+)[.)]\s+(.+)$/gm, '<li class="md-oli">$2</li>')
    .replace(/^[-*]\s+(.+)$/gm, '<li class="md-uli">$1</li>');

  html = html.replace(/(<li class="md-oli">[\s\S]*?<\/li>)(\s*<li class="md-oli">[\s\S]*?<\/li>)*/g,
    match => `<ol class="md-ol">${match}</ol>`);
  html = html.replace(/(<li class="md-uli">[\s\S]*?<\/li>)(\s*<li class="md-uli">[\s\S]*?<\/li>)*/g,
    match => `<ul class="md-ul">${match}</ul>`);

  html = html.replace(/\n\n+/g, '\n\n');
  const lines = html.split('\n');
  const out = [];
  let inParagraph = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (inParagraph) { out.push('</p>'); inParagraph = false; }
      continue;
    }
    if (/^<(h[1-3]|ol|ul|pre|li)/.test(trimmed)) {
      if (inParagraph) { out.push('</p>'); inParagraph = false; }
      out.push(trimmed);
    } else {
      if (!inParagraph) { out.push('<p class="md-p">'); inParagraph = true; }
      else out.push(' ');
      out.push(trimmed);
    }
  }
  if (inParagraph) out.push('</p>');
  return out.join('');
}

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

/* ── Priority style mapping ───────────────────────────────────────────────── */
function priorityStyle(priority = '') {
  const p = (priority || '').toLowerCase();
  if (p.includes('critical') || /^1\s*[-–]/.test(p) || p === '1')
    return { bg: '#fef2f2', darkBg: 'rgba(239,68,68,0.12)', color: '#dc2626', darkColor: '#f87171', border: '#fca5a5', darkBorder: 'rgba(239,68,68,0.30)', pill: '#dc2626', Icon: AlertCircle };
  if (p.includes('high') || /^2\s*[-–]/.test(p) || p === '2')
    return { bg: '#fff7ed', darkBg: 'rgba(245,158,11,0.12)', color: '#ea580c', darkColor: '#fbbf24', border: '#fdba74', darkBorder: 'rgba(245,158,11,0.30)', pill: '#ea580c', Icon: AlertTriangle };
  if (p.includes('moderate') || p.includes('medium') || /^3\s*[-–]/.test(p) || p === '3')
    return { bg: '#fefce8', darkBg: 'rgba(234,179,8,0.12)', color: '#ca8a04', darkColor: '#facc15', border: '#fde047', darkBorder: 'rgba(234,179,8,0.30)', pill: '#ca8a04', Icon: AlertTriangle };
  if (p.includes('low') || /^4\s*[-–]/.test(p) || p === '4')
    return { bg: '#f0fdf4', darkBg: 'rgba(22,163,74,0.12)', color: '#16a34a', darkColor: '#4ade80', border: '#86efac', darkBorder: 'rgba(22,163,74,0.30)', pill: '#16a34a', Icon: CheckCircle2 };
  return { bg: '#f8fafc', darkBg: 'rgba(99,102,241,0.10)', color: '#64748b', darkColor: '#94a3b8', border: '#e2e8f0', darkBorder: 'rgba(99,102,241,0.22)', pill: '#64748b', Icon: AlertCircle };
}

/* ── Main feed ────────────────────────────────────────────────────────────── */
export default function MessageFeed({ messages }) {
  const bottomRef = useRef(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem 1rem' }}>
      <MarkdownStyleInjector />
      <div style={{ maxWidth: '860px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
        {messages.map(msg =>
          msg.role === 'user'
            ? <UserBubble key={msg.id} text={msg.text} />
            : <AIBubble key={msg.id} msg={msg} />
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

/* ── User bubble ──────────────────────────────────────────────────────────── */
function UserBubble({ text }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
      <div style={{
        maxWidth: '72%', padding: '0.875rem 1.125rem',
        borderRadius: '1.25rem 1.25rem 0.375rem 1.25rem',
        background: 'linear-gradient(135deg, #6366f1, #4f46e5)',
        color: '#fff', fontSize: '0.875rem', lineHeight: 1.65,
        boxShadow: '0 4px 18px rgba(99,102,241,.38)',
      }}>
        {text}
      </div>
    </div>
  );
}

/* ── AI bubble ────────────────────────────────────────────────────────────── */
function AIBubble({ msg }) {
  const { isDark } = useTheme();

  if (msg.loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-start', width: '100%' }}>
        <div className="glass-card" style={{ padding: '0.875rem 1.125rem', borderRadius: '1rem', minWidth: '160px' }}>
          {msg.step && (
            <div style={{ fontSize: '0.6875rem', color: 'var(--text-brand)', fontFamily: 'JetBrains Mono, monospace', marginBottom: '0.5rem', fontWeight: 500 }}>
              ◌ {msg.step}
            </div>
          )}
          <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
            <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
          </div>
        </div>
      </div>
    );
  }

  const pInfo = priorityStyle(msg.predicted_priority);
  const PriorityIcon = pInfo.Icon;
  const hasMeta = msg.predicted_team || msg.predicted_priority;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
      <div style={{ width: '100%', minWidth: 0 }}>


        {hasMeta && (
          <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '0.625rem', marginBottom: '0.625rem' }}>
            {/* Severity pill */}
            {msg.predicted_priority && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: '0.5rem',
                padding: '0.5rem 0.875rem',
                background: isDark ? pInfo.darkBg : pInfo.bg,
                border: `1px solid ${isDark ? pInfo.darkBorder : pInfo.border}`,
                borderRadius: '0.75rem',
              }}>
                <PriorityIcon size={16} strokeWidth={2.2} style={{ color: isDark ? pInfo.darkColor : pInfo.color }} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.05rem' }}>
                  <span style={{ fontSize: '0.5rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: isDark ? pInfo.darkColor : pInfo.color, opacity: 0.8 }}>Severity</span>
                  <span style={{ fontSize: '0.8125rem', fontWeight: 800, color: isDark ? pInfo.darkColor : pInfo.color, fontFamily: 'JetBrains Mono, monospace', whiteSpace: 'nowrap' }}>
                    {msg.predicted_priority}
                  </span>
                </div>
              </div>
            )}

            {/* Team card */}
            {msg.predicted_team && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: '0.5rem',
                padding: '0.5rem 0.875rem',
                background: isDark ? 'rgba(99,102,241,0.14)' : '#eef2ff',
                border: `1px solid ${isDark ? 'rgba(99,102,241,0.28)' : '#c7d2fe'}`,
                borderRadius: '0.75rem',
              }}>
                <Users size={16} strokeWidth={2} style={{ color: 'var(--text-brand)' }} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.05rem' }}>
                  <span style={{ fontSize: '0.5rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-brand)', opacity: 0.8 }}>Designated Team</span>
                  <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--text-link)' }}>{msg.predicted_team}</span>
                </div>
              </div>
            )}

            {/* Justification */}
            {msg.routing_justification && (
              <div style={{
                gridColumn: '1 / -1', padding: '0.5rem 0.875rem',
                background: isDark ? 'rgba(14,21,40,0.7)' : 'rgba(248,250,252,0.9)',
                border: `1px solid var(--border-card)`,
                borderRadius: '0.625rem',
                fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.55,
                display: 'flex', alignItems: 'flex-start', gap: '0.4rem',
              }}>
                <Lightbulb size={14} strokeWidth={2} style={{ color: 'var(--text-brand)', flexShrink: 0, marginTop: '2px' }} />
                <span>{msg.routing_justification}</span>
              </div>
            )}
          </div>
        )}

        {/* Main answer card */}
        <div className="glass-card" style={{ padding: '1.375rem 1.5rem', borderRadius: '0.375rem 1.25rem 1.25rem 1.25rem' }}>

          {/* HyDE badge */}
          {msg.hyde_used && (
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '0.35rem',
              fontSize: '0.625rem', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700,
              color: isDark ? '#a78bfa' : '#7c3aed',
              background: isDark ? 'rgba(139,92,246,0.14)' : '#f5f3ff',
              border: `1px solid ${isDark ? 'rgba(139,92,246,0.28)' : '#ddd6fe'}`,
              padding: '0.125rem 0.5rem', borderRadius: '4px', marginBottom: '0.875rem',
            }}>
              <Sparkles size={11} strokeWidth={2.2} />
              <span>HyDE Fallback Active</span>
            </div>
          )}

          {/* Answer */}
          <div className="answer-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.answer || '') }} />

          {/* Attribution table */}
          {msg.incident_attribution?.length > 0 && (
            <div style={{ marginTop: '1.5rem', paddingTop: '1.25rem', borderTop: `1px solid var(--border-divider)` }}>
              <div style={{ fontSize: '0.5625rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: '0.625rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <FileText size={12} strokeWidth={2} style={{ color: 'var(--text-brand)' }} />
                <span>Historical Incident Attribution</span>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.6875rem', fontFamily: 'JetBrains Mono, monospace' }}>
                  <thead>
                    <tr style={{ background: 'var(--bg-inset)' }}>
                      {['#', 'Incident ID', 'Handling Team', 'Urgency', 'Impact'].map(h => (
                        <th key={h} style={{
                          padding: '0.375rem 0.75rem', textAlign: 'left',
                          fontSize: '0.5625rem', textTransform: 'uppercase',
                          letterSpacing: '0.06em', color: 'var(--text-muted)', fontWeight: 700,
                          borderBottom: `1px solid var(--border-divider)`, whiteSpace: 'nowrap',
                        }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {msg.incident_attribution.map((attr, i) => (
                      <tr key={attr.id ?? i} style={{ borderBottom: `1px solid var(--border-divider)` }}>
                        <td style={{ padding: '0.375rem 0.75rem', color: 'var(--text-muted)' }}>{i + 1}</td>
                        <td style={{ padding: '0.375rem 0.75rem', color: 'var(--text-link)', fontWeight: 700 }}>{attr.id}</td>
                        <td style={{ padding: '0.375rem 0.75rem', color: 'var(--text-secondary)' }}>{attr.team || '—'}</td>
                        <td style={{ padding: '0.375rem 0.75rem', color: 'var(--text-secondary)' }}>{attr.urgency || '—'}</td>
                        <td style={{ padding: '0.375rem 0.75rem', color: 'var(--text-secondary)' }}>{attr.impact || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Footer stats */}
          <div style={{
            display: 'flex', gap: '1rem', marginTop: '1rem', paddingTop: '0.75rem',
            borderTop: `1px solid var(--border-divider)`,
            fontSize: '0.625rem', color: 'var(--text-muted)',
            fontFamily: 'JetBrains Mono, monospace', flexWrap: 'wrap',
          }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <Clock size={11} strokeWidth={2} />{msg.latency_ms}ms
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <Layers size={11} strokeWidth={2} />{msg.reranked_ids?.length ?? 0} incidents retrieved
            </span>
            {msg.hyde_used && (
              <span style={{ color: 'var(--text-brand)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                <Sparkles size={11} strokeWidth={2} />HyDE
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Injected markdown styles — theme-adaptive via CSS vars ───────────────── */

function MarkdownStyleInjector() {
  return (
    <style>{`
      .answer-body { font-size:0.875rem; line-height:1.75; color:var(--text-primary); }
      .answer-body .md-h1 { font-size:1.125rem; font-weight:800; color:var(--text-primary); margin:1.25rem 0 0.5rem; padding-bottom:0.375rem; border-bottom:2px solid var(--border-divider); }
      .answer-body .md-h2 { font-size:1rem; font-weight:700; color:var(--text-primary); margin:1.375rem 0 0.5rem; display:flex; align-items:center; gap:0.375rem; padding:0.5rem 0.75rem; background:var(--bg-inset); border-left:3px solid #6366f1; border-radius:0 0.5rem 0.5rem 0; }
      .answer-body .md-h3 { font-size:0.75rem; font-weight:700; color:var(--text-secondary); margin:1rem 0 0.375rem; text-transform:uppercase; letter-spacing:0.04em; }
      .answer-body .md-p { margin:0.625rem 0; color:var(--text-secondary); }
      .answer-body .md-ol { margin:0.5rem 0 0.75rem 0; padding-left:1.25rem; display:flex; flex-direction:column; gap:0.375rem; }
      .answer-body .md-ul { margin:0.5rem 0 0.75rem 0; padding-left:1.25rem; display:flex; flex-direction:column; gap:0.3rem; }
      .answer-body .md-oli, .answer-body .md-uli { color:var(--text-secondary); line-height:1.65; }
      .answer-body .md-oli::marker { color:#6366f1; font-weight:700; }
      .answer-body .md-uli { list-style-type:disc; }
      .answer-body .md-uli::marker { color:#6366f1; }
      .answer-body .md-code { background:var(--bg-inset); color:var(--text-primary); border:1px solid var(--border-card); border-radius:0.5rem; padding:0.875rem 1rem; overflow-x:auto; margin:0.75rem 0; font-size:0.75rem; font-family:'JetBrains Mono',monospace; line-height:1.6; }
      .dark .answer-body .md-code { background:#060C1A; border-color:rgba(99,102,241,.22); color:#e2e8f0; }
      .answer-body .md-inline-code { background:var(--code-bg); color:var(--code-color); padding:0.1rem 0.35rem; border:1px solid var(--code-border); border-radius:0.25rem; font-size:0.8125rem; font-family:'JetBrains Mono',monospace; }
      .answer-body strong { color:var(--text-primary); }
    `}</style>
  );
}
