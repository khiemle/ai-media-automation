import { Card } from './index.jsx';

const STYLES = [
  { key: null,         label: 'None',       desc: 'No overlay' },
  { key: 'chip',       label: 'Chip',       desc: 'Compact bottom-left pill' },
  { key: 'sidebar',    label: 'Sidebar',    desc: 'Right-side playlist column' },
  { key: 'bottom_bar', label: 'Bottom bar', desc: 'Bottom-center bar with track + duration' },
];

export function OverlayStylePicker({ value, onChange, trackCount }) {
  const disabled = trackCount < 2;

  return (
    <Card title="Now-Playing Overlay">
      {disabled && (
        <p className="text-xs text-[#9090a8] mb-3 px-1">
          Single track — overlay hidden automatically
        </p>
      )}
      <div className="grid grid-cols-2 gap-2">
        {STYLES.map(s => (
          <label
            key={s.key ?? 'none'}
            className={`flex items-start gap-2 px-2 py-2 rounded-lg transition-colors
              ${disabled
                ? 'opacity-50 pointer-events-none'
                : 'cursor-pointer hover:bg-[#16161a]'
              }
              ${!disabled && value === s.key ? 'bg-[#16161a] border border-[#2a2a32]' : ''}
            `}
          >
            <input
              type="radio"
              name="overlay_style"
              checked={value === s.key}
              onChange={() => onChange(s.key)}
              disabled={disabled}
              className="mt-0.5 accent-[#7c6af7]"
            />
            <div>
              <div className="text-sm text-[#e8e8f0] font-medium">{s.label}</div>
              <div className="text-xs text-[#9090a8]">{s.desc}</div>
            </div>
          </label>
        ))}
      </div>
    </Card>
  );
}
