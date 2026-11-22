// src/components/DossierPanel.jsx
// Right panel: Incident Dossier — fully theme-aware via CSS vars

import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { FileSearch, X, BrainCircuit, Clock, Layers } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

export default function DossierPanel({ response, onClose }) {
  const [selectedIncident, setSelectedIncident] = useState(null);
  const { isDark } = useTheme();
  if (!response) return null;

  const top = response.incidents?.[0];
  const score = top ? Math.round(top.rerank_score * 100) : 0;

  return (
    <aside className="glass-sidebar" style={{
      width: '360px', flexShrink: 0, display: 'flex', flexDirection: 'column',
      height: '100%',
      borderLeft: `1px solid var(--border-sidebar)`,
      zIndex: 20,
    }}>
      {/* Header */}
      <div style={{
        padding: '1rem', borderBottom: `1px solid var(--border-sidebar)`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: isDark ? 'rgba(8,13,26,0.4)' : 'rgba(255,255,255,.4)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
          <FileSearch size={16} strokeWidth={2} style={{ color: 'var(--text-brand)' }} />
          <span style={{ fontWeight: 600, fontSize: '.6875rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '.07em' }}>
            Incident Dossier
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
          <span style={{
            padding: '.125rem .5rem', borderRadius: '9999px',
            fontSize: '.625rem', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700,
            background: isDark ? 'rgba(239,68,68,0.14)' : '#fef2f2',
            color: isDark ? '#f87171' : '#dc2626',
            border: `1px solid ${isDark ? 'rgba(239,68,68,0.28)' : '#fecaca'}`,
          }}>INVESTIGATING</span>
          <button
            onClick={onClose}
            style={{ padding: '.25rem', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }}
          >
            <X size={16} strokeWidth={2} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

        {/* Root Cause Certainty */}
        {top && (
          <div style={{ background: 'var(--bg-inset)', padding: '.625rem .75rem', borderRadius: '.75rem', border: `1px solid var(--border-card)` }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '.75rem', fontWeight: 600, marginBottom: '.375rem' }}>
              <span style={{ color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '.35rem' }}>
                <BrainCircuit size={14} strokeWidth={2} style={{ color: 'var(--text-brand)' }} />
                <span>Root Cause Certainty</span>
              </span>
              <span style={{ color: 'var(--text-brand)', fontFamily: 'JetBrains Mono, monospace' }}>{score}%</span>
            </div>
            <div style={{ height: '6px', background: 'var(--border-divider)', borderRadius: '999px', overflow: 'hidden' }}>
              <div style={{
                height: '100%', borderRadius: '999px',
                background: 'linear-gradient(90deg, #6366f1, #06b6d4)',
                width: `${score}%`, transition: 'width 1s ease',
              }} />
            </div>
          </div>
        )}

        {/* Retrieved Incidents list */}
        {response.incidents?.length > 0 && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '.5rem' }}>
              <SectionTitle>Retrieved Incidents</SectionTitle>
              <div style={{ fontSize: '.625rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace', textAlign: 'right' }}>
                <div>{response.incidents.length} incidents</div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.2rem' }}>
                  <Clock size={10} strokeWidth={2} />
                  <span>{response.latency_ms}ms</span>
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '.375rem' }}>
              {response.incidents.map((inc, i) => (
                <div
                  key={inc.id}
                  onClick={() => setSelectedIncident(inc)}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '.5rem .75rem', borderRadius: '.75rem',
                    background: 'var(--bg-btn)',
                    border: `1px solid var(--border-card)`,
                    cursor: 'pointer',
                  }}
                  onMouseOver={e => e.currentTarget.style.background = 'var(--bg-btn-hover)'}
                  onMouseOut={e => e.currentTarget.style.background = 'var(--bg-btn)'}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
                    <span style={{
                      width: '1.25rem', height: '1.25rem', borderRadius: '50%',
                      background: isDark ? 'rgba(99,102,241,0.18)' : '#eef2ff',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: '.5625rem', color: 'var(--text-brand)', fontWeight: 700,
                      fontFamily: 'JetBrains Mono, monospace',
                    }}>{i + 1}</span>
                    <span style={{ fontSize: '.6875rem', color: 'var(--text-primary)', fontWeight: 500, maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {inc.short_description}
                    </span>
                  </div>
                  <span style={{ fontSize: '.5625rem', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, color: 'var(--text-link)' }}>
                    {Math.round(inc.rerank_score * 100)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Retrieval IDs metadata */}
        {(response.reranked_ids?.length > 0 || response.rrf_ids?.length > 0) && (
          <div style={{ background: 'var(--bg-inset)', padding: '.625rem .75rem', borderRadius: '.75rem', border: `1px solid var(--border-card)` }}>
            <SectionTitle style={{ marginBottom: '.5rem' }}>Retrieval Pipeline</SectionTitle>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '.375rem', fontSize: '.6125rem', fontFamily: 'JetBrains Mono, monospace' }}>
              {[
                { label: 'Dense (BGE)', ids: response.dense_ids },
                { label: 'Sparse (BM25)', ids: response.sparse_ids },
                { label: 'RRF Fused', ids: response.rrf_ids },
                { label: 'Reranked', ids: response.reranked_ids },
              ].map(({ label, ids }) => ids?.length > 0 && (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
                  <span style={{ color: 'var(--text-muted)', minWidth: '80px' }}>{label}</span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.2rem' }}>
                    {ids.slice(0, 5).map(id => (
                      <span key={id} style={{
                        padding: '.05rem .3rem', borderRadius: '3px',
                        background: isDark ? 'rgba(99,102,241,0.16)' : '#eef2ff',
                        color: 'var(--text-link)',
                        fontSize: '.5625rem',
                      }}>{id}</span>
                    ))}
                    {ids.length > 5 && <span style={{ color: 'var(--text-muted)', fontSize: '.5625rem' }}>+{ids.length - 5}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {selectedIncident && (
        <IncidentModal incident={selectedIncident} onClose={() => setSelectedIncident(null)} />
      )}
    </aside>
  );
}

function SectionTitle({ children, style }) {
  return (
    <div style={{ fontSize: '.625rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.08em', color: 'var(--text-muted)', marginBottom: '.5rem', ...style }}>
      {children}
    </div>
  );
}

function IncidentModal({ incident, onClose }) {
  return createPortal(
    <div style={{
      position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
      background: 'rgba(5,10,20,0.72)', zIndex: 99999, display: 'flex',
      alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(6px)',
    }}>
      <div className="glass-card" style={{
        background: 'var(--bg-panel)',
        backdropFilter: 'blur(24px)',
        borderRadius: '1rem', width: '90%', maxWidth: '800px',
        maxHeight: '90vh', overflowY: 'auto', padding: '1.5rem',
        boxShadow: '0 32px 64px -16px rgba(0,0,0,0.45)',
        border: `1px solid var(--border-panel)`,
        position: 'relative',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.25rem', color: 'var(--text-primary)', fontWeight: 700, lineHeight: 1.3 }}>
              {incident.short_description}
            </h2>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.375rem', fontFamily: 'JetBrains Mono, monospace' }}>
              {incident.id} · {incident.category}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'var(--bg-inset)', border: '1px solid var(--border-btn)',
            width: '2rem', height: '2rem', borderRadius: '50%',
            cursor: 'pointer', color: 'var(--text-secondary)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginLeft: '1rem', flexShrink: 0,
          }}>
            <X size={16} strokeWidth={2} />
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <InfoBlock label="Description" value={incident.description || 'No description provided.'} />
          <InfoBlock label="Resolution" value={incident.resolution || 'No resolution provided.'} accent />

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
            {[
              { label: 'Urgency', value: incident.urgency },
              { label: 'Impact', value: incident.impact },
              { label: 'Team', value: incident.assignment_group },
            ].map(({ label, value }) => (
              <InfoBlock key={label} label={label} value={value || '—'} compact />
            ))}
          </div>

          {(incident.keywords || incident.affected_component) && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              {incident.affected_component && <InfoBlock label="Component" value={incident.affected_component} compact />}
              {incident.keywords && <InfoBlock label="Keywords" value={incident.keywords} compact mono />}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}

function InfoBlock({ label, value, accent, compact, mono }) {
  return (
    <div style={{
      background: accent ? 'var(--bg-btn-hover)' : 'var(--bg-inset)',
      padding: compact ? '0.75rem' : '1rem',
      borderRadius: '0.75rem',
      border: accent ? '1px solid var(--border-strong)' : '1px solid var(--border-card)',
    }}>
      <div style={{ fontSize: '0.625rem', color: accent ? 'var(--text-brand)' : 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700, marginBottom: '0.375rem', letterSpacing: '0.05em' }}>
        {label}
      </div>
      <div style={{ fontSize: mono ? '0.75rem' : '0.875rem', fontWeight: compact ? 600 : 400, color: 'var(--text-primary)', lineHeight: 1.55, fontFamily: mono ? 'JetBrains Mono, monospace' : undefined }}>
        {value}
      </div>
    </div>
  );
}
