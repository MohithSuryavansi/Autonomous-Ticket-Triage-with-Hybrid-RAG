// src/components/ProjectLogo.jsx
// Hexagonal Neural Agent Mesh Badge with Aether Gradient & Central AI Hub Sparkle

import React from 'react';

export default function ProjectLogo({ size = 44, className = '', style = {} }) {
  const gradId = "aetherGrad7";

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{ display: 'block', flexShrink: 0, ...style }}
    >
      <defs>
        <linearGradient id={gradId} x1="10" y1="10" x2="90" y2="90" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#3B82F6" />
          <stop offset="50%" stopColor="#6366F1" />
          <stop offset="100%" stopColor="#8B5CF6" />
        </linearGradient>
      </defs>
      {/* Outer Hexagonal Constellation Boundary */}
      <polygon
        points="50,15 80,32 80,68 50,85 20,68 20,32"
        fill="rgba(17,24,39,0.88)"
        stroke={`url(#${gradId})`}
        strokeWidth="2.5"
        strokeDasharray="4 2"
      />
      {/* Interconnected Neural Agent Mesh */}
      <path
        d="M50 15L50 50M80 32L50 50M80 68L50 50M50 85L50 50M20 68L50 50M20 32L50 50"
        stroke={`url(#${gradId})`}
        strokeWidth="1.8"
      />
      {/* Secondary Sub-Triangles */}
      <polygon
        points="50,28 68,38 68,62 50,72 32,62 32,38"
        fill="none"
        stroke="#38BDF8"
        strokeWidth="1.6"
      />
      {/* Neural Node Agent Satellites */}
      <circle cx="50" cy="15" r="3.5" fill="#3B82F6" />
      <circle cx="80" cy="32" r="3.5" fill="#6366F1" />
      <circle cx="80" cy="68" r="3.5" fill="#8B5CF6" />
      <circle cx="50" cy="85" r="3.5" fill="#3B82F6" />
      <circle cx="20" cy="68" r="3.5" fill="#6366F1" />
      <circle cx="20" cy="32" r="3.5" fill="#8B5CF6" />
      {/* Central AI Hub Sparkle */}
      <circle cx="50" cy="50" r="7" fill={`url(#${gradId})`} />
      <path d="M50 43L51.5 48.5L57 50L51.5 51.5L50 57L48.5 51.5L43 50L48.5 48.5L50 43Z" fill="#FFFFFF" />
    </svg>
  );
}
