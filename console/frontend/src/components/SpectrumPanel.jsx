import { useState } from 'react';
import { Card } from './index.jsx';

// Default landscape canvas — used to compute the over-width warning client-side.
// The render pipeline always uses 1920 for landscape_long; if a future template
// supports a different width, plumb it through as a prop.
const CANVAS_W = 1920;

export function SpectrumPanel({ value, onChange }) {
  const [open, setOpen] = useState(Boolean(value.spectrum_enabled));

  const update = (patch) => onChange({ ...value, ...patch });

  const handleToggle = (e) => {
    const enabled = e.target.checked;
    update({ spectrum_enabled: enabled });
    setOpen(enabled);
  };

  const style = value.spectrum_style ?? 'classic';
  const isBars = style === 'bars';

  // Bars-only knobs
  const barWidth = Math.round(value.spectrum_bar_width_px ?? 10);
  const barCount = Math.round(value.spectrum_bar_count ?? 50);
  const barGap = 2; // matches renderer default
  const barsBlockWidth = barCount * barWidth + (barCount - 1) * barGap;
  const overCanvas = barsBlockWidth > CANVAS_W;

  const alignH = value.spectrum_align_horizontal ?? 'center';
  const alignV = value.spectrum_align_vertical ?? 'bottom';

  // 3×3 grid: rows top→bottom, cols left→center→right
  const gridRows = ['top', 'center', 'bottom'];
  const gridCols = ['left', 'center', 'right'];

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
              value={style}
              onChange={e => update({ spectrum_style: e.target.value })}
              className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]"
            >
              <option value="classic">Classic (showfreqs)</option>
              <option value="bars">Bars (rounded)</option>
            </select>
          </div>

          {/* Bars-only knobs */}
          {isBars && (
            <>
              <div>
                <label className="block text-xs text-[#9090a8] mb-1.5">
                  Bar count:{' '}
                  <span className="text-[#e8e8f0] font-mono">{barCount}</span>
                </label>
                <input
                  type="range"
                  min={5}
                  max={200}
                  step={1}
                  value={barCount}
                  onChange={e => update({ spectrum_bar_count: parseInt(e.target.value, 10) })}
                  className="w-full accent-[#7c6af7]"
                />
              </div>

              <div>
                <label className="block text-xs text-[#9090a8] mb-1.5">
                  Bar width:{' '}
                  <span className="text-[#e8e8f0] font-mono">{barWidth}px</span>
                </label>
                <input
                  type="range"
                  min={2}
                  max={50}
                  step={1}
                  value={barWidth}
                  onChange={e => update({ spectrum_bar_width_px: parseFloat(e.target.value) })}
                  className="w-full accent-[#7c6af7]"
                />
                <div className={`text-[11px] mt-1 font-mono ${overCanvas ? 'text-[#fbbf24]' : 'text-[#5a5a70]'}`}>
                  Block: {barsBlockWidth}px {overCanvas ? `> ${CANVAS_W}px canvas — rightmost bars will be clipped` : `(fits in ${CANVAS_W}px canvas)`}
                </div>
              </div>
            </>
          )}

          {/* Position — 3×3 grid */}
          <div>
            <label className="block text-xs text-[#9090a8] mb-1.5">Position</label>
            <div className="inline-grid grid-cols-3 gap-1 p-1 bg-[#16161a] border border-[#2a2a32] rounded-lg">
              {gridRows.map(row => gridCols.map(col => {
                const active = alignV === row && alignH === col;
                return (
                  <button
                    key={`${row}-${col}`}
                    type="button"
                    onClick={() => update({
                      spectrum_align_horizontal: col,
                      spectrum_align_vertical: row,
                    })}
                    title={`${row} ${col}`}
                    className={`w-8 h-8 rounded text-xs flex items-center justify-center transition-colors
                                ${active
                                  ? 'bg-[#7c6af7] text-white'
                                  : 'bg-[#1c1c22] text-[#9090a8] hover:bg-[#2a2a32]'}`}
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-current" />
                  </button>
                );
              }))}
            </div>
            <div className="text-[11px] mt-1 text-[#5a5a70] font-mono">
              {alignV} {alignH}
            </div>
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
