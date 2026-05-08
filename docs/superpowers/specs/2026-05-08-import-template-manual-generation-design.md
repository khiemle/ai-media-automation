# Import Template — Manual Generation Mode Design

**Date:** 2026-05-08
**Status:** Approved

---

## Overview

Replace the auto-start behavior in Step 3 of the Import Template wizard with a fully manual generation UI. Step 3 no longer auto-starts on entry. Instead, it loads the item list in `pending` state and waits for user action. Users can trigger items individually, trigger all at once, or remove items before generation.

Scope: single file — `console/frontend/src/pages/YouTubeVideosPage.jsx`.

---

## Current Behavior (Step 3)

- On entry to Step 3, a `useEffect([step])` fires immediately and starts sequential generation (music first, then SFX items in order).
- No user interaction is possible during generation.
- On completion, auto-advances to Step 4.

---

## New Behavior (Step 3)

### Entry

Step 3 loads the item list in `pending` state. Nothing runs automatically. The `useEffect([step])` auto-start is removed.

### Header Row

A row above the item list:

```
▶ Start All     3 pending
```

- **"▶ Start All"** button — triggers all currently `pending` items sequentially (music first if present, then SFX in order). Enabled when ≥ 1 item is `pending`. Disabled/hidden when nothing is pending.
- **Pending count** — shows `N pending` while items remain. Hidden when all items are resolved.

### Item Row Controls

Each item row gains two new controls:

```
🎵  Study Focus · D Dorian    [pending]    [▶]  [✕]
🔊  Background Rain           [pending]    [▶]  [✕]
🔊  Rain Drop on Floor        [generating…]
🔊  Distant Wind Gust         [skipped]
```

**`▶` (Generate) button:**
- Triggers that item immediately, independent of any "Start All" run in progress.
- Enabled when item status is `pending` or `failed`.
- Disabled when `generating` or `done`.
- Not shown for `skipped` items.

**`✕` (Remove) button:**
- Removes the item from `genItems` entirely.
- Enabled when status is `pending` or `failed`.
- Disabled when `generating`.
- Not shown for `done` or `skipped` items.
- Removed items are excluded from `assembleSoundLayers` (they never appear in `genSfxResults`).

### Concurrency Rule

Individual `▶` clicks fire immediately regardless of whether "Start All" is also running. The "Start All" sequential loop skips any item that is already `generating` or `done` when it reaches that position.

### Footer Progression

| State | Footer |
|---|---|
| Any item is `generating` | Disabled "Generating… please wait" |
| Items are `pending` but none generating | "▶ Start All" (also in header) + `▶` per item |
| All items are `done` / `failed` / `skipped` / removed — nothing running or pending | **"Next →"** button appears |

"Next →" advances to Step 4 manually. Step 4 does not auto-appear.

### Modal Close Behavior

Same as before — cannot close while any item is `generating` (`onClose={step === 3 ? undefined : onClose}`).

---

## Step 4 — No Change

Step 4 is unchanged. Per-item listen (`PreviewPlayer`) and regenerate (`↺`) buttons remain. The "Apply to Video →" button is shown when at least one item succeeded.

---

## Implementation Notes

### Removed
- The `useEffect([step])` that auto-starts generation on Step 3 entry is removed entirely.

### Added
- `handleStartAll()` — iterates `genItems` where `status === 'pending'`, runs them sequentially using the same music-then-SFX order.
- `handleGenerateItem(genItem)` — generates a single item (music or SFX). Sets status to `generating`, calls the API, updates `genSfxResults` / `genMusicId` on success, marks `failed` on error.
- `handleRemoveItem(key)` — filters `genItems` removing the entry with that key.

### Footer logic change
Replace the current `step === 3` footer (single disabled button) with:

```js
if (step === 3) {
  const anyGenerating = genItems.some(it => it.status === 'generating')
  const anyPending    = genItems.some(it => it.status === 'pending')
  if (anyGenerating) return <Button disabled>Generating… please wait</Button>
  if (anyPending)    return <Button variant="primary" onClick={handleStartAll}>▶ Start All</Button>
  return <Button variant="primary" onClick={() => setStep(4)}>Next →</Button>
}
```

### Generation logic extraction
The current inline `run()` function inside the `useEffect` needs to be refactored into the two named handlers above so they can be called from button click handlers instead of only from the effect.

---

## Files Changed

| File | Change |
|---|---|
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | Remove auto-start effect; add `handleStartAll`, `handleGenerateItem`, `handleRemoveItem`; update `renderStep3` with header row and per-item buttons; update Step 3 footer logic |
