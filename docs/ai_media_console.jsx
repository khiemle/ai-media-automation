import { useState, useEffect, useCallback, useMemo, useRef } from "react";

// ═══════════════════════════════════════════════════════════════════════════════
// CONSTANTS & GENERATORS
// ═══════════════════════════════════════════════════════════════════════════════
const NICHES = ["finance", "health", "lifestyle", "fitness", "food", "productivity", "tech"];
const REGIONS = ["VN", "US", "TH", "ID", "PH"];
const TEMPLATES = ["tiktok_viral", "tiktok_30s", "youtube_clean", "shorts_hook"];
const LLM_MODES = ["local", "gemini", "auto", "hybrid"];
const ASSET_MODES = ["db_only", "db_then_pexels", "db_then_veo", "db_then_hybrid"];
const PLATFORMS = ["youtube", "tiktok", "instagram"];
const OVERLAY_STYLES = ["big_white_center", "bottom_caption", "top_title", "highlight_box", "minimal"];
const TRANSITION_TYPES = ["cut", "fade", "crossfade"];
const SCENE_TYPES = ["hook", "body", "transition", "cta"];
const MOODS = ["uplifting", "calm_focus", "energetic", "trust"];
const MUSIC_TRACKS = [
  "uplifting_120bpm_180s.mp3", "calm_focus_85bpm_240s.mp3", "energetic_140bpm_120s.mp3",
  "trust_95bpm_200s.mp3", "uplifting_110bpm_200s.mp3", "calm_focus_90bpm_300s.mp3",
];
const VOICES = ["af_heart", "am_bold", "af_gentle", "am_news"];
const SCRAPER_SOURCES = [
  { id: "tiktok_research", name: "TikTok Research API", type: "tiktok", status: "active", icon: "♪", color: "#e2e8f0" },
  { id: "tiktok_playwright", name: "TikTok Playwright", type: "tiktok", status: "standby", icon: "♪", color: "#94a3b8" },
  { id: "tiktok_apify", name: "TikTok Apify", type: "tiktok", status: "standby", icon: "♪", color: "#94a3b8" },
  { id: "youtube_trending", name: "YouTube Trending", type: "youtube", status: "planned", icon: "▶", color: "#ef4444" },
  { id: "news_vnexpress", name: "VnExpress News", type: "news", status: "planned", icon: "📰", color: "#f59e0b" },
  { id: "news_tuoitre", name: "Tuổi Trẻ News", type: "news", status: "planned", icon: "📰", color: "#f59e0b" },
];

const SC = {
  queued: "#6b7280", scripting: "#f59e0b", producing: "#3b82f6", rendering: "#8b5cf6",
  uploading: "#06b6d4", completed: "#10b981", failed: "#ef4444", scheduled: "#a78bfa",
  published: "#10b981", draft: "#f59e0b", approved: "#10b981", rejected: "#ef4444",
  pending_review: "#f59e0b", editing: "#3b82f6",
};

const ri = (a, b) => Math.floor(Math.random() * (b - a + 1)) + a;
const rf = (a, b) => +(Math.random() * (b - a) + a).toFixed(2);
const pick = (a) => a[ri(0, a.length - 1)];
const uid = () => Math.random().toString(36).slice(2, 10);

const SAMPLE_TOPICS_VN = [
  "5 thói quen buổi sáng tăng năng suất", "Cách tiết kiệm 50% thu nhập", "Bí mật giảm cân không cần ăn kiêng",
  "10 bài tập HIIT tại nhà", "Công thức smoothie detox 7 ngày", "Đầu tư chứng khoán cho người mới",
  "Morning routine của CEO", "Yoga 15 phút mỗi ngày", "Meal prep cho cả tuần",
  "5 cách kiếm tiền online 2026", "Thói quen đọc sách hiệu quả", "Skincare routine đơn giản",
  "Bí quyết ngủ ngon hơn", "Cách tập trung khi làm việc", "Top 5 app quản lý tài chính",
];

function genScrapedVideos(n = 40) {
  return Array.from({ length: n }, () => {
    const niche = pick(NICHES);
    const region = pick(REGIONS);
    return {
      id: `tt_${uid()}`,
      platform: "tiktok",
      source: pick(["tiktok_research", "tiktok_playwright"]),
      region,
      niche,
      author: `@${uid()}`,
      title: pick(SAMPLE_TOPICS_VN),
      hook_text: pick([
        "Bạn có biết rằng 90% người giàu đều làm điều này mỗi sáng?",
        "Đừng bao giờ ăn thứ này trước khi đi ngủ!",
        "Tôi đã kiếm được 100 triệu chỉ với thói quen đơn giản này",
        "Dừng lại! Bạn đang lãng phí tiền mỗi ngày vì điều này",
        "3 giây để thay đổi cuộc đời bạn",
      ]),
      play_count: ri(10000, 5000000),
      likes: ri(500, 200000),
      shares: ri(50, 50000),
      comments: ri(100, 30000),
      engagement_rate: rf(1.5, 15),
      duration: ri(15, 180),
      scraped_at: new Date(Date.now() - ri(0, 172800000)).toISOString(),
      is_indexed: Math.random() > 0.3,
      selected: false,
      tags: Array.from({ length: ri(2, 5) }, () => pick(["xuhuong", "viral", "moneytok", "healthtok", "foryou", "fyp", "tips", "trending", "lifestyle"])),
    };
  }).sort((a, b) => b.play_count - a.play_count);
}

function genScript(topic, niche) {
  const scenes = Array.from({ length: ri(6, 10) }, (_, i) => {
    const isHook = i === 0;
    const isCta = i === (ri(6, 10) - 1);
    const type = isHook ? "hook" : isCta ? "cta" : Math.random() > 0.8 ? "transition" : "body";
    return {
      id: i + 1,
      type,
      duration: type === "hook" ? ri(3, 5) : type === "cta" ? ri(5, 8) : type === "transition" ? ri(1, 3) : ri(4, 8),
      narration: pick([
        "Bạn có biết rằng thói quen buổi sáng quyết định 80% thành công của bạn?",
        "Hãy thức dậy lúc 5 giờ sáng và bắt đầu với ly nước ấm.",
        "Tiếp theo, hãy dành 10 phút để thiền định và lên kế hoạch cho ngày mới.",
        "Tập thể dục ít nhất 20 phút sẽ giúp bạn tỉnh táo suốt ngày.",
        "Đừng quên ăn sáng đầy đủ dinh dưỡng với protein và rau xanh.",
        "Follow để xem thêm những tip hay mỗi ngày nhé!",
        "Áp dụng ngay hôm nay và bạn sẽ thấy sự thay đổi chỉ sau 1 tuần.",
      ]),
      text_overlay: pick(["THÓI QUEN #1", "BÍ MẬT THÀNH CÔNG", "QUAN TRỌNG!", "FOLLOW ĐỂ XEM THÊM", "THAY ĐỔI NGAY", ""]),
      overlay_style: pick(OVERLAY_STYLES),
      visual_hint: pick([
        "person waking up sunrise bedroom", "morning coffee routine kitchen", "meditation peaceful room",
        "gym workout dynamic movement", "healthy breakfast close-up", "person walking nature park",
        "desk productivity setup", "yoga mat stretching", "healthy food preparation",
      ]),
      transition_out: pick(TRANSITION_TYPES),
      music_volume: 0.08,
      // production state
      asset_source: pick(["asset_db", "pexels", "veo", null]),
      asset_preview: null,
      audio_generated: Math.random() > 0.3,
      overlay_generated: Math.random() > 0.3,
    };
  });

  return {
    id: `script_${uid()}`,
    status: pick(["draft", "pending_review", "approved", "editing"]),
    created_at: new Date(Date.now() - ri(0, 86400000)).toISOString(),
    meta: { topic, niche, region: "VN", template: pick(TEMPLATES) },
    video: {
      title: topic,
      description: `${topic} - Video hướng dẫn chi tiết cho bạn. #${niche} #tips #viral`,
      hashtags: ["xuhuong", niche, "tips", "viral", "fyp"],
      total_duration: scenes.reduce((s, sc) => s + sc.duration, 0),
      music_mood: pick(MOODS),
      music_track: pick(MUSIC_TRACKS),
      voice: "af_heart",
      voice_speed: 1.1,
    },
    scenes,
    cta: { text: "Follow để xem thêm tip hay!", start_time: 55, duration: 7 },
    affiliate: { product: "", link: "", mention_at: 0 },
    llm_used: pick(["local", "gemini"]),
    generation_time: ri(20, 50),
  };
}

function genScripts(n = 8) {
  return Array.from({ length: n }, () => {
    const t = pick(SAMPLE_TOPICS_VN);
    return genScript(t, pick(NICHES));
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// ICONS
// ═══════════════════════════════════════════════════════════════════════════════
const I = {
  scraper: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>,
  script: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>,
  produce: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>,
  upload: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>,
  perf: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>,
  health: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>,
  llm: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>,
  pipeline: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>,
  play: <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21"/></svg>,
  pause: <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>,
  retry: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>,
  stop: <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>,
  check: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>,
  x: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>,
  edit: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>,
  trash: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>,
  plus: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>,
  copy: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>,
  image: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>,
  music: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>,
  mic: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/></svg>,
  swap: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/></svg>,
  eye: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>,
  arrow: <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="9 18 15 12 9 6"/></svg>,
  arrowDown: <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="6 9 12 15 18 9"/></svg>,
  arrowUp: <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="18 15 12 9 6 15"/></svg>,
  drag: <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" opacity="0.4"><circle cx="9" cy="6" r="1.5"/><circle cx="15" cy="6" r="1.5"/><circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/><circle cx="9" cy="18" r="1.5"/><circle cx="15" cy="18" r="1.5"/></svg>,
  generate: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>,
};

// ═══════════════════════════════════════════════════════════════════════════════
// SHARED UI
// ═══════════════════════════════════════════════════════════════════════════════
const font = "'IBM Plex Mono', 'Fira Code', 'Cascadia Code', monospace";
const bg0 = "#080b12", bg1 = "#0c1019", bg2 = "#111827", bg3 = "#1a2234", border = "#1e293b", border2 = "#2d3a50";
const txt1 = "#e2e8f0", txt2 = "#94a3b8", txt3 = "#64748b", accent = "#3b82f6", accent2 = "#8b5cf6";

function Card({ title, children, actions, noPad, style = {} }) {
  return (
    <div style={{ background: bg2, border: `1px solid ${border}`, borderRadius: 10, overflow: "hidden", ...style }}>
      {title && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", borderBottom: `1px solid ${border}` }}>
          <span style={{ fontWeight: 600, fontSize: 12, color: txt1 }}>{title}</span>
          {actions}
        </div>
      )}
      <div style={noPad ? {} : { padding: 14 }}>{children}</div>
    </div>
  );
}

function Badge({ status, small }) {
  const c = SC[status] || "#6b7280";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: small ? "2px 6px" : "3px 9px", borderRadius: 5, fontSize: small ? 9 : 10, fontWeight: 600, background: `${c}20`, color: c, textTransform: "uppercase", letterSpacing: "0.03em", whiteSpace: "nowrap" }}>
      <span style={{ width: 5, height: 5, borderRadius: "50%", background: c }} />{status.replace("_", " ")}
    </span>
  );
}

function Btn({ children, onClick, v = "default", disabled, style: sx = {} }) {
  const s = { default: { bg: bg3, c: txt2, h: border2 }, primary: { bg: "#1e40af", c: "#93c5fd", h: "#1d4ed8" }, danger: { bg: "#7f1d1d", c: "#fca5a5", h: "#991b1b" }, success: { bg: "#064e3b", c: "#6ee7b7", h: "#065f46" }, ghost: { bg: "transparent", c: txt2, h: `${border}66` }, accent: { bg: "#4c1d95", c: "#c4b5fd", h: "#5b21b6" } }[v];
  return (
    <button onClick={onClick} disabled={disabled} style={{ background: s.bg, color: s.c, border: "none", borderRadius: 6, padding: "5px 10px", fontSize: 11, cursor: disabled ? "not-allowed" : "pointer", fontFamily: font, display: "inline-flex", alignItems: "center", gap: 4, fontWeight: 500, opacity: disabled ? 0.5 : 1, transition: "background 0.12s", whiteSpace: "nowrap", ...sx }}
      onMouseEnter={(e) => !disabled && (e.currentTarget.style.background = s.h)}
      onMouseLeave={(e) => !disabled && (e.currentTarget.style.background = s.bg)}>
      {children}
    </button>
  );
}

function ProgressBar({ value, color = accent, h = 5 }) {
  return <div style={{ background: bg3, borderRadius: h, height: h, width: "100%", overflow: "hidden" }}><div style={{ height: "100%", width: `${Math.min(value, 100)}%`, background: color, borderRadius: h, transition: "width 0.4s ease" }} /></div>;
}

function Sel({ value, onChange, options, style: sx = {} }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} style={{ background: bg3, color: txt1, border: `1px solid ${border}`, borderRadius: 5, padding: "5px 8px", fontSize: 11, fontFamily: font, cursor: "pointer", ...sx }}>
      {options.map((o) => <option key={typeof o === "string" ? o : o.value} value={typeof o === "string" ? o : o.value}>{typeof o === "string" ? o : o.label}</option>)}
    </select>
  );
}

function Input({ value, onChange, placeholder, style: sx = {}, multiline, rows = 3 }) {
  const shared = { background: bg1, color: txt1, border: `1px solid ${border}`, borderRadius: 6, padding: "7px 10px", fontSize: 11, fontFamily: font, width: "100%", boxSizing: "border-box", outline: "none", resize: "vertical", ...sx };
  if (multiline) return <textarea value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} rows={rows} style={shared} />;
  return <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} style={shared} />;
}

