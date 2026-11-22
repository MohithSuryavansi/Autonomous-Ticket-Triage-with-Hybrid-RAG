// src/components/AmbientBackground.jsx
// Animated ambient blobs and dot-grid — adapts colours per theme

import { useTheme } from '../context/ThemeContext';

export default function AmbientBackground() {
  const { isDark } = useTheme();

  return (
    <div className="ambient-bg">
      {/* Blob 1 — top left */}
      <div
        className="blob"
        style={{
          top: '-8rem', left: '-8rem',
          width: '600px', height: '600px',
          background: isDark
            ? 'radial-gradient(circle, rgba(99,102,241,0.05) 0%, transparent 70%)'
            : 'radial-gradient(circle, rgba(147,197,253,.45) 0%, transparent 70%)',
          '--blur': '140px', '--dur': '14s', '--delay': '0s',
        }}
      />
      {/* Blob 2 — top right */}
      <div
        className="blob"
        style={{
          top: '-5rem', right: '-5rem',
          width: '650px', height: '650px',
          background: isDark
            ? 'radial-gradient(circle, rgba(139,92,246,0.04) 0%, transparent 70%)'
            : 'radial-gradient(circle, rgba(196,181,253,.4) 0%, transparent 70%)',
          '--blur': '150px', '--dur': '16s', '--delay': '-3s',
        }}
      />
      {/* Blob 3 — bottom centre */}
      <div
        className="blob"
        style={{
          bottom: '-10rem', left: '30%',
          width: '700px', height: '500px',
          background: isDark
            ? 'radial-gradient(circle, rgba(56,189,248,0.03) 0%, transparent 70%)'
            : 'radial-gradient(circle, rgba(186,230,253,.35) 0%, transparent 70%)',
          '--blur': '160px', '--dur': '18s', '--delay': '-6s',
        }}
      />
      {/* Subtle dot-grid */}
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: isDark
          ? 'linear-gradient(to right,rgba(255,255,255,0.015) 1px,transparent 1px),linear-gradient(to bottom,rgba(255,255,255,0.015) 1px,transparent 1px)'
          : 'linear-gradient(to right,#e2e8f00f 1px,transparent 1px),linear-gradient(to bottom,#e2e8f00f 1px,transparent 1px)',
        backgroundSize: '4rem 4rem',
      }} />
    </div>
  );
}

