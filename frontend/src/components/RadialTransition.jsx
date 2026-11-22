// src/components/RadialTransition.jsx
// Full-viewport overlay that performs the circular clip-path expansion animation
// when switching between light and dark mode.

import { useEffect, useRef } from 'react';
import { useTheme } from '../context/ThemeContext';

export default function RadialTransition() {
  const { transitioning, clipOrigin, pendingDark, onTransitionEnd } = useTheme();
  const overlayRef = useRef(null);

  useEffect(() => {
    if (!transitioning) return;

    const el = overlayRef.current;
    if (!el) return;

    // Compute max radius from origin to the furthest corner of the viewport
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const ox = parseFloat(clipOrigin.x);
    const oy = parseFloat(clipOrigin.y);
    const maxR = Math.hypot(
      Math.max(ox, vw - ox),
      Math.max(oy, vh - oy)
    ) + 10; // slight overshoot

    // Set CSS vars for the animation
    el.style.setProperty('--ox', clipOrigin.x);
    el.style.setProperty('--oy', clipOrigin.y);
    el.style.setProperty('--max-r', `${maxR}px`);

    // Force reflow then kick off animation
    el.getBoundingClientRect();
    el.classList.add('radial-active');

    const handler = () => {
      el.classList.remove('radial-active');
      onTransitionEnd();
    };
    el.addEventListener('animationend', handler, { once: true });
    return () => el.removeEventListener('animationend', handler);
  }, [transitioning, clipOrigin, onTransitionEnd]);

  if (!transitioning) return null;

  return (
    <div
      ref={overlayRef}
      className={`radial-overlay ${pendingDark ? 'radial-dark' : 'radial-light'}`}
      aria-hidden="true"
    />
  );
}