function StatBox({ label, value, sub, color = accent }) {
  return (
    <div style={{ background: bg2, border: `1px solid ${border}`, borderRadius: 9, padding: "12px 14px", flex: 1, minWidth: 120 }}>
      <div style={{ fontSize: 9, color: txt3, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color, letterSpacing: "-0.02em" }}>{value}</div>
      {sub && <div style={{ fontSize: 9, color: txt3, marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

function Tabs({ items, active, onChange }) {
  return (
    <div style={{ display: "flex", borderBottom: `1px solid ${border}`, overflowX: "auto", flexShrink: 0 }}>
      {items.map((t) => (
        <button key={t.id} onClick={() => onChange(t.id)} style={{ background: "none", border: "none", color: active === t.id ? txt1 : txt3, padding: "9px 14px", cursor: "pointer", fontSize: 11, fontFamily: font, display: "flex", alignItems: "center", gap: 5, borderBottom: active === t.id ? `2px solid ${accent}` : "2px solid transparent", transition: "all 0.12s", whiteSpace: "nowrap" }}>
          {t.icon} {t.label}
          {t.count != null && <span style={{ background: `${accent}30`, color: accent, padding: "1px 5px", borderRadius: 4, fontSize: 9, fontWeight: 600, marginLeft: 2 }}>{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

function Modal({ open, onClose, title, children, width = 700 }) {
  if (!open) return null;
  return (
    <div style={{ position: "fixed", inset: 0, background: "#000000bb", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: bg2, border: `1px solid ${border}`, borderRadius: 12, width: "100%", maxWidth: width, maxHeight: "85vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", borderBottom: `1px solid ${border}` }}>
          <span style={{ fontWeight: 700, fontSize: 14, color: txt1 }}>{title}</span>
          <Btn v="ghost" onClick={onClose}>{I.x}</Btn>
        </div>
        <div style={{ padding: 16, overflowY: "auto", flex: 1 }}>{children}</div>
      </div>
    </div>
  );
}

function Sparkline({ data, color = "#10b981", h = 36, w = 100 }) {
  if (!data?.length) return null;
  const max = Math.max(...data), min = Math.min(...data), range = max - min || 1;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * (h - 4) - 2}`).join(" ");
  return <svg width={w} height={h} style={{ display: "block" }}><polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

function BarChart({ data, lk, vk, color = accent, h = 140 }) {
  const max = Math.max(...data.map((d) => d[vk])) || 1;
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: h, padding: "0 2px" }}>
      {data.map((d, i) => (
        <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
          <div style={{ width: "100%", maxWidth: 28, height: `${(d[vk] / max) * (h - 24)}px`, background: `linear-gradient(180deg, ${color}, ${color}77)`, borderRadius: "3px 3px 0 0", minHeight: 2, transition: "height 0.4s" }} />
          <span style={{ fontSize: 8, color: txt3, whiteSpace: "nowrap" }}>{d[lk]}</span>
        </div>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════════════════════════
export default function App() {
  const [tab, setTab] = useState("scraper");
  const [toast, setToast] = useState(null);
  const [scraped, setScraped] = useState(() => genScrapedVideos(40));
  const [scripts, setScripts] = useState(() => genScripts(8));
  const [jobs, setJobs] = useState(() => genPipelineJobs(20));
  const [uploads, setUploads] = useState(() => genUploads(16));
  const [perfData] = useState(() => genPerf(14));
  const [llmMode, setLlmMode] = useState("hybrid");
  const [assetMode, setAssetMode] = useState("db_then_hybrid");
  const [batchOn, setBatchOn] = useState(true);

  const notify = useCallback((msg) => { setToast(msg); setTimeout(() => setToast(null), 2800); }, []);

  // live sim
  useEffect(() => {
    const iv = setInterval(() => {
      setJobs((prev) => prev.map((j) => {
        if (j.status === "queued" && Math.random() > 0.88) return { ...j, status: "scripting", progress: 8, startedAt: new Date().toISOString() };
        if (j.status === "scripting" && Math.random() > 0.75) return { ...j, status: "producing", progress: Math.min(j.progress + ri(12, 25), 60) };
        if (j.status === "producing" && Math.random() > 0.72) return { ...j, status: "rendering", progress: Math.min(j.progress + ri(8, 18), 85) };
        if (j.status === "rendering" && Math.random() > 0.65) return Math.random() > 0.92 ? { ...j, status: "failed", error: pick(["NVENC timeout", "ffmpeg crash"]) } : { ...j, status: "uploading", progress: 93 };
        if (j.status === "uploading" && Math.random() > 0.55) return { ...j, status: "completed", progress: 100, duration: ri(95, 230) };
        if (!["completed", "failed", "queued"].includes(j.status) && j.progress < 98) return { ...j, progress: Math.min(j.progress + ri(1, 4), 99) };
        return j;
      }));
    }, 2800);
    return () => clearInterval(iv);
  }, []);

  const tabs = [
    { id: "scraper", label: "Scraper", icon: I.scraper, count: scraped.filter((s) => s.selected).length || null },
    { id: "scripts", label: "Scripts", icon: I.script, count: scripts.filter((s) => s.status === "pending_review").length || null },
    { id: "produce", label: "Production", icon: I.produce },
    { id: "pipeline", label: "Pipeline", icon: I.pipeline },
    { id: "uploads", label: "Uploads", icon: I.upload },
    { id: "llm", label: "LLM Router", icon: I.llm },
    { id: "perf", label: "Performance", icon: I.perf },
    { id: "health", label: "System", icon: I.health },
  ];

  return (
    <div style={{ fontFamily: font, background: bg0, color: txt1, minHeight: "100vh", fontSize: 12 }}>
      {toast && <div style={{ position: "fixed", top: 14, right: 14, background: "#10b981", color: "#000", padding: "8px 18px", borderRadius: 7, fontWeight: 600, zIndex: 9999, fontSize: 11, boxShadow: "0 4px 20px #10b98144" }}>{toast}</div>}

      {/* HEADER */}
      <div style={{ background: bg1, borderBottom: `1px solid ${border}`, padding: "10px 18px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 30, height: 30, background: `linear-gradient(135deg, ${accent}, ${accent2})`, borderRadius: 7, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 12 }}>AI</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, letterSpacing: "-0.02em" }}>AI Media Factory</div>
            <div style={{ fontSize: 9, color: txt3 }}>v1.1 — Content Management Console</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 10, color: txt3 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: batchOn ? "#10b981" : "#ef4444" }} />
            Batch: {batchOn ? "On" : "Off"}
          </div>
          <span>LLM: {llmMode.toUpperCase()}</span>
          <span>{new Date().toLocaleTimeString()}</span>
        </div>
      </div>

      {/* TABS */}
      <div style={{ background: bg1 }}>
        <div style={{ maxWidth: 1260, margin: "0 auto" }}>
          <Tabs items={tabs} active={tab} onChange={setTab} />
        </div>
      </div>

      {/* CONTENT */}
      <div style={{ padding: 14, maxWidth: 1260, margin: "0 auto" }}>
        {tab === "scraper" && <ScraperTab scraped={scraped} setScraped={setScraped} scripts={scripts} setScripts={setScripts} notify={notify} />}
        {tab === "scripts" && <ScriptTab scripts={scripts} setScripts={setScripts} notify={notify} />}
        {tab === "produce" && <ProduceTab scripts={scripts} setScripts={setScripts} assetMode={assetMode} setAssetMode={setAssetMode} notify={notify} />}
        {tab === "pipeline" && <PipelineTab jobs={jobs} setJobs={setJobs} batchOn={batchOn} setBatchOn={setBatchOn} notify={notify} />}
        {tab === "uploads" && <UploadTab uploads={uploads} setUploads={setUploads} notify={notify} />}
        {tab === "llm" && <LLMTab llmMode={llmMode} setLlmMode={setLlmMode} notify={notify} />}
        {tab === "perf" && <PerfTab perfData={perfData} />}
        {tab === "health" && <HealthTab />}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB: SCRAPER — Extensible source management + data selection → topic creation
// ═══════════════════════════════════════════════════════════════════════════════
function ScraperTab({ scraped, setScraped, scripts, setScripts, notify }) {
  const [sourceFilter, setSourceFilter] = useState("all");
  const [nicheFilter, setNicheFilter] = useState("all");
  const [regionFilter, setRegionFilter] = useState("all");
  const [sortBy, setSortBy] = useState("play_count");
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [topicModal, setTopicModal] = useState(false);
  const [newTopic, setNewTopic] = useState("");
  const [newNiche, setNewNiche] = useState("lifestyle");
  const [newTemplate, setNewTemplate] = useState("tiktok_viral");
  const [sourceManager, setSourceManager] = useState(false);
  const [sources, setSources] = useState(SCRAPER_SOURCES);

  const filtered = useMemo(() => {
    let d = [...scraped];
    if (sourceFilter !== "all") d = d.filter((v) => v.source === sourceFilter);
    if (nicheFilter !== "all") d = d.filter((v) => v.niche === nicheFilter);
    if (regionFilter !== "all") d = d.filter((v) => v.region === regionFilter);
    d.sort((a, b) => b[sortBy] - a[sortBy]);
    return d;
  }, [scraped, sourceFilter, nicheFilter, regionFilter, sortBy]);

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  };

  const selectAll = () => {
    if (selectedIds.size === filtered.length) setSelectedIds(new Set());
    else setSelectedIds(new Set(filtered.map((v) => v.id)));
  };

  const generateFromSelected = () => {
    if (!newTopic.trim()) return notify("Enter a topic first");
    const s = genScript(newTopic, newNiche);
    s.meta.template = newTemplate;
    s.status = "draft";
    s._sourceVideos = [...selectedIds];
    setScripts((prev) => [s, ...prev]);
    setSelectedIds(new Set());
    setTopicModal(false);
    setNewTopic("");
    notify(`Script generated: "${newTopic}" → Scripts tab`);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* stats */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <StatBox label="Total Scraped" value={scraped.length} color={txt1} sub="Last 48 hours" />
        <StatBox label="Indexed" value={scraped.filter((v) => v.is_indexed).length} color="#10b981" sub="Synced to ChromaDB" />
        <StatBox label="Selected" value={selectedIds.size} color={accent} sub="Ready for topic generation" />
        <StatBox label="Avg ER" value={`${(scraped.reduce((s, v) => s + v.engagement_rate, 0) / scraped.length).toFixed(1)}%`} color="#f59e0b" />
        <StatBox label="Active Sources" value={sources.filter((s) => s.status === "active").length} color="#10b981" sub={`/ ${sources.length} total`} />
      </div>

      {/* source manager */}
      <Card title="Scraper Sources" actions={
        <div style={{ display: "flex", gap: 6 }}>
          <Btn v="primary" onClick={() => setSourceManager(true)}>{I.edit} Manage Sources</Btn>
          <Btn onClick={() => notify("Scraping TikTok Research API...")}>{I.play} Run Scrape Now</Btn>
        </div>
      }>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {sources.map((s) => (
            <div key={s.id} style={{ background: bg1, border: `1px solid ${s.status === "active" ? "#10b981" : border}`, borderRadius: 7, padding: "8px 12px", display: "flex", alignItems: "center", gap: 8, minWidth: 180 }}>
              <span style={{ fontSize: 16 }}>{s.icon}</span>
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: s.status === "active" ? txt1 : txt3 }}>{s.name}</div>
                <div style={{ fontSize: 9, color: s.status === "active" ? "#10b981" : s.status === "standby" ? "#f59e0b" : txt3 }}>
                  {s.status === "active" ? "● Active" : s.status === "standby" ? "◐ Standby" : "○ Planned"}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* source manager modal */}
      <Modal open={sourceManager} onClose={() => setSourceManager(false)} title="Manage Scraper Sources" width={600}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {sources.map((s, idx) => (
            <div key={s.id} style={{ background: bg1, border: `1px solid ${border}`, borderRadius: 8, padding: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 20 }}>{s.icon}</span>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 12 }}>{s.name}</div>
                  <div style={{ fontSize: 10, color: txt3 }}>Type: {s.type} · ID: {s.id}</div>
                </div>
              </div>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <Sel value={s.status} onChange={(v) => { setSources((prev) => prev.map((x, i) => i === idx ? { ...x, status: v } : x)); notify(`${s.name} → ${v}`); }} options={["active", "standby", "planned"]} />
                {s.status === "active" && <Btn v="primary" onClick={() => notify(`Running ${s.name}...`)}>{I.play} Run</Btn>}
              </div>
            </div>
          ))}
          <div style={{ borderTop: `1px solid ${border}`, paddingTop: 12, marginTop: 4 }}>
            <div style={{ fontSize: 10, color: txt3, marginBottom: 6 }}>Add new source (coming soon): news websites, YouTube trending, Reddit, etc.</div>
            <Btn v="ghost" disabled>{I.plus} Add Custom Source</Btn>
          </div>
        </div>
      </Modal>

      {/* filters + actions */}
      <Card title="Scraped Videos" actions={
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <Sel value={sourceFilter} onChange={setSourceFilter} options={[{ value: "all", label: "All Sources" }, ...sources.filter((s) => s.status !== "planned").map((s) => ({ value: s.id, label: s.name }))]} />
          <Sel value={nicheFilter} onChange={setNicheFilter} options={[{ value: "all", label: "All Niches" }, ...NICHES.map((n) => ({ value: n, label: n }))]} />
          <Sel value={regionFilter} onChange={setRegionFilter} options={[{ value: "all", label: "All Regions" }, ...REGIONS.map((r) => ({ value: r, label: r }))]} />
          <Sel value={sortBy} onChange={setSortBy} options={[{ value: "play_count", label: "Views ↓" }, { value: "engagement_rate", label: "ER ↓" }, { value: "likes", label: "Likes ↓" }]} />
        </div>
      } noPad>
        {/* action bar */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 14px", borderBottom: `1px solid ${border}`, background: bg1 }}>
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <Btn v="ghost" onClick={selectAll}>
              {selectedIds.size === filtered.length ? I.check : <span style={{ width: 13, height: 13, display: "inline-block", border: `2px solid ${txt3}`, borderRadius: 3 }} />}
              <span style={{ marginLeft: 4 }}>{selectedIds.size > 0 ? `${selectedIds.size} selected` : "Select all"}</span>
            </Btn>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <Btn v="primary" onClick={() => selectedIds.size > 0 ? setTopicModal(true) : notify("Select videos first")} disabled={selectedIds.size === 0}>
              {I.generate} Generate Script from Selected
            </Btn>
            <Btn onClick={() => notify("Indexing selected to ChromaDB...")} disabled={selectedIds.size === 0}>Index to ChromaDB</Btn>
          </div>
        </div>

        {/* video list */}
        <div style={{ maxHeight: 440, overflowY: "auto" }}>
          {filtered.map((v) => {
            const sel = selectedIds.has(v.id);
            return (
              <div key={v.id} onClick={() => toggleSelect(v.id)} style={{ display: "grid", gridTemplateColumns: "32px 1fr 90px 80px 70px 80px 60px", alignItems: "center", gap: 6, padding: "8px 14px", borderBottom: `1px solid ${border}`, cursor: "pointer", background: sel ? `${accent}10` : "transparent", transition: "background 0.1s" }}
                onMouseEnter={(e) => !sel && (e.currentTarget.style.background = `${bg3}66`)}
                onMouseLeave={(e) => !sel && (e.currentTarget.style.background = "transparent")}>
                <div style={{ width: 18, height: 18, borderRadius: 4, border: sel ? `2px solid ${accent}` : `2px solid ${txt3}`, background: sel ? accent : "transparent", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {sel && <span style={{ color: "#fff", fontSize: 10, fontWeight: 800 }}>✓</span>}
                </div>
                <div style={{ overflow: "hidden" }}>
                  <div style={{ fontSize: 11, fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{v.hook_text || v.title}</div>
                  <div style={{ fontSize: 9, color: txt3, marginTop: 2 }}>{v.author} · {v.tags.slice(0, 3).map((t) => `#${t}`).join(" ")}</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: txt1 }}>{v.play_count > 1000000 ? `${(v.play_count / 1000000).toFixed(1)}M` : `${(v.play_count / 1000).toFixed(0)}K`}</div>
                  <div style={{ fontSize: 9, color: txt3 }}>views</div>
                </div>
                <div style={{ fontSize: 11, fontWeight: 600, color: v.engagement_rate > 5 ? "#10b981" : v.engagement_rate > 2 ? "#f59e0b" : txt3 }}>
                  {v.engagement_rate}%
                </div>
                <Badge status={v.niche} small />
                <span style={{ fontSize: 10, color: txt3 }}>{v.region}</span>
                <span style={{ fontSize: 10, color: v.is_indexed ? "#10b981" : txt3 }}>{v.is_indexed ? "✓ idx" : "—"}</span>
              </div>
            );
          })}
        </div>
      </Card>

      {/* topic creation modal */}
      <Modal open={topicModal} onClose={() => setTopicModal(false)} title={`Create Script from ${selectedIds.size} Videos`}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ background: bg1, borderRadius: 8, padding: 12, border: `1px solid ${border}` }}>
            <div style={{ fontSize: 10, color: txt3, marginBottom: 6 }}>SELECTED VIDEOS ({selectedIds.size})</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {[...selectedIds].slice(0, 6).map((id) => {
                const v = scraped.find((x) => x.id === id);
                return v ? <span key={id} style={{ background: `${accent}20`, color: accent, padding: "2px 8px", borderRadius: 4, fontSize: 9 }}>{v.hook_text?.slice(0, 30)}...</span> : null;
              })}
              {selectedIds.size > 6 && <span style={{ color: txt3, fontSize: 9, padding: "2px 8px" }}>+{selectedIds.size - 6} more</span>}
            </div>
          </div>

          <div>
            <label style={{ fontSize: 10, color: txt3, display: "block", marginBottom: 4 }}>TOPIC / TITLE</label>
            <Input value={newTopic} onChange={setNewTopic} placeholder="e.g., 5 thói quen buổi sáng tăng năng suất" />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div>
              <label style={{ fontSize: 10, color: txt3, display: "block", marginBottom: 4 }}>NICHE</label>
              <Sel value={newNiche} onChange={setNewNiche} options={NICHES} style={{ width: "100%" }} />
            </div>
            <div>
              <label style={{ fontSize: 10, color: txt3, display: "block", marginBottom: 4 }}>TEMPLATE</label>
              <Sel value={newTemplate} onChange={setNewTemplate} options={TEMPLATES} style={{ width: "100%" }} />
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", paddingTop: 8, borderTop: `1px solid ${border}` }}>
            <Btn v="ghost" onClick={() => setTopicModal(false)}>Cancel</Btn>
            <Btn v="primary" onClick={generateFromSelected}>{I.generate} Generate Script with LLM</Btn>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB: SCRIPT EDITOR — Full script editing after LLM generation
// ═══════════════════════════════════════════════════════════════════════════════
function ScriptTab({ scripts, setScripts, notify }) {
  const [editing, setEditing] = useState(null);
  const [editData, setEditData] = useState(null);
  const [filter, setFilter] = useState("all");

  const filtered = filter === "all" ? scripts : scripts.filter((s) => s.status === filter);

  const openEditor = (script) => {
    setEditing(script.id);
    setEditData(JSON.parse(JSON.stringify(script)));
  };

  const saveScript = () => {
    setScripts((prev) => prev.map((s) => s.id === editing ? { ...editData, status: editData.status === "draft" ? "pending_review" : editData.status } : s));
    setEditing(null);
    setEditData(null);
    notify("Script saved");
  };

  const approveScript = (id) => {
    setScripts((prev) => prev.map((s) => s.id === id ? { ...s, status: "approved" } : s));
    notify("Script approved → ready for production");
  };

  const rejectScript = (id) => {
    setScripts((prev) => prev.map((s) => s.id === id ? { ...s, status: "draft" } : s));
    notify("Script sent back to draft");
  };

  const regenerateScript = (id) => {
    setScripts((prev) => prev.map((s) => s.id === id ? { ...genScript(s.meta.topic, s.meta.niche), id: s.id, status: "draft" } : s));
    notify("Script regenerated by LLM");
  };

  const updateScene = (idx, field, value) => {
    setEditData((prev) => {
      const n = { ...prev, scenes: [...prev.scenes] };
      n.scenes[idx] = { ...n.scenes[idx], [field]: value };
      if (field === "duration") n.video = { ...n.video, total_duration: n.scenes.reduce((s, sc) => s + sc.duration, 0) };
      return n;
    });
  };

  const addScene = () => {
    setEditData((prev) => ({
      ...prev,
      scenes: [...prev.scenes, {
        id: prev.scenes.length + 1, type: "body", duration: 5,
        narration: "", text_overlay: "", overlay_style: "big_white_center",
        visual_hint: "", transition_out: "cut", music_volume: 0.08,
        asset_source: null, audio_generated: false, overlay_generated: false,
      }],
    }));
  };

  const removeScene = (idx) => {
    setEditData((prev) => ({
      ...prev,
      scenes: prev.scenes.filter((_, i) => i !== idx).map((s, i) => ({ ...s, id: i + 1 })),
    }));
  };

  const moveScene = (idx, dir) => {
    setEditData((prev) => {
      const s = [...prev.scenes];
      const ni = idx + dir;
      if (ni < 0 || ni >= s.length) return prev;
      [s[idx], s[ni]] = [s[ni], s[idx]];
      return { ...prev, scenes: s.map((sc, i) => ({ ...sc, id: i + 1 })) };
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* stats */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <StatBox label="Total Scripts" value={scripts.length} color={txt1} />
        <StatBox label="Draft" value={scripts.filter((s) => s.status === "draft").length} color="#f59e0b" />
        <StatBox label="Pending Review" value={scripts.filter((s) => s.status === "pending_review").length} color={accent} />
        <StatBox label="Approved" value={scripts.filter((s) => s.status === "approved").length} color="#10b981" />
      </div>

      {/* script list */}
      <Card title="Scripts" actions={
        <div style={{ display: "flex", gap: 4 }}>
          {["all", "draft", "pending_review", "approved", "editing"].map((f) => (
            <button key={f} onClick={() => setFilter(f)} style={{ background: filter === f ? "#1e40af" : "transparent", color: filter === f ? "#93c5fd" : txt3, border: "none", borderRadius: 4, padding: "3px 7px", fontSize: 10, cursor: "pointer", fontFamily: font, textTransform: "capitalize" }}>
              {f.replace("_", " ")}
            </button>
          ))}
        </div>
      }>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 480, overflowY: "auto" }}>
          {filtered.map((s) => (
            <div key={s.id} style={{ background: bg1, borderRadius: 8, border: `1px solid ${border}`, padding: 12, transition: "border 0.15s" }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = border2)}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = border)}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <Badge status={s.status} />
                    <span style={{ fontSize: 9, color: txt3 }}>{s.meta.template} · {s.llm_used} · {s.generation_time}s</span>
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: txt1, marginBottom: 4 }}>{s.meta.topic}</div>
                  <div style={{ fontSize: 10, color: txt3 }}>
                    {s.meta.niche} · {s.meta.region} · {s.scenes.length} scenes · {s.video.total_duration}s total
                  </div>
                  <div style={{ fontSize: 9, color: txt3, marginTop: 4 }}>
                    Hook: "{s.scenes[0]?.narration?.slice(0, 60)}..."
                  </div>
                </div>
                <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
                  <Btn v="primary" onClick={() => openEditor(s)}>{I.edit} Edit</Btn>
                  {s.status === "pending_review" && <Btn v="success" onClick={() => approveScript(s.id)}>{I.check} Approve</Btn>}
                  {s.status === "pending_review" && <Btn v="danger" onClick={() => rejectScript(s.id)}>{I.x} Reject</Btn>}
                  <Btn v="ghost" onClick={() => regenerateScript(s.id)}>{I.retry} Regen</Btn>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* FULL SCRIPT EDITOR MODAL */}
      <Modal open={!!editing} onClose={() => { setEditing(null); setEditData(null); }} title="Script Editor" width={900}>
        {editData && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* meta */}
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 10 }}>
              <div>
                <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3 }}>TOPIC</label>
                <Input value={editData.meta.topic} onChange={(v) => setEditData({ ...editData, meta: { ...editData.meta, topic: v } })} />
              </div>
              <div>
                <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3 }}>NICHE</label>
                <Sel value={editData.meta.niche} onChange={(v) => setEditData({ ...editData, meta: { ...editData.meta, niche: v } })} options={NICHES} style={{ width: "100%" }} />
              </div>
              <div>
                <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3 }}>TEMPLATE</label>
                <Sel value={editData.meta.template} onChange={(v) => setEditData({ ...editData, meta: { ...editData.meta, template: v } })} options={TEMPLATES} style={{ width: "100%" }} />
              </div>
              <div>
                <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3 }}>REGION</label>
                <Sel value={editData.meta.region} onChange={(v) => setEditData({ ...editData, meta: { ...editData.meta, region: v } })} options={REGIONS} style={{ width: "100%" }} />
              </div>
            </div>

            {/* video meta */}
            <div style={{ background: bg1, borderRadius: 8, padding: 12, border: `1px solid ${border}` }}>
              <div style={{ fontSize: 10, color: txt3, marginBottom: 8, fontWeight: 600 }}>VIDEO METADATA</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div>
                  <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3 }}>TITLE</label>
                  <Input value={editData.video.title} onChange={(v) => setEditData({ ...editData, video: { ...editData.video, title: v } })} />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                  <div>
                    <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3 }}>MOOD</label>
                    <Sel value={editData.video.music_mood} onChange={(v) => setEditData({ ...editData, video: { ...editData.video, music_mood: v } })} options={MOODS} style={{ width: "100%" }} />
                  </div>
                  <div>
                    <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3 }}>VOICE</label>
                    <Sel value={editData.video.voice} onChange={(v) => setEditData({ ...editData, video: { ...editData.video, voice: v } })} options={VOICES} style={{ width: "100%" }} />
                  </div>
                  <div>
                    <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3 }}>SPEED</label>
                    <Sel value={editData.video.voice_speed} onChange={(v) => setEditData({ ...editData, video: { ...editData.video, voice_speed: +v } })} options={[{ value: 0.8, label: "0.8×" }, { value: 0.9, label: "0.9×" }, { value: 1.0, label: "1.0×" }, { value: 1.1, label: "1.1×" }, { value: 1.2, label: "1.2×" }]} style={{ width: "100%" }} />
                  </div>
                </div>
              </div>
              <div style={{ marginTop: 8 }}>
                <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3 }}>DESCRIPTION</label>
                <Input multiline rows={2} value={editData.video.description} onChange={(v) => setEditData({ ...editData, video: { ...editData.video, description: v } })} />
              </div>
              <div style={{ marginTop: 8 }}>
                <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3 }}>HASHTAGS (comma separated)</label>
                <Input value={editData.video.hashtags.join(", ")} onChange={(v) => setEditData({ ...editData, video: { ...editData.video, hashtags: v.split(",").map((t) => t.trim()).filter(Boolean) } })} />
              </div>
            </div>

            {/* scenes editor */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: txt1 }}>SCENES ({editData.scenes.length}) · Total: {editData.scenes.reduce((s, sc) => s + sc.duration, 0)}s</div>
                <Btn v="primary" onClick={addScene}>{I.plus} Add Scene</Btn>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {editData.scenes.map((sc, idx) => (
                  <div key={idx} style={{ background: bg1, border: `1px solid ${sc.type === "hook" ? "#f59e0b44" : sc.type === "cta" ? "#10b98144" : border}`, borderRadius: 8, padding: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ color: txt3 }}>{I.drag}</span>
                        <span style={{ fontSize: 11, fontWeight: 700, color: accent }}>#{sc.id}</span>
                        <Sel value={sc.type} onChange={(v) => updateScene(idx, "type", v)} options={SCENE_TYPES} />
                        <Sel value={sc.duration} onChange={(v) => updateScene(idx, "duration", +v)} options={Array.from({ length: 20 }, (_, i) => ({ value: i + 1, label: `${i + 1}s` }))} />
                        <Sel value={sc.transition_out} onChange={(v) => updateScene(idx, "transition_out", v)} options={TRANSITION_TYPES} />
                      </div>
                      <div style={{ display: "flex", gap: 4 }}>
                        <Btn v="ghost" onClick={() => moveScene(idx, -1)} disabled={idx === 0}>{I.arrowUp}</Btn>
                        <Btn v="ghost" onClick={() => moveScene(idx, 1)} disabled={idx === editData.scenes.length - 1}>{I.arrowDown}</Btn>
                        <Btn v="danger" onClick={() => removeScene(idx)} disabled={editData.scenes.length <= 2}>{I.trash}</Btn>
                      </div>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                      <div>
                        <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 2 }}>NARRATION (TTS)</label>
                        <Input multiline rows={2} value={sc.narration} onChange={(v) => updateScene(idx, "narration", v)} placeholder="Text for voiceover..." />
                      </div>
                      <div>
                        <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 2 }}>VISUAL HINT (for asset resolver)</label>
                        <Input multiline rows={2} value={sc.visual_hint} onChange={(v) => updateScene(idx, "visual_hint", v)} placeholder="e.g., person waking up sunrise bedroom" />
                      </div>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 6 }}>
                      <div>
                        <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 2 }}>TEXT OVERLAY</label>
                        <Input value={sc.text_overlay} onChange={(v) => updateScene(idx, "text_overlay", v)} placeholder="On-screen text..." />
                      </div>
                      <div>
                        <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 2 }}>OVERLAY STYLE</label>
                        <Sel value={sc.overlay_style} onChange={(v) => updateScene(idx, "overlay_style", v)} options={OVERLAY_STYLES} style={{ width: "100%" }} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* CTA + affiliate */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div style={{ background: bg1, borderRadius: 8, padding: 12, border: `1px solid ${border}` }}>
                <div style={{ fontSize: 10, color: txt3, marginBottom: 6, fontWeight: 600 }}>CTA</div>
                <Input value={editData.cta.text} onChange={(v) => setEditData({ ...editData, cta: { ...editData.cta, text: v } })} placeholder="CTA text..." />
              </div>
              <div style={{ background: bg1, borderRadius: 8, padding: 12, border: `1px solid ${border}` }}>
                <div style={{ fontSize: 10, color: txt3, marginBottom: 6, fontWeight: 600 }}>AFFILIATE</div>
                <Input value={editData.affiliate.product} onChange={(v) => setEditData({ ...editData, affiliate: { ...editData.affiliate, product: v } })} placeholder="Product name..." />
                <Input value={editData.affiliate.link} onChange={(v) => setEditData({ ...editData, affiliate: { ...editData.affiliate, link: v } })} placeholder="https://..." style={{ marginTop: 4 }} />
              </div>
            </div>

            {/* save bar */}
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", paddingTop: 10, borderTop: `1px solid ${border}` }}>
              <Btn v="ghost" onClick={() => { setEditing(null); setEditData(null); }}>Cancel</Btn>
              <Btn v="accent" onClick={() => { regenerateScript(editing); setEditing(null); setEditData(null); }}>{I.retry} Regenerate</Btn>
              <Btn v="primary" onClick={saveScript}>{I.check} Save Script</Btn>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB: PRODUCTION — Scene-level editing: replace video/photo, change audio
