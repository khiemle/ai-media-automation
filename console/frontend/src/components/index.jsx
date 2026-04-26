// ─── Card ─────────────────────────────────────────────────────────────────────
export function Card({ title, actions, children, className = '' }) {
  return (
    <div className={`bg-[#1c1c22] border border-[#2a2a32] rounded-xl overflow-hidden ${className}`}>
      {(title || actions) && (
        <div className="flex items-center justify-between px-5 py-3 border-b border-[#2a2a32]">
          {title && <span className="text-sm font-semibold text-[#e8e8f0] tracking-wide">{title}</span>}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  )
}

// ─── Badge ────────────────────────────────────────────────────────────────────
const BADGE_STYLES = {
  draft:          'bg-[#1e1e2e] text-[#9090a8] border border-[#2a2a42]',
  pending_review: 'bg-[#1e1a00] text-[#fbbf24] border border-[#3a3000]',
  approved:       'bg-[#001e12] text-[#34d399] border border-[#003020]',
  rejected:       'bg-[#1e0a0a] text-[#f87171] border border-[#3a1010]',
  editing:        'bg-[#001624] text-[#4a9eff] border border-[#002840]',
  producing:      'bg-[#1a0e2e] text-[#7c6af7] border border-[#2a1a50]',
  completed:      'bg-[#0a1e14] text-[#34d399] border border-[#103020]',
  active:         'bg-[#001e12] text-[#34d399] border border-[#003020]',
  standby:        'bg-[#1e1a00] text-[#fbbf24] border border-[#3a3000]',
  planned:        'bg-[#1e1e2e] text-[#9090a8] border border-[#2a2a42]',
  connected:      'bg-[#001e12] text-[#34d399] border border-[#003020]',
  expired:        'bg-[#1e0a0a] text-[#f87171] border border-[#3a1010]',
  disconnected:   'bg-[#1e1e2e] text-[#9090a8] border border-[#2a2a42]',
  youtube:        'bg-[#1e0808] text-[#ff6060] border border-[#3a1010]',
  tiktok:         'bg-[#001624] text-[#22d3ee] border border-[#002840]',
  instagram:      'bg-[#1a0820] text-[#c084fc] border border-[#2a1040]',
}

export function Badge({ status, label, className = '' }) {
  const style = BADGE_STYLES[status] || 'bg-[#1e1e2e] text-[#9090a8] border border-[#2a2a42]'
  const text = label ?? status?.replace(/_/g, ' ')
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium ${style} ${className}`}>
      {text}
    </span>
  )
}

// ─── Button ───────────────────────────────────────────────────────────────────
const BUTTON_STYLES = {
  default: 'bg-[#222228] hover:bg-[#2a2a32] text-[#e8e8f0] border border-[#2a2a32]',
  primary: 'bg-[#7c6af7] hover:bg-[#6a58e5] text-white border border-transparent',
  danger:  'bg-[#3a1010] hover:bg-[#501515] text-[#f87171] border border-[#5a1515]',
  success: 'bg-[#003020] hover:bg-[#004030] text-[#34d399] border border-[#004535]',
  ghost:   'bg-transparent hover:bg-[#222228] text-[#9090a8] border border-transparent',
  accent:  'bg-[#001624] hover:bg-[#002030] text-[#4a9eff] border border-[#002840]',
}

const BUTTON_SIZES = {
  sm: 'px-2.5 py-1 text-xs',
  md: 'px-3.5 py-1.5 text-sm',
  lg: 'px-5 py-2 text-sm',
}

export function Button({ variant = 'default', size = 'md', disabled, loading, onClick, children, className = '', type = 'button', ...rest }) {
  const style = BUTTON_STYLES[variant] || BUTTON_STYLES.default
  const sz = BUTTON_SIZES[size] || BUTTON_SIZES.md
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`inline-flex items-center gap-1.5 rounded-lg font-medium transition-colors ${style} ${sz} disabled:opacity-40 disabled:cursor-not-allowed ${className}`}
      {...rest}
    >
      {loading && (
        <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
      )}
      {children}
    </button>
  )
}

// ─── Input ────────────────────────────────────────────────────────────────────
export function Input({ label, value, onChange, placeholder, type = 'text', className = '', ...rest }) {
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      {label && <label className="text-xs text-[#9090a8] font-medium">{label}</label>}
      <input
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] transition-colors"
        {...rest}
      />
    </div>
  )
}

// ─── Textarea ─────────────────────────────────────────────────────────────────
export function Textarea({ label, value, onChange, placeholder, rows = 3, className = '' }) {
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      {label && <label className="text-xs text-[#9090a8] font-medium">{label}</label>}
      <textarea
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        rows={rows}
        className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] resize-y transition-colors"
      />
    </div>
  )
}

// ─── Select ───────────────────────────────────────────────────────────────────
export function Select({ label, value, onChange, options = [], placeholder, className = '', children }) {
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      {label && <label className="text-xs text-[#9090a8] font-medium">{label}</label>}
      <select
        value={value}
        onChange={onChange}
        className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors appearance-none cursor-pointer"
      >
        {placeholder && <option value="">{placeholder}</option>}
        {children
          ? children
          : options.map(o => (
              <option key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</option>
            ))
        }
      </select>
    </div>
  )
}

// ─── Modal ────────────────────────────────────────────────────────────────────
export function Modal({ open, onClose, title, children, footer, width = 'max-w-2xl' }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className={`relative z-10 w-full ${width} mx-4 bg-[#1c1c22] border border-[#2a2a32] rounded-2xl shadow-2xl flex flex-col max-h-[90vh]`}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#2a2a32] flex-shrink-0">
          <span className="font-semibold text-[#e8e8f0]">{title}</span>
          <button onClick={onClose} className="text-[#9090a8] hover:text-[#e8e8f0] transition-colors p-1 rounded">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M3.293 3.293a1 1 0 011.414 0L8 6.586l3.293-3.293a1 1 0 111.414 1.414L9.414 8l3.293 3.293a1 1 0 01-1.414 1.414L8 9.414l-3.293 3.293a1 1 0 01-1.414-1.414L6.586 8 3.293 4.707a1 1 0 010-1.414z" />
            </svg>
          </button>
        </div>
        {/* Body */}
        <div className="overflow-y-auto flex-1 px-6 py-5">{children}</div>
        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-[#2a2a32] flex-shrink-0">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── StatBox ──────────────────────────────────────────────────────────────────
export function StatBox({ label, value, sub, accent = false }) {
  return (
    <div className="bg-[#16161a] border border-[#2a2a32] rounded-xl px-4 py-3 flex flex-col gap-0.5 min-w-[110px]">
      <span className="text-xs text-[#9090a8] font-medium uppercase tracking-wider">{label}</span>
      <span className={`text-2xl font-bold font-mono ${accent ? 'text-[#7c6af7]' : 'text-[#e8e8f0]'}`}>{value ?? '—'}</span>
      {sub && <span className="text-xs text-[#5a5a70]">{sub}</span>}
    </div>
  )
}

// ─── ProgressBar ──────────────────────────────────────────────────────────────
export function ProgressBar({ value = 0, max = 100, color = '#7c6af7', label }) {
  const pct = Math.min(100, Math.round((value / max) * 100))
  return (
    <div className="flex flex-col gap-1">
      {label && <div className="flex justify-between text-xs text-[#9090a8]"><span>{label}</span><span>{pct}%</span></div>}
      <div className="h-1.5 bg-[#2a2a32] rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-300" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  )
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────
export function Tabs({ tabs = [], active, onChange }) {
  return (
    <div className="flex gap-1 border-b border-[#2a2a32]">
      {tabs.map(t => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
            active === t.id
              ? 'border-[#7c6af7] text-[#7c6af7]'
              : 'border-transparent text-[#9090a8] hover:text-[#e8e8f0]'
          }`}
        >
          {t.label}
          {t.count !== undefined && (
            <span className="ml-1.5 text-xs bg-[#2a2a32] px-1.5 py-0.5 rounded-full">{t.count}</span>
          )}
        </button>
      ))}
    </div>
  )
}

// ─── Toast ────────────────────────────────────────────────────────────────────
export function Toast({ message, type = 'success', onClose }) {
  const colors = {
    success: 'bg-[#001e12] border-[#003020] text-[#34d399]',
    error:   'bg-[#1e0a0a] border-[#3a1010] text-[#f87171]',
    info:    'bg-[#001624] border-[#002840] text-[#4a9eff]',
  }
  return (
    <div className={`fixed bottom-5 right-5 z-[100] flex items-center gap-3 px-4 py-3 rounded-xl border shadow-xl text-sm font-medium ${colors[type] || colors.info}`}>
      {message}
      <button onClick={onClose} className="opacity-60 hover:opacity-100 ml-2">✕</button>
    </div>
  )
}

// ─── Spinner ─────────────────────────────────────────────────────────────────
export function Spinner({ size = 20 }) {
  return (
    <svg className="animate-spin text-[#7c6af7]" style={{ width: size, height: size }} viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
    </svg>
  )
}

export { default as NicheCombobox } from './NicheCombobox.jsx'
// ─── EmptyState ───────────────────────────────────────────────────────────────
export function EmptyState({ icon = '📭', title, description }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
      <span className="text-4xl">{icon}</span>
      <p className="text-[#e8e8f0] font-medium">{title}</p>
      {description && <p className="text-sm text-[#9090a8] max-w-sm">{description}</p>}
    </div>
  )
}
