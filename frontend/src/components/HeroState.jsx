// src/components/HeroState.jsx
// Centered empty-state workspace — fully theme-aware

import React from 'react';
import { Sparkles, Database, Boxes, Activity, Sliders } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

const QUICK = [
  {
    Icon: Database, color: '#ef4444', darkColor: '#f87171',
    bg: '#fef2f2', darkBg: 'rgba(239,68,68,0.12)',
    border: '#fecaca', darkBorder: 'rgba(239,68,68,0.25)',
    tag: 'P1', tagColor: '#ef4444',
    title: '[P1 Alert] Postgres Pool Timeout',
    sub: 'Diagnose PgBouncer queue latency & transaction locks',
    query: 'Triage P1 PostgreSQL Connection Timeout on us-east-1 DB cluster',
  },
  {
    Icon: Boxes, color: '#f59e0b', darkColor: '#fbbf24',
    bg: '#fffbeb', darkBg: 'rgba(245,158,11,0.12)',
    border: '#fde68a', darkBorder: 'rgba(245,158,11,0.25)',
    tag: 'P2', tagColor: '#f59e0b',
    title: '[P2] K8s Pod CrashLoopBackOff',
    sub: 'Analyze pod OOMKilled events and recent commit diffs',
    query: 'Investigate Kubernetes CrashLoopBackOff in payment-gateway service',
  },
  {
    Icon: Activity, color: '#0ea5e9', darkColor: '#38bdf8',
    bg: '#eff6ff', darkBg: 'rgba(14,165,233,0.12)',
    border: '#bfdbfe', darkBorder: 'rgba(14,165,233,0.25)',
    tag: 'SENTRY', tagColor: '#0ea5e9',
    title: 'Synthesize Stripe 502 Outage',
    sub: 'Correlate TLS handshake errors with cert rotations',
    query: 'Summarize Stripe Webhook 502 Bad Gateway failures from Sentry logs',
  },
  {
    Icon: Sliders, color: '#8b5cf6', darkColor: '#a78bfa',
    bg: '#f5f3ff', darkBg: 'rgba(139,92,246,0.12)',
    border: '#ddd6fe', darkBorder: 'rgba(139,92,246,0.25)',
    tag: 'PLAYBOOK', tagColor: '#8b5cf6',
    title: 'Auto-Scale Kafka Consumers',
    sub: 'Simulate consumer replica expansion & partition rebalance',
    query: 'Run dry-run auto-remediation on Kafka topic lag anomaly',
  },
];

export default function HeroState({ onQuickPrompt }) {
  const { isDark } = useTheme();
  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '2rem 1.5rem', maxWidth: '720px', margin: '0 auto', width: '100%', textAlign: 'center',
    }}>
      {/* Badge */}
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: '.5rem',
        padding: '.375rem .875rem', borderRadius: '9999px',
        background: isDark ? 'rgba(99,102,241,0.14)' : 'rgba(238,242,255,.8)',
        border: isDark ? '1px solid rgba(99,102,241,0.28)' : '1px solid rgba(199,210,254,.6)',
        color: isDark ? '#a5b4fc' : '#4338ca',
        fontSize: '.75rem', fontWeight: 500,
        backdropFilter: 'blur(8px)', marginBottom: '1.5rem',
      }}>
        <Sparkles size={14} className="spin-slow" style={{ color: isDark ? '#818cf8' : '#6366f1' }} />
        <span>Autonomous Ticket Triaging Engine v3.4</span>
      </div>

      {/* Headline */}
      <h2 style={{ fontSize: '2.75rem', fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1.15, marginBottom: '.75rem', letterSpacing: '-.02em' }}>
        Hi, Engineer.
      </h2>
      <p style={{ fontSize: '1.125rem', color: 'var(--text-secondary)', fontWeight: 400, marginBottom: '2.25rem', maxWidth: '440px', lineHeight: 1.6 }}>
        Ready whenever you are. Describe an anomaly, paste a stack trace, or select an active alert below.
      </p>

      {/* Quick prompts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '.75rem', width: '100%', textAlign: 'left' }}>
        {QUICK.map((q, i) => (
          <QuickCard key={i} q={q} onClick={() => onQuickPrompt(q.query)} isDark={isDark} />
        ))}
      </div>
    </div>
  );
}

function QuickCard({ q, onClick, isDark }) {
  const { Icon } = q;
  return (
    <button
      onClick={onClick}
      className="glass-card"
      style={{
        padding: '.875rem', borderRadius: '1rem', cursor: 'pointer',
        display: 'flex', alignItems: 'flex-start', gap: '.75rem',
        textAlign: 'left', width: '100%',
      }}
    >
      <div style={{
        padding: '.5rem', borderRadius: '.75rem', flexShrink: 0,
        background: isDark ? q.darkBg : q.bg,
        border: `1px solid ${isDark ? q.darkBorder : q.border}`,
        color: isDark ? q.darkColor : q.color,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon size={18} strokeWidth={2} />
      </div>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '.4rem', marginBottom: '.25rem' }}>
          <span style={{ fontSize: '.75rem', fontWeight: 600, color: 'var(--text-primary)' }}>{q.title}</span>
          <span style={{
            fontSize: '.6rem', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700,
            color: isDark ? q.darkColor : q.tagColor,
            padding: '.1rem .3rem', borderRadius: '3px',
            background: isDark ? q.darkBg : q.bg,
          }}>{q.tag}</span>
        </div>
        <div style={{ fontSize: '.6875rem', color: 'var(--text-secondary)' }}>{q.sub}</div>
      </div>
    </button>
  );
}