// ═══════════════════════════════════════════════════════════════════════════════
function ProduceTab({ scripts, setScripts, assetMode, setAssetMode, notify }) {
  const [selected, setSelected] = useState(null);
  const [sceneEdit, setSceneEdit] = useState(null);
  const [assetBrowser, setAssetBrowser] = useState(false);
  const [assetTarget, setAssetTarget] = useState(null);

  const approved = scripts.filter((s) => s.status === "approved" || s.status === "editing");
  const script = approved.find((s) => s.id === selected);

  const mockAssets = useMemo(() => Array.from({ length: 20 }, (_, i) => ({
    id: `asset_${uid()}`,
    source: pick(["pexels", "veo", "manual"]),
    keywords: Array.from({ length: ri(2, 4) }, () => pick(["morning", "sunrise", "person", "workout", "kitchen", "nature", "office", "yoga", "food", "city"])),
    duration: ri(4, 15),
    resolution: "1080x1920",
    quality: rf(0.6, 1.0),
    usage_count: ri(0, 20),
    preview_color: `hsl(${ri(0, 360)}, 40%, ${ri(15, 30)}%)`,
  })), []);

  const openAssetBrowser = (sceneIdx, field) => {
    setAssetTarget({ sceneIdx, field });
    setAssetBrowser(true);
  };

  const selectAsset = (asset) => {
    if (!assetTarget || !script) return;
    setScripts((prev) => prev.map((s) => {
      if (s.id !== script.id) return s;
      const scenes = [...s.scenes];
      scenes[assetTarget.sceneIdx] = {
        ...scenes[assetTarget.sceneIdx],
        asset_source: asset.source,
        asset_preview: asset.preview_color,
        visual_hint: asset.keywords.join(" "),
      };
      return { ...s, scenes, status: "editing" };
    }));
    setAssetBrowser(false);
    notify(`Scene #${assetTarget.sceneIdx + 1}: asset replaced from ${asset.source}`);
  };

  const regenerateAudio = (sceneIdx) => {
    setScripts((prev) => prev.map((s) => {
      if (s.id !== script.id) return s;
      const scenes = [...s.scenes];
      scenes[sceneIdx] = { ...scenes[sceneIdx], audio_generated: true };
      return { ...s, scenes, status: "editing" };
    }));
    notify(`Scene #${sceneIdx + 1}: TTS audio regenerated`);
  };

  const startProduction = (id) => {
    notify(`Production started for script ${id} → Pipeline tab`);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* stats */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <StatBox label="Approved Scripts" value={approved.length} color="#10b981" sub="Ready for production" />
        <StatBox label="Asset DB" value={`${ri(320, 500)} clips`} color={accent2} />
        <StatBox label="Cache Hit" value={`${rf(55, 78)}%`} color="#10b981" />
        <StatBox label="Asset Mode" value={assetMode.replace("db_then_", "").toUpperCase()} color={accent} />
      </div>

      {/* asset mode selector */}
      <Card title="Asset Resolver" actions={
        <Sel value={assetMode} onChange={(v) => { setAssetMode(v); notify(`Asset mode → ${v}`); }} options={ASSET_MODES.map((m) => ({ value: m, label: m }))} />
      }>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
          {[
            { type: "hook", src: "veo", icon: "🎬", reason: "Generate fresh — first impression" },
            { type: "body", src: "pexels", icon: "📦", reason: "Stock footage — cost effective" },
            { type: "transition", src: "pexels", icon: "📦", reason: "Filler — always stock" },
            { type: "cta", src: "veo", icon: "🎬", reason: "Generate fresh — closing shot" },
          ].map((r) => (
            <div key={r.type} style={{ background: bg1, borderRadius: 7, padding: 10, border: `1px solid ${border}`, textAlign: "center" }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: txt1, textTransform: "uppercase" }}>{r.type}</div>
              <div style={{ fontSize: 18, margin: "4px 0" }}>{r.icon}</div>
              <div style={{ fontSize: 10, fontWeight: 600, color: r.src === "veo" ? accent2 : "#06b6d4" }}>{r.src}</div>
              <div style={{ fontSize: 8, color: txt3, marginTop: 2 }}>{r.reason}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* script selector + scene editor */}
      <Card title="Production Editor" noPad>
        {/* script list */}
        <div style={{ display: "flex", borderBottom: `1px solid ${border}`, overflowX: "auto" }}>
          {approved.length === 0 && <div style={{ padding: 20, color: txt3, fontSize: 11 }}>No approved scripts. Go to Scripts tab to approve some.</div>}
          {approved.map((s) => (
            <button key={s.id} onClick={() => setSelected(s.id)} style={{ background: selected === s.id ? bg3 : "transparent", color: selected === s.id ? txt1 : txt3, border: "none", borderBottom: selected === s.id ? `2px solid ${accent}` : "2px solid transparent", padding: "10px 14px", cursor: "pointer", fontFamily: font, fontSize: 11, whiteSpace: "nowrap", textAlign: "left", maxWidth: 200 }}>
              <div style={{ fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis" }}>{s.meta.topic}</div>
              <div style={{ fontSize: 9, color: txt3, marginTop: 2 }}>{s.scenes.length} scenes · {s.video.total_duration}s</div>
            </button>
          ))}
        </div>

        {/* scene-level editor */}
        {script && (
          <div style={{ padding: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: txt1 }}>{script.meta.topic}</div>
              <div style={{ display: "flex", gap: 6 }}>
                <Btn v="primary" onClick={() => startProduction(script.id)}>{I.play} Start Production</Btn>
                <Btn onClick={() => notify("Preview generating...")}>{I.eye} Preview</Btn>
              </div>
            </div>

            {/* timeline */}
            <div style={{ display: "flex", gap: 2, marginBottom: 14, padding: "6px 0" }}>
              {script.scenes.map((sc, idx) => {
                const pct = (sc.duration / script.video.total_duration) * 100;
                const colors = { hook: "#f59e0b", body: accent, transition: txt3, cta: "#10b981" };
                return (
                  <div key={idx} onClick={() => setSceneEdit(sceneEdit === idx ? null : idx)} title={`Scene #${sc.id}: ${sc.type} (${sc.duration}s)`}
                    style={{ height: 24, width: `${pct}%`, minWidth: 16, background: sceneEdit === idx ? `${colors[sc.type]}` : `${colors[sc.type]}66`, borderRadius: 3, cursor: "pointer", transition: "background 0.15s", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 8, color: "#fff", fontWeight: 600 }}>
                    {sc.duration}s
                  </div>
                );
              })}
            </div>

            {/* scene cards */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {script.scenes.map((sc, idx) => {
                const isExpanded = sceneEdit === idx;
                return (
                  <div key={idx} style={{ background: bg1, border: `1px solid ${isExpanded ? accent : border}`, borderRadius: 8, overflow: "hidden", transition: "border 0.15s" }}>
                    {/* scene header */}
                    <div onClick={() => setSceneEdit(isExpanded ? null : idx)} style={{ display: "grid", gridTemplateColumns: "40px 60px 1fr 100px 100px 100px 40px", alignItems: "center", gap: 8, padding: "8px 12px", cursor: "pointer" }}
                      onMouseEnter={(e) => !isExpanded && (e.currentTarget.style.background = `${bg3}44`)}
                      onMouseLeave={(e) => !isExpanded && (e.currentTarget.style.background = "transparent")}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: accent }}>#{sc.id}</span>
                      <Badge status={sc.type} small />
                      <div style={{ fontSize: 10, color: txt2, overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis" }}>{sc.narration.slice(0, 50)}...</div>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <div style={{ width: 20, height: 14, borderRadius: 2, background: sc.asset_preview || `${bg3}` }} />
                        <span style={{ fontSize: 9, color: sc.asset_source ? "#10b981" : txt3 }}>{sc.asset_source || "none"}</span>
                      </div>
                      <span style={{ fontSize: 9, color: sc.audio_generated ? "#10b981" : txt3 }}>{sc.audio_generated ? "✓ Audio" : "○ Audio"}</span>
                      <span style={{ fontSize: 9, color: txt3 }}>{sc.duration}s · {sc.transition_out}</span>
                      <span style={{ color: txt3, transition: "transform 0.2s", transform: isExpanded ? "rotate(90deg)" : "rotate(0)" }}>{I.arrow}</span>
                    </div>

                    {/* expanded editor */}
                    {isExpanded && (
                      <div style={{ padding: "12px 14px", borderTop: `1px solid ${border}`, background: `${bg0}88` }}>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
                          {/* visual */}
                          <div>
                            <div style={{ fontSize: 10, fontWeight: 600, color: txt2, marginBottom: 6, display: "flex", alignItems: "center", gap: 4 }}>{I.image} VISUAL ASSET</div>
                            <div style={{ background: sc.asset_preview || bg3, height: 100, borderRadius: 6, border: `1px solid ${border}`, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 8 }}>
                              <span style={{ fontSize: 28, opacity: 0.4 }}>{sc.asset_source === "veo" ? "🎬" : sc.asset_source === "pexels" ? "📦" : "?"}</span>
                            </div>
                            <div style={{ display: "flex", gap: 4 }}>
                              <Btn v="primary" onClick={() => openAssetBrowser(idx, "video")}>{I.swap} Replace from Asset DB</Btn>
                              <Btn v="accent" onClick={() => notify(`Generating Veo clip for scene #${sc.id}...`)}>{I.generate} Gen Veo</Btn>
                              <Btn onClick={() => notify("Search Pexels...")}>{I.scraper} Pexels</Btn>
                            </div>
                            <div style={{ marginTop: 8 }}>
                              <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 2 }}>VISUAL HINT</label>
                              <Input value={sc.visual_hint} onChange={(v) => {
                                setScripts((prev) => prev.map((s) => {
                                  if (s.id !== script.id) return s;
                                  const scenes = [...s.scenes]; scenes[idx] = { ...scenes[idx], visual_hint: v };
                                  return { ...s, scenes };
                                }));
                              }} />
                            </div>
                          </div>

                          {/* audio */}
                          <div>
                            <div style={{ fontSize: 10, fontWeight: 600, color: txt2, marginBottom: 6, display: "flex", alignItems: "center", gap: 4 }}>{I.mic} AUDIO / TTS</div>
                            <div style={{ background: bg3, height: 48, borderRadius: 6, border: `1px solid ${border}`, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 8 }}>
                              {sc.audio_generated
                                ? <div style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ color: "#10b981" }}>{I.check}</span><span style={{ fontSize: 10, color: "#10b981" }}>Audio ready ({sc.duration}s)</span></div>
                                : <span style={{ fontSize: 10, color: txt3 }}>Not generated</span>}
                            </div>
                            <div style={{ display: "flex", gap: 4, marginBottom: 8 }}>
                              <Btn v="primary" onClick={() => regenerateAudio(idx)}>{I.retry} Regenerate TTS</Btn>
                              <Btn onClick={() => notify("Upload custom audio...")}>{I.upload} Upload Audio</Btn>
                            </div>
                            <div>
                              <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 2 }}>NARRATION TEXT</label>
                              <Input multiline rows={3} value={sc.narration} onChange={(v) => {
                                setScripts((prev) => prev.map((s) => {
                                  if (s.id !== script.id) return s;
                                  const scenes = [...s.scenes]; scenes[idx] = { ...scenes[idx], narration: v, audio_generated: false };
                                  return { ...s, scenes };
                                }));
                              }} />
                            </div>

                            {/* overlay */}
                            <div style={{ marginTop: 8 }}>
                              <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 2 }}>TEXT OVERLAY</label>
                              <div style={{ display: "flex", gap: 6 }}>
                                <Input value={sc.text_overlay} onChange={(v) => {
                                  setScripts((prev) => prev.map((s) => {
                                    if (s.id !== script.id) return s;
                                    const scenes = [...s.scenes]; scenes[idx] = { ...scenes[idx], text_overlay: v };
                                    return { ...s, scenes };
                                  }));
                                }} style={{ flex: 1 }} />
                                <Sel value={sc.overlay_style} onChange={(v) => {
                                  setScripts((prev) => prev.map((s) => {
                                    if (s.id !== script.id) return s;
                                    const scenes = [...s.scenes]; scenes[idx] = { ...scenes[idx], overlay_style: v };
                                    return { ...s, scenes };
                                  }));
                                }} options={OVERLAY_STYLES} />
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* scene controls */}
                        <div style={{ display: "flex", gap: 6, paddingTop: 8, borderTop: `1px solid ${border}` }}>
                          <Sel value={sc.type} onChange={(v) => {
                            setScripts((prev) => prev.map((s) => {
                              if (s.id !== script.id) return s;
                              const scenes = [...s.scenes]; scenes[idx] = { ...scenes[idx], type: v };
                              return { ...s, scenes };
                            }));
                          }} options={SCENE_TYPES} />
                          <Sel value={sc.duration} onChange={(v) => {
                            setScripts((prev) => prev.map((s) => {
                              if (s.id !== script.id) return s;
                              const scenes = [...s.scenes]; scenes[idx] = { ...scenes[idx], duration: +v };
                              return { ...s, scenes };
                            }));
                          }} options={Array.from({ length: 20 }, (_, i) => ({ value: i + 1, label: `${i + 1}s` }))} />
                          <Sel value={sc.transition_out} onChange={(v) => {
                            setScripts((prev) => prev.map((s) => {
                              if (s.id !== script.id) return s;
                              const scenes = [...s.scenes]; scenes[idx] = { ...scenes[idx], transition_out: v };
                              return { ...s, scenes };
                            }));
                          }} options={TRANSITION_TYPES} />
                          <div style={{ flex: 1 }} />
                          <Btn v="danger" onClick={() => {
                            setScripts((prev) => prev.map((s) => {
                              if (s.id !== script.id) return s;
                              return { ...s, scenes: s.scenes.filter((_, i) => i !== idx).map((sc, i) => ({ ...sc, id: i + 1 })) };
                            }));
                            setSceneEdit(null);
                          }}>{I.trash} Remove Scene</Btn>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </Card>

      {/* asset browser modal */}
      <Modal open={assetBrowser} onClose={() => setAssetBrowser(false)} title="Asset Browser — Select Replacement Clip" width={800}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", gap: 6 }}>
            <Input placeholder="Search keywords..." style={{ flex: 1 }} value="" onChange={() => {}} />
            <Sel value="all" onChange={() => {}} options={[{ value: "all", label: "All Sources" }, "pexels", "veo", "manual"]} />
            <Sel value="all" onChange={() => {}} options={[{ value: "all", label: "All Niches" }, ...NICHES]} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, maxHeight: 400, overflowY: "auto" }}>
            {mockAssets.map((a) => (
              <div key={a.id} onClick={() => selectAsset(a)} style={{ background: a.preview_color, borderRadius: 8, height: 120, cursor: "pointer", border: `2px solid transparent`, display: "flex", flexDirection: "column", justifyContent: "flex-end", padding: 8, transition: "border 0.15s" }}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = accent)}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = "transparent")}>
                <div style={{ background: "#000000aa", borderRadius: 4, padding: "4px 6px" }}>
                  <div style={{ fontSize: 9, color: "#fff", fontWeight: 600 }}>{a.source} · {a.duration}s · Q:{a.quality.toFixed(1)}</div>
                  <div style={{ fontSize: 8, color: "#ffffff88" }}>{a.keywords.join(", ")}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// REMAINING TABS (Pipeline, Uploads, LLM, Performance, Health)
// ═══════════════════════════════════════════════════════════════════════════════

function genPipelineJobs(n = 20) {
  const sts = ["queued", "scripting", "producing", "rendering", "uploading", "completed", "failed"];
  return Array.from({ length: n }, (_, i) => {
    const s = i < 2 ? "completed" : i < 4 ? "failed" : pick(sts);
    return { id: `job_${uid()}`, topic: pick(SAMPLE_TOPICS_VN), niche: pick(NICHES), template: pick(TEMPLATES), llm: pick(["local", "gemini"]), status: s, progress: s === "completed" ? 100 : s === "failed" ? ri(10, 80) : s === "queued" ? 0 : ri(10, 95), startedAt: s !== "queued" ? new Date(Date.now() - ri(60000, 7200000)).toISOString() : null, duration: s === "completed" ? ri(90, 240) : null, error: s === "failed" ? pick(["NVENC timeout", "Pexels 429", "Whisper OOM"]) : null };
  });
}

// default channel mapping by template
const TEMPLATE_DEFAULT_CHANNELS = {
  tiktok_viral: ["ch_4", "ch_5"],   // HealthHub + FitnessPro (TikTok)
  tiktok_30s:   ["ch_4"],            // HealthHub (TikTok)
  youtube_clean: ["ch_1", "ch_2"],   // MainChannel + LifestyleVN (YouTube)
  shorts_hook:  ["ch_1", "ch_3"],    // MainChannel + FinanceTips (YouTube)
};

function genUploads(n = 16) {
  const sts = ["scheduled", "uploading", "published", "failed", "ready"];
  return Array.from({ length: n }, () => {
    const template = pick(TEMPLATES);
    const niche = pick(NICHES);
    const status = pick(sts);
    const defaultChs = TEMPLATE_DEFAULT_CHANNELS[template] || ["ch_1"];
    return {
      id: `up_${uid()}`,
      template,
      niche,
      status,
      targetChannels: [...defaultChs],
      scheduledAt: new Date(Date.now() + ri(-86400000, 172800000)).toISOString(),
      title: pick(SAMPLE_TOPICS_VN),
      views: status === "published" ? ri(1000, 500000) : 0,
      er: status === "published" ? rf(0.5, 12) : 0,
      duration: ri(30, 180),
      renderTime: ri(90, 240),
    };
  });
}

function genPerf(days = 14) {
  return Array.from({ length: days }, (_, i) => {
    const d = new Date(); d.setDate(d.getDate() - (days - 1 - i));
    return { date: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }), videos: ri(30, 200), views: ri(50000, 800000), avgER: rf(1.5, 6.5), reindexed: ri(0, 15), lowPerf: ri(0, 10), revenue: rf(5, 120) };
  });
}

