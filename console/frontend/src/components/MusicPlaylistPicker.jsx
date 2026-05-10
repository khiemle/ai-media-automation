import { useState, useEffect, useMemo, useRef } from 'react';
import { Card } from './index.jsx';
import { musicApi } from '../api/client.js';

function fmt(s) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return h ? `${h}h ${m}m` : `${m}m ${sec}s`;
}

export function MusicPlaylistPicker({ value, onChange, transition, transitionSeconds }) {
  const [available, setAvailable] = useState([]);
  const dragIdx = useRef(null);

  useEffect(() => {
    let cancelled = false;
    musicApi.list({ limit: 500 })
      .then(data => {
        if (!cancelled) setAvailable(data.items ?? data ?? []);
      })
      .catch(() => {
        if (!cancelled) setAvailable([]);
      });
    return () => { cancelled = true; };
  }, []);

  const selectedTracks = useMemo(
    () => value.map(id => available.find(t => t.id === id)).filter(Boolean),
    [value, available],
  );

  const totalSeconds = useMemo(() => {
    if (!selectedTracks.length) return 0;
    const sum = selectedTracks.reduce((acc, t) => acc + (t.duration_s || 0), 0);
    if (transition === 'crossfade') return sum - transitionSeconds * (selectedTracks.length - 1);
    if (transition === 'gap')       return sum + transitionSeconds * (selectedTracks.length - 1);
    return sum;
  }, [selectedTracks, transition, transitionSeconds]);

  const handleDragStart = (e, idx) => {
    dragIdx.current = idx;
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDrop = (e, toIdx) => {
    e.preventDefault();
    const fromIdx = dragIdx.current;
    if (fromIdx === null || fromIdx === toIdx) return;
    const next = [...value];
    const [moved] = next.splice(fromIdx, 1);
    next.splice(toIdx, 0, moved);
    onChange(next);
    dragIdx.current = null;
  };

  const remove = (id) => onChange(value.filter(v => v !== id));

  const add = (id) => {
    const numId = parseInt(id, 10);
    if (!value.includes(numId)) onChange([...value, numId]);
  };

  const unselected = available.filter(t => !value.includes(t.id));

  return (
    <Card title="Music Playlist">
      {selectedTracks.length === 0 ? (
        <p className="text-sm text-[#5a5a70] mb-2">No tracks selected. Add tracks below.</p>
      ) : (
        <ul className="space-y-1 mb-2">
          {selectedTracks.map((t, i) => (
            <li
              key={t.id}
              draggable
              onDragStart={e => handleDragStart(e, i)}
              onDragOver={e => e.preventDefault()}
              onDrop={e => handleDrop(e, i)}
              className="flex items-center gap-2 px-2 py-1.5 bg-[#16161a] border border-[#2a2a32] rounded-lg select-none"
            >
              <span
                className="text-[#5a5a70] cursor-grab active:cursor-grabbing text-sm leading-none"
                title="Drag to reorder"
              >
                ⋮⋮
              </span>
              <span className="flex-1 truncate text-sm text-[#e8e8f0]">{t.title}</span>
              <span className="text-xs text-[#9090a8] font-mono shrink-0">
                {fmt(t.duration_s ?? 0)}
              </span>
              <button
                onClick={() => remove(t.id)}
                className="text-[#f87171] hover:text-red-400 text-xs leading-none px-1"
                title="Remove"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      <select
        onChange={e => { if (e.target.value) { add(e.target.value); e.target.value = ''; } }}
        defaultValue=""
        disabled={unselected.length === 0}
        className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] w-full focus:outline-none focus:border-[#7c6af7] disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <option value="" disabled>
          {unselected.length === 0 ? 'All tracks added' : 'Add track…'}
        </option>
        {unselected.map(t => (
          <option key={t.id} value={t.id}>
            {t.title} ({fmt(t.duration_s ?? 0)})
          </option>
        ))}
      </select>

      <div className="mt-3 text-sm text-[#9090a8] border-t border-[#2a2a32] pt-3">
        Total:{' '}
        <span className="text-[#e8e8f0] font-medium">{fmt(Math.max(0, totalSeconds))}</span>
        {' · '}
        {value.length} {value.length === 1 ? 'track' : 'tracks'}
      </div>
    </Card>
  );
}
