// src/api.js
// All HTTP calls to the FastAPI backend (port 5000)

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000';

export async function searchIncidents(query, top_n = 8) {
  const res = await fetch(`${BASE}/api/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_n }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchHistory(limit = 30) {
  const res = await fetch(`${BASE}/api/history?limit=${limit}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchHistoryById(id) {
  const res = await fetch(`${BASE}/api/history/${id}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function deleteHistoryById(id) {
  const res = await fetch(`${BASE}/api/history/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