function PipelineTab({ jobs, setJobs, batchOn, setBatchOn, notify }) {
  const [filter, setFilter] = useState("all");
  const filtered = filter === "all" ? jobs : jobs.filter((j) => j.status === filter);
  const stats = useMemo(() => ({ c: jobs.filter((j) => j.status === "completed").length, f: jobs.filter((j) => j.status === "failed").length, a: jobs.filter((j) => !["completed", "failed", "queued"].includes(j.status)).length, q: jobs.filter((j) => j.status === "queued").length }), [jobs]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <StatBox label="Active" value={stats.a} color={accent} />
        <StatBox label="Queued" value={stats.q} color="#f59e0b" />
        <StatBox label="Completed" value={stats.c} color="#10b981" />
        <StatBox label="Failed" value={stats.f} color="#ef4444" />
      </div>
      <Card title="Batch Controls">
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <Btn v={batchOn ? "danger" : "success"} onClick={() => { setBatchOn(!batchOn); notify(batchOn ? "Batch paused" : "Batch resumed"); }}>{batchOn ? I.pause : I.play} {batchOn ? "Pause" : "Start"}</Btn>
          <Btn onClick={() => notify("Overnight batch queued")}>{I.play} Queue Overnight</Btn>
          <Btn v="danger" onClick={() => notify("All queued cancelled")}>{I.stop} Cancel Queued</Btn>
        </div>
      </Card>
      <Card title={`Jobs (${filtered.length})`} actions={
        <div style={{ display: "flex", gap: 3 }}>
          {["all", "queued", "scripting", "producing", "rendering", "completed", "failed"].map((f) => (
            <button key={f} onClick={() => setFilter(f)} style={{ background: filter === f ? "#1e40af" : "transparent", color: filter === f ? "#93c5fd" : txt3, border: "none", borderRadius: 4, padding: "2px 6px", fontSize: 9, cursor: "pointer", fontFamily: font, textTransform: "capitalize" }}>{f}</button>
          ))}
        </div>
      } noPad>
        <div style={{ maxHeight: 380, overflowY: "auto" }}>
          {filtered.map((j) => (
            <div key={j.id} style={{ display: "grid", gridTemplateColumns: "1fr 80px 70px 120px 70px", alignItems: "center", gap: 6, padding: "7px 14px", borderBottom: `1px solid ${border}` }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{j.topic}</div>
                <div style={{ fontSize: 9, color: txt3 }}>{j.niche} · {j.template}</div>
              </div>
              <Badge status={j.status} small />
              <span style={{ fontSize: 10, color: txt2 }}>{j.llm === "local" ? "Qwen" : "Gemini"}</span>
              <ProgressBar value={j.progress} color={SC[j.status]} />
              <div style={{ display: "flex", gap: 3, justifyContent: "flex-end" }}>
                {j.status === "failed" && <Btn v="primary" onClick={() => { setJobs((p) => p.map((x) => x.id === j.id ? { ...x, status: "queued", progress: 0, error: null } : x)); notify("Re-queued"); }}>{I.retry}</Btn>}
                {!["completed", "failed"].includes(j.status) && <Btn v="danger" onClick={() => { setJobs((p) => p.map((x) => x.id === j.id ? { ...x, status: "failed", error: "Cancelled" } : x)); notify("Cancelled"); }}>{I.x}</Btn>}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ── ChannelPicker: inline multi-select dropdown for target channels ──
function ChannelPicker({ channels, platformAuths, selected, onChange, notify }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const toggle = (chId) => {
    const next = selected.includes(chId) ? selected.filter((id) => id !== chId) : [...selected, chId];
    onChange(next);
  };

  const activeChannels = channels.filter((c) => c.status === "active");

  return (
    <div ref={ref} style={{ position: "relative", display: "inline-block" }}>
      <Btn v="ghost" onClick={() => setOpen(!open)} style={{ padding: "2px 6px", fontSize: 9 }}>
        {I.edit} Target
      </Btn>
      {open && (
        <div style={{ position: "absolute", top: "100%", left: 0, marginTop: 4, background: bg2, border: `1px solid ${border2}`, borderRadius: 8, padding: 6, zIndex: 100, minWidth: 220, boxShadow: "0 8px 30px #00000066" }}>
          <div style={{ fontSize: 9, color: txt3, padding: "4px 8px", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 2 }}>Select Target Channels</div>
          {activeChannels.map((ch) => {
            const pl = platformAuths.find((x) => x.id === ch.platform);
            const isSel = selected.includes(ch.id);
            return (
              <div key={ch.id} onClick={() => toggle(ch.id)} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", borderRadius: 5, cursor: "pointer", background: isSel ? `${accent}15` : "transparent", transition: "background 0.1s" }}
                onMouseEnter={(e) => !isSel && (e.currentTarget.style.background = `${bg3}88`)}
                onMouseLeave={(e) => !isSel && (e.currentTarget.style.background = "transparent")}>
                <div style={{ width: 16, height: 16, borderRadius: 4, border: isSel ? `2px solid ${accent}` : `2px solid ${txt3}`, background: isSel ? accent : "transparent", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  {isSel && <span style={{ color: "#fff", fontSize: 9, fontWeight: 800 }}>✓</span>}
                </div>
                <span style={{ fontSize: 12, color: pl?.color || txt3 }}>{pl?.icon}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 10, fontWeight: 600, color: txt1 }}>{ch.name}</div>
                  <div style={{ fontSize: 8, color: txt3 }}>{ch.platform} · {ch.subs?.toLocaleString()} subs</div>
                </div>
              </div>
            );
          })}
          {activeChannels.length === 0 && <div style={{ padding: 8, fontSize: 10, color: txt3 }}>No active channels</div>}
          <div style={{ borderTop: `1px solid ${border}`, marginTop: 4, paddingTop: 4, display: "flex", gap: 4 }}>
            <Btn v="ghost" onClick={() => { onChange(activeChannels.map((c) => c.id)); }} style={{ fontSize: 9, flex: 1 }}>All</Btn>
            <Btn v="ghost" onClick={() => { onChange([]); }} style={{ fontSize: 9, flex: 1 }}>None</Btn>
            <Btn v="primary" onClick={() => { setOpen(false); notify(`${selected.length} channels targeted`); }} style={{ fontSize: 9, flex: 1 }}>Done</Btn>
          </div>
        </div>
      )}
    </div>
  );
}

function UploadTab({ uploads, setUploads, notify }) {
  const [pf, setPf] = useState("all");
  const [authModal, setAuthModal] = useState(null);
  const [channelModal, setChannelModal] = useState(null);
  const [showSecrets, setShowSecrets] = useState({});
  const [subTab, setSubTab] = useState("queue");

  const pIcon = (p) => p === "youtube" ? "▶" : p === "tiktok" ? "♪" : "◎";
  const pColor = (p) => p === "youtube" ? "#ef4444" : p === "tiktok" ? "#e2e8f0" : "#e040fb";

  const [platformAuths, setPlatformAuths] = useState([
    {
      id: "youtube", name: "YouTube", icon: "▶", color: "#ef4444",
      authType: "oauth2", status: "connected",
      config: { client_id: "823451927364-abc123def456.apps.googleusercontent.com", client_secret: "GOCSPX-aBcDeFgHiJkLmNoPqRsTuVwXyZ", redirect_uri: "http://localhost:8080/oauth/youtube/callback", scopes: ["youtube.upload", "youtube.readonly", "youtube.force-ssl"], token_endpoint: "https://oauth2.googleapis.com/token", auth_endpoint: "https://accounts.google.com/o/oauth2/v2/auth" },
      tokens: { access_token: "ya29.a0AfH6SMBxyz123456789abcdefghijk", refresh_token: "1//0eXyZaBcDeFgHiJkLm", expires_at: new Date(Date.now() + 2400000).toISOString(), last_refreshed: new Date(Date.now() - 1800000).toISOString() },
      quotas: { label: "Daily Units", total: 10000, used: 3420, reset_at: "00:00 UTC" },
    },
    {
      id: "tiktok", name: "TikTok", icon: "♪", color: "#e2e8f0",
      authType: "oauth2", status: "connected",
      config: { client_key: "aw8j3k5m2n1p7q9r", client_secret: "TkSec-aBcDeFgHiJkLmNoPqRsTuV", redirect_uri: "http://localhost:8080/oauth/tiktok/callback", scopes: ["video.upload", "video.list", "user.info.basic"], token_endpoint: "https://open.tiktokapis.com/v2/oauth/token/", auth_endpoint: "https://www.tiktok.com/v2/auth/authorize/" },
      tokens: { access_token: "act.1234567890AbCdEfGhIjKlMnOpQrStUv", refresh_token: "rft.aBcDeFgHiJkLmNoPqRsTuVwXyZ", expires_at: new Date(Date.now() + 86400000).toISOString(), last_refreshed: new Date(Date.now() - 43200000).toISOString() },
      quotas: { label: "Daily Uploads", total: 50, used: 12, reset_at: "00:00 UTC" },
    },
    {
      id: "instagram", name: "Instagram Reels", icon: "◎", color: "#e040fb",
      authType: "oauth2", status: "expired",
      config: { app_id: "1234567890", app_secret: "abc123def456ghi789jkl012", redirect_uri: "http://localhost:8080/oauth/instagram/callback", scopes: ["instagram_content_publish", "instagram_basic", "pages_read_engagement"], token_endpoint: "https://graph.facebook.com/v18.0/oauth/access_token", auth_endpoint: "https://www.facebook.com/v18.0/dialog/oauth" },
      tokens: { access_token: "EAAGza1234567890abcdefghijklmnop", refresh_token: null, expires_at: new Date(Date.now() - 3600000).toISOString(), last_refreshed: new Date(Date.now() - 604800000).toISOString() },
      quotas: { label: "Daily Uploads", total: 25, used: 0, reset_at: "00:00 UTC" },
    },
  ]);

  const [channels, setChannels] = useState([
    { id: "ch_1", name: "MainChannel", platform: "youtube", email: "main@aimedia.vn", category: "22", lang: "vi", monetized: true, status: "active", subs: 12400, videos: 284 },
    { id: "ch_2", name: "LifestyleVN", platform: "youtube", email: "lifestyle@aimedia.vn", category: "22", lang: "vi", monetized: true, status: "active", subs: 8700, videos: 156 },
    { id: "ch_3", name: "FinanceTips", platform: "youtube", email: "finance@aimedia.vn", category: "22", lang: "vi", monetized: false, status: "active", subs: 3200, videos: 89 },
    { id: "ch_4", name: "HealthHub", platform: "tiktok", email: "health@aimedia.vn", category: "health", lang: "vi", monetized: true, status: "active", subs: 45000, videos: 420 },
    { id: "ch_5", name: "FitnessPro", platform: "tiktok", email: "fitness@aimedia.vn", category: "fitness", lang: "vi", monetized: true, status: "active", subs: 21000, videos: 310 },
    { id: "ch_6", name: "LifeReels", platform: "instagram", email: "reels@aimedia.vn", category: "lifestyle", lang: "vi", monetized: false, status: "paused", subs: 1500, videos: 42 },
  ]);

  const filtered = useMemo(() => {
    if (pf === "all") return uploads;
    return uploads.filter((u) => {
      return (u.targetChannels || []).some((cid) => {
        const ch = channels.find((c) => c.id === cid);
        return ch && ch.platform === pf;
      });
    });
  }, [uploads, pf, channels]);

  const updateAuth = (pid, path, val) => {
    setPlatformAuths((prev) => prev.map((p) => {
      if (p.id !== pid) return p;
      const keys = path.split(".");
      if (keys.length === 2) {
        const [group, field] = keys;
        return { ...p, [group]: { ...p[group], [field]: val } };
      }
      return { ...p, [path]: val };
    }));
  };

  const toggleSecret = (k) => setShowSecrets((p) => ({ ...p, [k]: !p[k] }));
  const mask = (v, k) => {
    if (!v) return "—";
    return showSecrets[k] ? v : v.slice(0, 6) + "•".repeat(Math.min(v.length - 10, 16)) + v.slice(-4);
  };

  const tokenTTL = (exp) => {
    const d = new Date(exp) - Date.now();
    if (d <= 0) return { t: "EXPIRED", c: "#ef4444" };
    const m = Math.floor(d / 60000), h = Math.floor(m / 60);
    if (h > 24) return { t: `${Math.floor(h / 24)}d ${h % 24}h`, c: "#10b981" };
    if (h > 1) return { t: `${h}h ${m % 60}m`, c: h < 6 ? "#f59e0b" : "#10b981" };
    return { t: `${m}m`, c: "#ef4444" };
  };

  const SecretRow = ({ label, value, skey, pid, editable = true }) => (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 3 }}>
        <label style={{ fontSize: 9, color: txt3, textTransform: "uppercase", letterSpacing: "0.04em" }}>{label}</label>
        <div style={{ display: "flex", gap: 3 }}>
          <Btn v="ghost" onClick={() => toggleSecret(skey)} style={{ padding: "1px 5px", fontSize: 9 }}>{I.eye} {showSecrets[skey] ? "Hide" : "Show"}</Btn>
          <Btn v="ghost" onClick={() => notify("Copied")} style={{ padding: "1px 5px", fontSize: 9 }}>{I.copy}</Btn>
        </div>
      </div>
      {editable ? (
        <Input value={showSecrets[skey] ? (value || "") : mask(value, skey)} onChange={(v) => updateAuth(pid, skey.split(`${pid}.`)[1], v)} style={{ fontSize: 10, letterSpacing: "0.02em", background: bg0 }} />
      ) : (
        <div style={{ background: bg0, border: `1px solid ${border}`, borderRadius: 6, padding: "7px 10px", fontSize: 10, color: value ? txt2 : txt3, wordBreak: "break-all", letterSpacing: "0.02em" }}>{mask(value, skey)}</div>
      )}
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* platform overview */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        {platformAuths.map((p) => {
          const ttl = tokenTTL(p.tokens.expires_at);
          const platChannelIds = channels.filter((c) => c.platform === p.id).map((c) => c.id);
          const items = uploads.filter((u) => (u.targetChannels || []).some((cid) => platChannelIds.includes(cid)));
          return (
            <div key={p.id} onClick={() => setPf(pf === p.id ? "all" : p.id)} style={{ flex: 1, minWidth: 200, background: pf === p.id ? bg3 : bg2, border: `1px solid ${pf === p.id ? accent : border}`, borderRadius: 9, padding: 12, cursor: "pointer", transition: "all 0.15s" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 18, color: p.color }}>{p.icon}</span>
                  <span style={{ fontSize: 12, fontWeight: 600 }}>{p.name}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: p.status === "connected" ? "#10b981" : "#ef4444" }} />
                  <span style={{ fontSize: 9, color: p.status === "connected" ? "#10b981" : "#ef4444", fontWeight: 600, textTransform: "uppercase" }}>{p.status}</span>
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 3, fontSize: 10, color: txt3 }}>
                <span>Token: <span style={{ color: ttl.c, fontWeight: 600 }}>{ttl.t}</span></span>
                <span>Auth: {p.authType.toUpperCase()}</span>
                <span>{items.filter((u) => u.status === "published").length} published</span>
                <span>{items.filter((u) => u.status === "scheduled").length} scheduled</span>
              </div>
              <div style={{ marginTop: 5 }}>
                <ProgressBar value={(p.quotas.used / p.quotas.total) * 100} color={p.quotas.used / p.quotas.total > 0.8 ? "#f59e0b" : accent} h={3} />
                <div style={{ fontSize: 8, color: txt3, marginTop: 2 }}>{p.quotas.label}: {p.quotas.used}/{p.quotas.total}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* sub tabs */}
      <div style={{ display: "flex", borderBottom: `1px solid ${border}` }}>
        {[{ id: "queue", label: "Videos", ct: filtered.length }, { id: "auth", label: "Auth & Credentials" }, { id: "channels", label: "Channels" }].map((t) => (
          <button key={t.id} onClick={() => setSubTab(t.id)} style={{ background: "none", border: "none", color: subTab === t.id ? txt1 : txt3, padding: "8px 14px", cursor: "pointer", fontSize: 11, fontFamily: font, borderBottom: subTab === t.id ? `2px solid ${accent}` : "2px solid transparent", display: "flex", alignItems: "center", gap: 4 }}>
            {t.label}
            {t.ct != null && <span style={{ background: `${accent}30`, color: accent, padding: "1px 5px", borderRadius: 4, fontSize: 9, fontWeight: 600 }}>{t.ct}</span>}
          </button>
        ))}
      </div>

      {/* ── VIDEOS ── */}
      {subTab === "queue" && (<>
        <Card title="Upload Controls">
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <Btn v="primary" onClick={() => notify("Uploading all ready...")}>{I.upload} Upload All Ready</Btn>
            <Btn onClick={() => notify("Optimizing schedule...")}>{I.retry} Optimize Schedule</Btn>
            <Btn onClick={() => { setPlatformAuths((prev) => prev.map((p) => ({ ...p, tokens: { ...p.tokens, last_refreshed: new Date().toISOString(), expires_at: new Date(Date.now() + 86400000).toISOString() }, status: "connected" }))); notify("All tokens refreshed"); }}>{I.retry} Refresh All Tokens</Btn>
            <Btn v="danger" onClick={() => notify("All paused")}>{I.pause} Pause All</Btn>
          </div>
        </Card>
        <Card title={`Production Videos (${filtered.length})`} noPad>
          {/* header row */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 70px 70px auto 80px 50px 70px", alignItems: "center", gap: 6, padding: "6px 14px", borderBottom: `1px solid ${border}`, background: bg1 }}>
            <span style={{ fontSize: 9, color: txt3, textTransform: "uppercase", letterSpacing: "0.05em" }}>Title / Template</span>
            <span style={{ fontSize: 9, color: txt3, textTransform: "uppercase", letterSpacing: "0.05em" }}>Status</span>
            <span style={{ fontSize: 9, color: txt3, textTransform: "uppercase", letterSpacing: "0.05em" }}>Niche</span>
            <span style={{ fontSize: 9, color: txt3, textTransform: "uppercase", letterSpacing: "0.05em" }}>Target Channels</span>
            <span style={{ fontSize: 9, color: txt3, textTransform: "uppercase", letterSpacing: "0.05em" }}>Schedule</span>
            <span style={{ fontSize: 9, color: txt3, textTransform: "uppercase", letterSpacing: "0.05em" }}>Views</span>
            <span style={{ fontSize: 9, color: txt3, textTransform: "uppercase", letterSpacing: "0.05em", textAlign: "right" }}>Actions</span>
          </div>
          <div style={{ maxHeight: 440, overflowY: "auto" }}>
            {filtered.sort((a, b) => new Date(a.scheduledAt) - new Date(b.scheduledAt)).map((u) => {
              const canEditTarget = !["uploading", "published"].includes(u.status);
              const targetChs = (u.targetChannels || []).map((cid) => channels.find((c) => c.id === cid)).filter(Boolean);
              return (
                <div key={u.id} style={{ display: "grid", gridTemplateColumns: "1fr 70px 70px auto 80px 50px 70px", alignItems: "center", gap: 6, padding: "8px 14px", borderBottom: `1px solid ${border}`, transition: "background 0.1s" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = `${bg3}44`)}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                  {/* title + template */}
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{u.title}</div>
                    <div style={{ fontSize: 9, color: txt3, marginTop: 1 }}>{u.template} · {u.duration}s</div>
                  </div>
                  {/* status */}
                  <Badge status={u.status} small />
                  {/* niche */}
                  <span style={{ fontSize: 10, color: txt2, textTransform: "capitalize" }}>{u.niche}</span>
                  {/* target channels */}
                  <div style={{ display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap" }}>
                    {targetChs.map((ch) => {
                      const pl = platformAuths.find((x) => x.id === ch.platform);
                      return (
                        <span key={ch.id} style={{ display: "inline-flex", alignItems: "center", gap: 3, padding: "2px 6px", borderRadius: 4, background: `${pl?.color || txt3}15`, border: `1px solid ${pl?.color || txt3}30`, fontSize: 9, color: pl?.color || txt2, whiteSpace: "nowrap" }}>
                          <span style={{ fontSize: 10 }}>{pl?.icon}</span>
                          {ch.name}
                        </span>
                      );
                    })}
                    {targetChs.length === 0 && <span style={{ fontSize: 9, color: txt3, fontStyle: "italic" }}>No target</span>}
                    {canEditTarget && (
                      <ChannelPicker
                        channels={channels}
                        platformAuths={platformAuths}
                        selected={u.targetChannels || []}
                        onChange={(newChs) => setUploads((prev) => prev.map((x) => x.id === u.id ? { ...x, targetChannels: newChs } : x))}
                        notify={notify}
                      />
                    )}
                  </div>
                  {/* schedule */}
                  <span style={{ fontSize: 10, color: txt3 }}>
                    {new Date(u.scheduledAt).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                    <span style={{ display: "block", fontSize: 8, color: txt3 }}>{new Date(u.scheduledAt).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}</span>
                  </span>
                  {/* views */}
                  <span style={{ fontSize: 10, color: u.views > 0 ? txt1 : txt3, fontWeight: u.views > 0 ? 600 : 400 }}>
                    {u.views > 0 ? `${(u.views / 1000).toFixed(0)}K` : "—"}
                  </span>
                  {/* actions */}
                  <div style={{ display: "flex", gap: 3, justifyContent: "flex-end" }}>
                    {(u.status === "scheduled" || u.status === "ready") && <Btn v="primary" onClick={() => { setUploads((p) => p.map((x) => x.id === u.id ? { ...x, status: "uploading" } : x)); notify("Uploading..."); }}>{I.play}</Btn>}
                    {u.status === "failed" && <Btn v="primary" onClick={() => { setUploads((p) => p.map((x) => x.id === u.id ? { ...x, status: "scheduled" } : x)); notify("Re-scheduled"); }}>{I.retry}</Btn>}
                    <Btn v="danger" onClick={() => { setUploads((prev) => prev.filter((x) => x.id !== u.id)); notify("Video removed"); }}>{I.trash}</Btn>
                  </div>
                </div>
              );
            })}
            {filtered.length === 0 && <div style={{ padding: 20, textAlign: "center", color: txt3, fontSize: 11 }}>No production videos yet</div>}
          </div>
        </Card>
      </>)}

      {/* ── AUTH & CREDENTIALS ── */}
      {subTab === "auth" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {platformAuths.map((p) => {
            const ttl = tokenTTL(p.tokens.expires_at);
            const isOpen = authModal === p.id;
            return (
              <Card key={p.id} title={
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 16, color: p.color }}>{p.icon}</span>
                  <span>{p.name}</span>
                  <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 4, background: p.status === "connected" ? "#10b98120" : "#ef444420", color: p.status === "connected" ? "#10b981" : "#ef4444", fontWeight: 600 }}>{p.status.toUpperCase()}</span>
                </div>
              } actions={
                <div style={{ display: "flex", gap: 4 }}>
                  <Btn v="ghost" onClick={() => setAuthModal(isOpen ? null : p.id)}>{isOpen ? "Collapse" : "Configure"} {isOpen ? I.arrowUp : I.arrowDown}</Btn>
                  {p.status === "expired" && <Btn v="primary" onClick={() => { updateAuth(p.id, "status", "connected"); updateAuth(p.id, "tokens.expires_at", new Date(Date.now() + 86400000).toISOString()); notify(`${p.name} re-authorized`); }}>{I.retry} Re-authorize</Btn>}
                  <Btn onClick={() => { updateAuth(p.id, "tokens.last_refreshed", new Date().toISOString()); updateAuth(p.id, "tokens.expires_at", new Date(Date.now() + 86400000).toISOString()); updateAuth(p.id, "status", "connected"); notify(`${p.name} token refreshed`); }}>{I.retry} Refresh</Btn>
                </div>
              }>
                {/* token status — always visible */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8, marginBottom: isOpen ? 12 : 0 }}>
                  <div style={{ background: bg1, borderRadius: 7, padding: 9, border: `1px solid ${border}` }}>
                    <div style={{ fontSize: 9, color: txt3 }}>TOKEN EXPIRES</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: ttl.c, marginTop: 2 }}>{ttl.t}</div>
                    <div style={{ fontSize: 8, color: txt3, marginTop: 1 }}>{new Date(p.tokens.expires_at).toLocaleString()}</div>
                  </div>
                  <div style={{ background: bg1, borderRadius: 7, padding: 9, border: `1px solid ${border}` }}>
                    <div style={{ fontSize: 9, color: txt3 }}>LAST REFRESHED</div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: txt1, marginTop: 3 }}>{new Date(p.tokens.last_refreshed).toLocaleTimeString()}</div>
                    <div style={{ fontSize: 8, color: txt3, marginTop: 1 }}>{new Date(p.tokens.last_refreshed).toLocaleDateString()}</div>
                  </div>
                  <div style={{ background: bg1, borderRadius: 7, padding: 9, border: `1px solid ${border}` }}>
                    <div style={{ fontSize: 9, color: txt3 }}>AUTH TYPE</div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: txt1, marginTop: 3 }}>{p.authType.toUpperCase()}</div>
                    <div style={{ fontSize: 8, color: txt3, marginTop: 1 }}>{p.config.scopes?.length || 0} scopes</div>
                  </div>
                  <div style={{ background: bg1, borderRadius: 7, padding: 9, border: `1px solid ${border}` }}>
                    <div style={{ fontSize: 9, color: txt3 }}>QUOTA</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: p.quotas.used / p.quotas.total > 0.8 ? "#f59e0b" : "#10b981", marginTop: 2 }}>{p.quotas.used}/{p.quotas.total}</div>
                    <div style={{ fontSize: 8, color: txt3, marginTop: 1 }}>{p.quotas.label} · resets {p.quotas.reset_at}</div>
                  </div>
                </div>

                {/* expanded config */}
                {isOpen && (
                  <div style={{ borderTop: `1px solid ${border}`, paddingTop: 12 }}>
                    {/* OAuth Credentials */}
                    <div style={{ fontSize: 10, fontWeight: 700, color: txt2, marginBottom: 10, display: "flex", alignItems: "center", gap: 5 }}>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
                      OAuth App Credentials
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
                      <div>
                        {p.id === "youtube" && <SecretRow label="Client ID" value={p.config.client_id} skey={`${p.id}.config.client_id`} pid={p.id} />}
                        {p.id === "youtube" && <SecretRow label="Client Secret" value={p.config.client_secret} skey={`${p.id}.config.client_secret`} pid={p.id} />}
                        {p.id === "tiktok" && <SecretRow label="Client Key" value={p.config.client_key} skey={`${p.id}.config.client_key`} pid={p.id} />}
                        {p.id === "tiktok" && <SecretRow label="Client Secret" value={p.config.client_secret} skey={`${p.id}.config.client_secret`} pid={p.id} />}
                        {p.id === "instagram" && <SecretRow label="App ID" value={p.config.app_id} skey={`${p.id}.config.app_id`} pid={p.id} />}
                        {p.id === "instagram" && <SecretRow label="App Secret" value={p.config.app_secret} skey={`${p.id}.config.app_secret`} pid={p.id} />}
                      </div>
                      <div>
                        <div style={{ marginBottom: 8 }}>
                          <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3, textTransform: "uppercase", letterSpacing: "0.04em" }}>Redirect URI</label>
                          <Input value={p.config.redirect_uri} onChange={(v) => updateAuth(p.id, "config.redirect_uri", v)} style={{ fontSize: 10 }} />
                        </div>
                        <div>
                          <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3, textTransform: "uppercase", letterSpacing: "0.04em" }}>Scopes</label>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                            {p.config.scopes?.map((s, i) => <span key={i} style={{ background: `${accent}18`, color: accent, padding: "2px 6px", borderRadius: 4, fontSize: 9 }}>{s}</span>)}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Active Tokens */}
                    <div style={{ fontSize: 10, fontWeight: 700, color: txt2, marginBottom: 10, display: "flex", alignItems: "center", gap: 5 }}>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 11-7.778 7.778 5.5 5.5 0 017.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
                      Active Tokens
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
                      <SecretRow label="Access Token" value={p.tokens.access_token} skey={`${p.id}.tokens.access_token`} pid={p.id} editable={false} />
                      <SecretRow label="Refresh Token" value={p.tokens.refresh_token || "(none — long-lived token)"} skey={`${p.id}.tokens.refresh_token`} pid={p.id} editable={false} />
                    </div>

                    {/* API Endpoints */}
                    <div style={{ fontSize: 10, fontWeight: 700, color: txt2, marginBottom: 10, display: "flex", alignItems: "center", gap: 5 }}>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>
                      API Endpoints
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
                      <div>
                        <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3, textTransform: "uppercase" }}>Auth Endpoint</label>
                        <div style={{ background: bg0, border: `1px solid ${border}`, borderRadius: 6, padding: "7px 10px", fontSize: 10, color: txt2, wordBreak: "break-all" }}>{p.config.auth_endpoint}</div>
                      </div>
                      <div>
                        <label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3, textTransform: "uppercase" }}>Token Endpoint</label>
                        <div style={{ background: bg0, border: `1px solid ${border}`, borderRadius: 6, padding: "7px 10px", fontSize: 10, color: txt2, wordBreak: "break-all" }}>{p.config.token_endpoint}</div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div style={{ display: "flex", gap: 6, paddingTop: 10, borderTop: `1px solid ${border}`, flexWrap: "wrap" }}>
                      <Btn v="primary" onClick={() => notify(`Opening ${p.name} OAuth consent screen...`)}>
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                        Start OAuth Flow
                      </Btn>
                      <Btn onClick={() => { updateAuth(p.id, "tokens.last_refreshed", new Date().toISOString()); updateAuth(p.id, "tokens.expires_at", new Date(Date.now() + 86400000).toISOString()); updateAuth(p.id, "status", "connected"); notify(`Token refreshed`); }}>{I.retry} Force Refresh</Btn>
                      <Btn onClick={() => notify(`Testing ${p.name} API...`)}>{I.check} Test Connection</Btn>
                      <Btn v="danger" onClick={() => { updateAuth(p.id, "status", "disconnected"); notify(`${p.name} disconnected`); }}>{I.x} Disconnect</Btn>
                      <div style={{ flex: 1 }} />
                      <Btn v="primary" onClick={() => notify("Credentials saved")}>{I.check} Save</Btn>
                    </div>
                  </div>
                )}
              </Card>
            );
          })}

          {/* .env reference */}
          <Card title="Environment Variables (.env)">
            <div style={{ background: bg0, borderRadius: 7, padding: 12, border: `1px solid ${border}`, fontSize: 10, lineHeight: 1.9, color: txt2 }}>
              <span style={{ color: "#10b981" }}># YouTube API</span><br />
              <span style={{ color: "#f59e0b" }}>YOUTUBE_CLIENT_ID</span>=<span style={{ color: txt3 }}>your_client_id</span><br />
              <span style={{ color: "#f59e0b" }}>YOUTUBE_CLIENT_SECRET</span>=<span style={{ color: txt3 }}>your_client_secret</span><br />
              <span style={{ color: "#f59e0b" }}>YOUTUBE_REDIRECT_URI</span>=<span style={{ color: txt3 }}>http://localhost:8080/oauth/youtube/callback</span><br />
              <br />
              <span style={{ color: "#10b981" }}># TikTok API</span><br />
              <span style={{ color: "#f59e0b" }}>TIKTOK_CLIENT_KEY</span>=<span style={{ color: txt3 }}>your_client_key</span><br />
              <span style={{ color: "#f59e0b" }}>TIKTOK_CLIENT_SECRET</span>=<span style={{ color: txt3 }}>your_client_secret</span><br />
              <span style={{ color: "#f59e0b" }}>TIKTOK_REDIRECT_URI</span>=<span style={{ color: txt3 }}>http://localhost:8080/oauth/tiktok/callback</span><br />
              <br />
              <span style={{ color: "#10b981" }}># Instagram / Meta API</span><br />
              <span style={{ color: "#f59e0b" }}>INSTAGRAM_APP_ID</span>=<span style={{ color: txt3 }}>your_app_id</span><br />
              <span style={{ color: "#f59e0b" }}>INSTAGRAM_APP_SECRET</span>=<span style={{ color: txt3 }}>your_app_secret</span><br />
              <span style={{ color: "#f59e0b" }}>INSTAGRAM_REDIRECT_URI</span>=<span style={{ color: txt3 }}>http://localhost:8080/oauth/instagram/callback</span><br />
              <br />
              <span style={{ color: "#10b981" }}># Gemini API (for Veo + LLM)</span><br />
              <span style={{ color: "#f59e0b" }}>GEMINI_API_KEY</span>=<span style={{ color: txt3 }}>your_gemini_api_key</span><br />
              <br />
              <span style={{ color: "#10b981" }}># Pexels API</span><br />
              <span style={{ color: "#f59e0b" }}>PEXELS_API_KEY</span>=<span style={{ color: txt3 }}>your_pexels_api_key</span><br />
            </div>
            <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
              <Btn onClick={() => notify("Exported to .env")}>{I.copy} Export .env</Btn>
              <Btn onClick={() => notify("Importing...")}>{I.upload} Import .env</Btn>
              <Btn onClick={() => notify("Validating...")}>{I.check} Validate All</Btn>
            </div>
          </Card>
        </div>
      )}

      {/* ── CHANNELS ── */}
      {subTab === "channels" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Card title="Channel Management" actions={
            <Btn v="primary" onClick={() => {
              const nc = { id: `ch_${uid()}`, name: "New Channel", platform: "youtube", email: "", category: "22", lang: "vi", monetized: false, status: "paused", subs: 0, videos: 0 };
              setChannels((prev) => [...prev, nc]);
              setChannelModal(nc);
              notify("Channel added");
            }}>{I.plus} Add Channel</Btn>
          }>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {channels.map((ch) => {
                const pl = platformAuths.find((x) => x.id === ch.platform);
                return (
                  <div key={ch.id} style={{ background: bg1, border: `1px solid ${border}`, borderRadius: 8, padding: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 18, color: pl?.color || txt3 }}>{pl?.icon || "?"}</span>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <span style={{ fontSize: 12, fontWeight: 600 }}>{ch.name}</span>
                          <span style={{ fontSize: 9, padding: "1px 5px", borderRadius: 3, background: ch.status === "active" ? "#10b98118" : "#f59e0b18", color: ch.status === "active" ? "#10b981" : "#f59e0b", fontWeight: 600 }}>{ch.status}</span>
                          {ch.monetized && <span style={{ fontSize: 9, padding: "1px 5px", borderRadius: 3, background: "#f59e0b18", color: "#f59e0b" }}>$</span>}
                        </div>
                        <div style={{ fontSize: 10, color: txt3, marginTop: 2 }}>{ch.platform} · {ch.email || "—"} · {ch.subs.toLocaleString()} subs · {ch.videos} vids</div>
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 4 }}>
                      <Btn v="primary" onClick={() => setChannelModal(ch)}>{I.edit}</Btn>
                      <Btn v="ghost" onClick={() => { setChannels((prev) => prev.map((c) => c.id === ch.id ? { ...c, status: c.status === "active" ? "paused" : "active" } : c)); notify(`${ch.name} ${ch.status === "active" ? "paused" : "activated"}`); }}>{ch.status === "active" ? I.pause : I.play}</Btn>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* default upload settings */}
          <Card title="Default Upload Settings">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
              {[
                { icon: "▶", color: "#ef4444", name: "YouTube", fields: ["Privacy: Public", "Category: 22 (People & Blogs)", "Language: Vietnamese", "Notify subs: Yes", "Embeddable: Yes", "Made for kids: No"] },
                { icon: "♪", color: "#e2e8f0", name: "TikTok", fields: ["Privacy: Public", "Comments: Enabled", "Duet: Enabled", "Stitch: Enabled", "Brand content: No", "Auto-caption: Yes"] },
                { icon: "◎", color: "#e040fb", name: "Instagram", fields: ["Share to Feed: Yes", "Location: None", "Cover: Auto (0s)", "Audio: Original", "Collaboration: Off"] },
              ].map((pl) => (
                <div key={pl.name} style={{ background: bg1, borderRadius: 8, padding: 12, border: `1px solid ${border}` }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                    <span style={{ fontSize: 14, color: pl.color }}>{pl.icon}</span>
                    <span style={{ fontSize: 11, fontWeight: 600 }}>{pl.name}</span>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 5, fontSize: 10 }}>
                    {pl.fields.map((f, i) => { const [k, v] = f.split(": "); return <div key={i}><span style={{ color: txt3 }}>{k}:</span> <span style={{ color: txt1 }}>{v}</span></div>; })}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* channel edit modal */}
      <Modal open={!!channelModal} onClose={() => setChannelModal(null)} title={channelModal ? `Edit: ${channelModal.name}` : ""} width={560}>
        {channelModal && (() => {
          const ch = channelModal;
          const up = (f, v) => { const u = { ...ch, [f]: v }; setChannelModal(u); setChannels((prev) => prev.map((c) => c.id === ch.id ? u : c)); };
          const pl = platformAuths.find((x) => x.id === ch.platform);
          const ttl = pl ? tokenTTL(pl.tokens.expires_at) : null;
          return (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div><label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3, textTransform: "uppercase" }}>Name</label><Input value={ch.name} onChange={(v) => up("name", v)} /></div>
                <div><label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3, textTransform: "uppercase" }}>Platform</label><Sel value={ch.platform} onChange={(v) => up("platform", v)} options={PLATFORMS.map((p) => ({ value: p, label: p }))} style={{ width: "100%" }} /></div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div><label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3, textTransform: "uppercase" }}>Email</label><Input value={ch.email} onChange={(v) => up("email", v)} placeholder="email@example.com" /></div>
                <div><label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3, textTransform: "uppercase" }}>Category</label><Input value={ch.category} onChange={(v) => up("category", v)} /></div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
                <div><label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3, textTransform: "uppercase" }}>Language</label><Sel value={ch.lang} onChange={(v) => up("lang", v)} options={[{ value: "vi", label: "Vietnamese" }, { value: "en", label: "English" }, { value: "th", label: "Thai" }]} style={{ width: "100%" }} /></div>
                <div><label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3, textTransform: "uppercase" }}>Status</label><Sel value={ch.status} onChange={(v) => up("status", v)} options={["active", "paused"]} style={{ width: "100%" }} /></div>
                <div><label style={{ fontSize: 9, color: txt3, display: "block", marginBottom: 3, textTransform: "uppercase" }}>Monetization</label><Sel value={ch.monetized ? "yes" : "no"} onChange={(v) => up("monetized", v === "yes")} options={[{ value: "yes", label: "Enabled" }, { value: "no", label: "Disabled" }]} style={{ width: "100%" }} /></div>
              </div>
              {/* platform link */}
              <div style={{ background: bg1, borderRadius: 7, padding: 10, border: `1px solid ${border}` }}>
                <div style={{ fontSize: 10, fontWeight: 600, color: txt2, marginBottom: 6 }}>Platform Connection</div>
                {pl ? (
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 16, color: pl.color }}>{pl.icon}</span>
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 600 }}>{pl.name} — <span style={{ color: pl.status === "connected" ? "#10b981" : "#ef4444" }}>{pl.status}</span></div>
                        <div style={{ fontSize: 9, color: txt3 }}>Token: <span style={{ color: ttl.c }}>{ttl.t}</span></div>
                      </div>
                    </div>
                    <Btn v="ghost" onClick={() => { setChannelModal(null); setSubTab("auth"); }}>Auth Settings {I.arrow}</Btn>
                  </div>
                ) : <div style={{ fontSize: 10, color: txt3 }}>Platform not configured yet.</div>}
              </div>
              <div style={{ display: "flex", gap: 6, justifyContent: "flex-end", paddingTop: 8, borderTop: `1px solid ${border}` }}>
                <Btn v="danger" onClick={() => { setChannels((prev) => prev.filter((c) => c.id !== ch.id)); setChannelModal(null); notify("Deleted"); }}>{I.trash} Delete</Btn>
                <div style={{ flex: 1 }} />
                <Btn v="ghost" onClick={() => setChannelModal(null)}>Cancel</Btn>
                <Btn v="primary" onClick={() => { setChannelModal(null); notify("Saved"); }}>{I.check} Save</Btn>
              </div>
            </div>
          );
        })()}
      </Modal>
    </div>
  );
}

