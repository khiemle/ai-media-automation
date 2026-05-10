import { Card } from './index.jsx';

const MODES = [
  { key: 'gapless',   label: 'Gapless',   desc: 'Tracks play back-to-back with no gap' },
  { key: 'crossfade', label: 'Crossfade', desc: 'Tracks fade into each other' },
  { key: 'gap',       label: 'Gap',       desc: 'Brief silence between tracks' },
];

export function TransitionPanel({ transition, transitionSeconds, onChange }) {
  const showSeconds = transition === 'crossfade' || transition === 'gap';

  return (
    <Card title="Track Transition">
      <div className="space-y-1">
        {MODES.map(m => (
          <label
            key={m.key}
            className="flex items-start gap-3 px-2 py-2 rounded-lg cursor-pointer hover:bg-[#16161a] transition-colors"
          >
            <input
              type="radio"
              name="transition"
              value={m.key}
              checked={transition === m.key}
              onChange={() => onChange({ transition: m.key, transitionSeconds })}
              className="mt-0.5 accent-[#7c6af7]"
            />
            <div>
              <div className="text-sm text-[#e8e8f0] font-medium">{m.label}</div>
              <div className="text-xs text-[#9090a8]">{m.desc}</div>
            </div>
          </label>
        ))}
      </div>

      {showSeconds && (
        <div className="mt-3 pl-2">
          <label className="block text-xs text-[#9090a8] mb-1">
            {transition === 'crossfade' ? 'Crossfade' : 'Gap'} duration (seconds)
          </label>
          <input
            type="number"
            min={0.5}
            max={10}
            step={0.5}
            value={transitionSeconds}
            onChange={e => onChange({ transition, transitionSeconds: parseFloat(e.target.value) || 0.5 })}
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] w-24 focus:outline-none focus:border-[#7c6af7]"
          />
        </div>
      )}
    </Card>
  );
}
