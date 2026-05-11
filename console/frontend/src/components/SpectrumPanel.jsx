import { useState } from 'react';
import { Card } from './index.jsx';

export function SpectrumPanel({ value, onChange }) {
  const [open, setOpen] = useState(Boolean(value.spectrum_enabled));

  const update = (patch) => onChange({ ...value, ...patch });

  const handleToggle = (e) => {
    const enabled = e.target.checked;
    update({ spectrum_enabled: enabled });
    setOpen(enabled);
  };

  return (
    <Card title="Audio Spectrum (optional)">
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={Boolean(value.spectrum_enabled)}
          onChange={handleToggle}
          className="accent-[#7c6af7] w-4 h-4"
        />
        <span className="text-sm text-[#e8e8f0]">Enable spectrum visualizer</span>
      </label>

      {open && (
        <div className="mt-4 space-y-4 pl-6 border-l border-[#2a2a32]">
          {/* Style */}
          <div>
            <label className="block text-xs text-[#9090a8] mb-1.5">Style</label>
            <select
              value={value.spectrum_style ?? 'classic'}
              onChange={e => update({ spectrum_style: e.target.value })}
              className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]"
            >
              <option value="classic">Classic (showfreqs)</option>
              <option value="bars">Bars (50, rounded)</option>
            </select>
          </div>

          {/* Position */}
          <div>
            <label className="block text-xs text-[#9090a8] mb-1.5">Position</label>
            <select
              value={value.spectrum_position ?? 'bottom'}
              onChange={e => update({ spectrum_position: e.target.value })}
              className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]"
            >
              <option value="bottom">Bottom</option>
              <option value="center">Center</option>
            </select>
          </div>

          {/* Height */}
          <div>
            <label className="block text-xs text-[#9090a8] mb-1.5">
              Height:{' '}
              <span className="text-[#e8e8f0] font-mono">
                {Math.round((value.spectrum_height_pct ?? 0.12) * 100)}%
              </span>
            </label>
            <input
              type="range"
              min={0.05}
              max={0.50}
              step={0.01}
              value={value.spectrum_height_pct ?? 0.12}
              onChange={e => update({ spectrum_height_pct: parseFloat(e.target.value) })}
              className="w-full accent-[#7c6af7]"
            />
          </div>

          {/* Color */}
          <div>
            <label className="block text-xs text-[#9090a8] mb-1.5">Color</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={value.spectrum_color ?? '#7c6af7'}
                onChange={e => update({ spectrum_color: e.target.value })}
                className="w-8 h-8 rounded cursor-pointer border border-[#2a2a32] bg-transparent"
              />
              <span className="text-xs text-[#9090a8] font-mono">
                {value.spectrum_color ?? '#7c6af7'}
              </span>
            </div>
          </div>

          {/* Opacity */}
          <div>
            <label className="block text-xs text-[#9090a8] mb-1.5">
              Opacity:{' '}
              <span className="text-[#e8e8f0] font-mono">
                {(value.spectrum_opacity ?? 0.8).toFixed(2)}
              </span>
            </label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={value.spectrum_opacity ?? 0.8}
              onChange={e => update({ spectrum_opacity: parseFloat(e.target.value) })}
              className="w-full accent-[#7c6af7]"
            />
          </div>
        </div>
      )}
    </Card>
  );
}