function LLMTab({ llmMode, setLlmMode, notify }) {
  const strats = [
    { id: "local", label: "100% Local", desc: "Qwen2.5 7B via Ollama", cost: "$0" },
    { id: "gemini", label: "100% Gemini", desc: "Gemini 2.5 Flash", cost: "~$1.80/mo" },
    { id: "auto", label: "Auto", desc: "Ollama up → Local, else Gemini", cost: "$0–1.80" },
    { id: "hybrid", label: "Hybrid ★", desc: "TikTok → Local · YouTube → Gemini", cost: "~$0.90" },
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <StatBox label="Mode" value={llmMode.toUpperCase()} color={accent2} />
        <StatBox label="Ollama" value="ONLINE" color="#10b981" sub=":11434 · Qwen2.5 7B" />
        <StatBox label="Gemini Quota" value={`${ri(80, 200)}/250`} color="#f59e0b" sub="RPD used today" />
        <StatBox label="Avg Latency" value="1.8s" color="#06b6d4" />
      </div>
      <Card title="LLM Mode">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          {strats.map((s) => (
            <div key={s.id} onClick={() => { setLlmMode(s.id); notify(`LLM → ${s.id}`); }} style={{ background: llmMode === s.id ? "#1e3a5f" : bg1, border: `1px solid ${llmMode === s.id ? accent : border}`, borderRadius: 8, padding: 12, cursor: "pointer" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontWeight: 600, fontSize: 12, color: llmMode === s.id ? "#93c5fd" : txt1 }}>{s.label}</span>
                <span style={{ fontSize: 10, color: "#10b981", fontWeight: 600 }}>{s.cost}</span>
              </div>
              <div style={{ fontSize: 10, color: txt3, marginTop: 3 }}>{s.desc}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function PerfTab({ perfData }) {
  const t = useMemo(() => ({ v: perfData.reduce((s, d) => s + d.videos, 0), vw: perfData.reduce((s, d) => s + d.views, 0), er: +(perfData.reduce((s, d) => s + d.avgER, 0) / perfData.length).toFixed(2), rev: +perfData.reduce((s, d) => s + d.revenue, 0).toFixed(2), ri: perfData.reduce((s, d) => s + d.reindexed, 0) }), [perfData]);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <StatBox label="14d Videos" value={t.v} color={accent} spark={<Sparkline data={perfData.map((d) => d.videos)} color={accent} />} />
        <StatBox label="Views" value={`${(t.vw / 1e6).toFixed(1)}M`} color={accent2} spark={<Sparkline data={perfData.map((d) => d.views)} color={accent2} />} />
        <StatBox label="Avg ER" value={`${t.er}%`} color="#10b981" spark={<Sparkline data={perfData.map((d) => d.avgER)} color="#10b981" />} />
        <StatBox label="Revenue" value={`$${t.rev}`} color="#f59e0b" spark={<Sparkline data={perfData.map((d) => d.revenue)} color="#f59e0b" />} />
        <StatBox label="Reindexed" value={t.ri} color="#06b6d4" sub="Score > 70" />
      </div>
      <Card title="Daily Output"><BarChart data={perfData} lk="date" vk="videos" color={accent} /></Card>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <Card title="Daily Views"><BarChart data={perfData} lk="date" vk="views" color={accent2} /></Card>
        <Card title="Revenue ($)"><BarChart data={perfData} lk="date" vk="revenue" color="#f59e0b" /></Card>
      </div>
      <Card title="Feedback Scoring">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
          <div style={{ background: bg1, borderRadius: 8, padding: 12, border: `1px solid ${border}` }}>
            <div style={{ fontSize: 10, color: txt3, marginBottom: 4 }}>FORMULA</div>
            <div style={{ fontSize: 10, color: txt1, lineHeight: 1.6 }}>er_score = ER × 10<br />reach_score = log10(views+1) × 20<br /><span style={{ color: accent, fontWeight: 600 }}>final = er×0.6 + reach×0.4</span></div>
          </div>
          <div style={{ background: bg1, borderRadius: 8, padding: 12, border: `1px solid #10b981` }}>
            <div style={{ fontSize: 10, color: "#10b981" }}>&gt;70 → REINDEX</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: "#10b981", marginTop: 4 }}>{t.ri}</div>
          </div>
          <div style={{ background: bg1, borderRadius: 8, padding: 12, border: `1px solid #ef4444` }}>
            <div style={{ fontSize: 10, color: "#ef4444" }}>&lt;40 → LOW PERF</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: "#ef4444", marginTop: 4 }}>{perfData.reduce((s, d) => s + d.lowPerf, 0)}</div>
          </div>
        </div>
      </Card>
    </div>
  );
}

function HealthTab() {
  const sys = useMemo(() => ({ cpu: ri(35, 78), gpu: ri(40, 92), ram: rf(18, 28), disk: rf(120, 380), nvenc: Math.random() > 0.05 ? "online" : "fallback", ollama: Math.random() > 0.1 ? "running" : "down", pg: "running", cdb: "running", uptime: "14d 7h 23m" }), []);
  const GaugeBar = ({ label, val, max, unit, warn = 80, crit = 95 }) => {
    const pct = (val / max) * 100; const c = pct >= crit ? "#ef4444" : pct >= warn ? "#f59e0b" : "#10b981";
    return <div style={{ marginBottom: 10 }}><div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, marginBottom: 3 }}><span style={{ color: txt2 }}>{label}</span><span style={{ color: c, fontWeight: 600 }}>{typeof val === "number" && val % 1 !== 0 ? val.toFixed(1) : val}{unit}/{max}{unit}</span></div><ProgressBar value={pct} color={c} h={7} /></div>;
  };
  const svcs = [
    { n: "PostgreSQL", p: ":5432", s: sys.pg }, { n: "ChromaDB", p: "file", s: sys.cdb },
    { n: "Ollama", p: ":11434", s: sys.ollama }, { n: "NVENC", p: "GPU", s: sys.nvenc === "online" ? "running" : "fallback" },
    { n: "Kokoro TTS", p: "CPU", s: "running" }, { n: "Whisper", p: "CPU", s: "running" },
    { n: "ffmpeg", p: "CLI", s: "running" }, { n: "Pexels API", p: "HTTPS", s: "running" },
  ];
  const crons = [
    { t: "06:50", n: "tracker.py --check-48h", s: "completed" }, { t: "07:00", n: "pipeline.py --scan", s: "completed" },
    { t: "07:30", n: "pipeline.py --index", s: "completed" }, { t: "08:00", n: "batch_runner.py --morning", s: "running" },
    { t: "13:00", n: "batch_runner.py --afternoon", s: "scheduled" }, { t: "22:00", n: "batch_runner.py --overnight", s: "scheduled" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <StatBox label="Uptime" value={sys.uptime} color="#10b981" />
        <StatBox label="NVENC" value={sys.nvenc === "online" ? "ONLINE" : "FALLBACK"} color={sys.nvenc === "online" ? "#10b981" : "#f59e0b"} sub="GTX 1660 Super" />
        <StatBox label="CPU" value={`${sys.cpu}%`} color={sys.cpu > 80 ? "#f59e0b" : "#10b981"} sub="Ryzen 9 · 16c" />
        <StatBox label="GPU" value={`${sys.gpu}%`} color={sys.gpu > 90 ? "#ef4444" : "#10b981"} sub="6 GB VRAM" />
      </div>
      <Card title="Resources">
        <GaugeBar label="CPU" val={sys.cpu} max={100} unit="%" />
        <GaugeBar label="GPU" val={sys.gpu} max={100} unit="%" />
        <GaugeBar label="RAM" val={sys.ram} max={32} unit=" GB" />
        <GaugeBar label="Disk" val={sys.disk} max={500} unit=" GB" warn={70} crit={90} />
      </Card>
      <Card title="Services">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 8 }}>
          {svcs.map((s) => (
            <div key={s.n} style={{ background: bg1, borderRadius: 7, padding: 10, border: `1px solid ${border}`, display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 7, height: 7, borderRadius: "50%", background: s.s === "running" ? "#10b981" : s.s === "fallback" ? "#f59e0b" : "#ef4444" }} />
              <div><div style={{ fontSize: 11, fontWeight: 600 }}>{s.n}</div><div style={{ fontSize: 9, color: txt3 }}>{s.p} · {s.s}</div></div>
            </div>
          ))}
        </div>
      </Card>
      <Card title="Cron Schedule" noPad>
        {crons.map((c, i) => (
          <div key={i} style={{ display: "grid", gridTemplateColumns: "50px 1fr 80px", alignItems: "center", gap: 8, padding: "7px 14px", borderBottom: `1px solid ${border}` }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: accent, fontVariantNumeric: "tabular-nums" }}>{c.t}</span>
            <span style={{ fontSize: 11, color: txt1 }}>{c.n}</span>
            <Badge status={c.s} small />
          </div>
        ))}
      </Card>
    </div>
  );
}
