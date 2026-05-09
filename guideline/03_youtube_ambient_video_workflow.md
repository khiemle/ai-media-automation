# YouTube Ambient Video — End-to-End Workflow Guideline

> **Purpose:** Repeatable, failure-free steps for producing one "Soundscapes & Ambience" YouTube video — from theme selection through Queue Render in the AI Media Console.
>
> **Last updated:** 2026-05-09  
> **Tested on:** Rainy Tokyo Night session

---

## 🛑 HARD STOP RULE

**Claude's final action is completing Step 7 — confirming the YouTube draft item appears in the `/youtube` page list.**

Do **not** click "Queue Render →" or any render/submit button. The human operator reviews the draft and handles everything after that point.

---

## ⚠️ KNOWN IMPOSSIBILITIES — READ BEFORE STARTING

These steps are technically blocked in the current setup. Do **not** attempt them — they waste time with no working workaround.

| Step | Why it fails | What to do instead |
|------|-------------|-------------------|
| **Generate video in Runway** | Runway requires human login, CAPTCHA, and manual queue; cannot be automated | Claude enters the Runway Gen-4 prompt into the **Visual Prompt Node** only, then stops. Human attaches Image A to the Visual Image Node and runs the workflow. |
| **Upload Midjourney thumbnail image in the YouTube form** | Chrome CDP `Input.setFiles` is blocked by browser security. The SPA intercepts all static file routes. CORS workaround also fails. | Skip thumbnail image upload entirely. Fill **Thumbnail Text** only and proceed to Queue Render. |
| **Upload Video A to Assets Library (Step 5)** | Human-owned step — Claude does not handle this. | Human uploads Video A to `/assets` and creates Visual Asset A. |
| **Select Visual Asset A in the YouTube form** | Visual Asset A does not exist until the human completes Step 5. | Claude leaves this field blank. Human selects it after Step 5 is done. |

---

## TOOLS USED

| Tool | URL |
|------|-----|
| Midjourney | https://www.midjourney.com/imagine |
| Runway Workflows | https://app.runwayml.com/video-tools/teams/khiemlq/ai-tools/workflows |
| AI Media Console | http://192.168.68.119:3000 (**always use this IP, never localhost**) |

---

## INPUT REFERENCE

- Channel plan: `./docs/channels/Channel_Launch_Plan_Soundscapes.md`
- Working folder per video: `./working/<visual-name>/`

```
working/
  <visual-name>/
    json/
      YYYY-MM-DD_<channel>_<slug>_suno.json     ← music prompt
      YYYY-MM-DD_<channel>_<slug>_visual.json   ← scene + Runway + SFX
      YYYY-MM-DD_<channel>_<slug>_seo.json      ← title, description, tags, thumbnail
    images/
      <slug>_image_a.png     ← Midjourney output (Image A)
    videos/
      <slug>_video_a.mp4     ← Runway final output (Video A)
    md/                      ← session notes
```

---

## STEP 1 — Pick Theme & Generate JSON Files

1. Read `./docs/channels/Channel_Launch_Plan_Soundscapes.md` to select an appropriate theme for the current day/time.
2. Run the **`/visual-video`** skill.
3. The skill produces three JSON files — save them to `./working/<visual-name>/json/`:
   - `*_suno.json` — Suno music prompt
   - `*_visual.json` — scene description, Runway Gen-4 prompt, full SFX spec (16 layers)
   - `*_seo.json` — YouTube title, description, 40 tags, thumbnail text options

---

## STEP 2 — Create Thumbnail Image in Midjourney

1. Open the `*_visual.json` file and copy the **Midjourney prompt** field.
2. Go to **https://www.midjourney.com/imagine**.
3. Paste the prompt and generate.
4. Choose the **first image** from the results.
5. Download and save it to:
   ```
   ./working/<visual-name>/images/<slug>_image_a.png   ← this is Image A
   ```

---

## STEP 3 — Set Up Runway Workflow (Claude) + Run (Human)

**Claude's role — set up inputs only:**

1. Open **https://app.runwayml.com/video-tools/teams/khiemlq/ai-tools/workflows**.
2. Find the workflow named **"AI Loop Video"** and **duplicate it**.
3. Rename the duplicate to `<visual-name>`.
4. Open the new workflow.
5. In the **Visual Prompt Node**: paste the Runway Gen-4 prompt from `*_visual.json` → `runway_prompt`.

> **STOP HERE — hand off to human operator.**

**Human's role:**
- Attach **Image A** (`./working/<visual-name>/images/<slug>_image_a.png`) to the **Visual Image Node**.
- Run the workflow node by node and monitor generation.
- Download all output videos and save them to `./working/<visual-name>/videos/`.
- The final node output becomes **Video A**:
  ```
  ./working/<visual-name>/videos/<slug>_video_a.mp4   ← Video A
  ```

---

## STEP 4 — Verify AI Media Console is Available

1. Open **http://192.168.68.119:3000** (never use localhost).
2. Check the page loads and the dashboard is visible.
   - **Yes → proceed to Step 5.**
   - **No → stop and wait for human confirmation before continuing.**

### Login credentials
```
URL:      http://192.168.68.119:3000
Username: admin
Password: admin123
```

If the login page appears, sign in with the above credentials before proceeding.

---

## STEP 5 — Upload Video A to Assets Library *(Human handles this step)*

> **Claude skips this step entirely.** The human operator handles uploading Video A to the Assets Library.

**Human's role:**
1. Navigate to **http://192.168.68.119:3000/assets**.
2. Click **Import Asset**, attach **Video A**.
3. Fill in asset info (Title = visual name, Source = **Runway**), click **Import**.

The imported video becomes **Visual Asset A** — selectable inside the YouTube video form in Step 7.

---

## STEP 6 — Create YouTube Video Data

1. Navigate to **http://192.168.68.119:3000/youtube**.
2. In the left panel, **uncollapse Channel Plans**.
3. Select **Soundscapes & Ambience** channel.
4. Click **New Video** for this channel — the New Video form opens on the right.

### 6a — Fill Theme

Type the video theme into the **Theme** text box.

> ⚠️ **Type Theme LAST** (after SEO fields are filled) to avoid AI Autofill overwriting your SEO Title and Description — see Phase 7 note below.

### 6b — Import Template (JSON injection)

Click **Import Template**. The modal has three JSON paste areas: SEO JSON, SFX JSON, MUSIC JSON.

**File dialog is unreliable** (Chrome blocks `Input.setFiles`). Use the **Paste** method for each section.

> **JS injection pattern for React-controlled textareas** (use browser console or Chrome MCP javascript_tool):
> ```javascript
> const setter = Object.getOwnPropertyDescriptor(
>   window.HTMLTextAreaElement.prototype, 'value'
> ).set;
> setter.call(textareaElement, JSON.stringify(jsonData, null, 2));
> textareaElement.dispatchEvent(new Event('input', { bubbles: true }));
> textareaElement.dispatchEvent(new Event('change', { bubbles: true }));
> ```
> Using `element.value = ...` directly does **not** work with React — always use the native setter pattern above.

Inject in this order:
- **SEO JSON** → content of `*_seo.json`
- **SFX JSON** → content of `*_visual.json`
- **MUSIC JSON** → content of `*_suno.json`

### 6c — Generate and Start

After all three are injected:

1. Click **Next: Preview Plan**
2. Click **Generate Composition Plan**
3. Click **Next: Generate**
4. Click **Start All**
5. **Wait** until all 16 audio assets show Ready / green (1 music track + 15 SFX tracks)
6. Click **Next**
7. Click **Apply to Video**

---

## STEP 7 — Fill Remaining Video Fields

After Apply to Video, the form is populated. Verify and complete:

| Field | Value | Source |
|-------|-------|--------|
| **Theme** | e.g. "Rainy Tokyo Night" | Type last — see warning below |
| **Duration** | e.g. 3h | `meta.video_length_hours` in seo.json |
| **SEO Title** | Full recommended title | `seo.titles.recommended` |
| **SEO Description** | Full multi-section description | `seo.description.full` — inject via JS |
| **SEO Tags** | 40 comma-separated tags | `seo.tags.all` |
| **Thumbnail — Midjourney Image** | ~~Image A~~ | **SKIP — upload not possible. Leave blank.** |
| **Thumbnail Text** | e.g. "TOKYO NIGHT" | `seo.thumbnail.text_options[0].main_line` |
| **Visual Video** | ~~Select Visual Asset A~~ | **Human selects this after Step 5 is done** |
| **Music track** | Auto-filled from composition | Verify: 1 track ~600s |
| **SFX tracks** | Auto-filled from composition | Verify: 15 tracks |

### ⚠️ AI Autofill Warning — Theme Field

Typing in the **Theme** field triggers AI Autofill that **overwrites SEO Title and SEO Description** with generic content. To avoid this:

1. Fill SEO Title, SEO Description, and SEO Tags **first**.
2. Type Theme **last**.
3. After typing Theme, immediately verify:
   - SEO Title — if overwritten, triple-click the field and retype from `seo.titles.recommended`
   - SEO Description — if overwritten, re-inject the full description via JS injection pattern above

### Injecting the SEO Description

The full description is long and multi-line. Always inject via JS to avoid truncation:

```javascript
// Find the SEO Description textarea (adjust selector as needed)
const descTA = document.querySelector('[placeholder*="description" i], [data-field="seo_description"] textarea');
const setter = Object.getOwnPropertyDescriptor(
  window.HTMLTextAreaElement.prototype, 'value'
).set;
const fullDesc = `PASTE FULL DESCRIPTION FROM seo.description.full HERE`;
setter.call(descTA, fullDesc);
descTA.dispatchEvent(new Event('input', { bubbles: true }));
descTA.dispatchEvent(new Event('change', { bubbles: true }));
```

---

## STEP 8 — Verify Draft & Hand Off *(Claude's last step)*

### Verify the draft is saved

1. Navigate to **http://192.168.68.119:3000/youtube**.
2. Confirm the new video appears as a **draft item** in the list with the correct title.
3. Take a screenshot for confirmation.

### Final checklist — verify before handing off

- [ ] Theme filled
- [ ] Duration filled (e.g. 3h)
- [ ] SEO Title = full recommended title (not autofill generic version)
- [ ] SEO Description = full multi-section description (not autofill generic version)
- [ ] SEO Tags = 40 comma-separated tags
- [ ] Thumbnail Text filled (e.g. "TOKYO NIGHT")
- [ ] Thumbnail Image — intentionally skipped (blank is fine)
- [ ] Visual Video — left blank (human selects Visual Asset A after Step 5)
- [ ] Music track loaded (1 track)
- [ ] All 15 SFX tracks loaded
- [ ] Draft item visible in `/youtube` page list ✅

### 🛑 STOP HERE

**Do not click "Queue Render →" or any other action button.** Report to the human that the draft is ready, listing what is filled and what the human still needs to do (select Visual Asset A, then Queue Render).

---

## COMMON ERRORS & FIXES

| Error | Cause | Fix |
|-------|-------|-----|
| Login page shown | Session expired or first visit | Sign in: admin / admin123 |
| `"Theme is required"` on Queue Render | Theme field left empty | Type the theme name; then re-verify SEO Title/Description |
| SEO Title / Description overwritten | AI Autofill triggered by Theme field | Triple-click field, retype; for Description use JS injection |
| `"Not allowed"` on file upload | Chrome security blocks `Input.setFiles` | Skip image upload; Thumbnail Text only |
| Textarea injection does nothing | React synthetic event not triggered | Use native value setter pattern — not `element.value =` |
| `fetch('/image.png')` returns HTML | SPA catches all unknown routes | Do not serve static files through the app; skip image upload |
| Track generation stuck / error | Network or LLM timeout | Retry individual track from the UI |
| Console URL not reachable | Wrong URL used | Always use `http://192.168.68.119:3000` — never localhost |

---

## POST-UPLOAD TASKS (after video is live on YouTube)

From `*_seo.json`:

1. **Pin comment** — copy `pinned_comment.text` and post + pin as the first comment immediately after upload.
2. **End screen** — add Subscribe button, "Watch next" video, and Work Music Playlist per `end_screen.elements`.
3. **Cards** — add playlist card at `00:01:00` per `cards[]`.
4. **Chapter markers** — add timestamps from `chapter_markers[]` to the description.

---

## JSON KEY REFERENCE

### suno.json
| Key | Used for |
|-----|----------|
| `suno.style_of_music` | Suno music generation prompt |
| `suno.title` | Track name |
| `suno.exclude_styles` | Negative prompt |

### visual.json
| Key | Used for |
|-----|----------|
| `midjourney_prompt` | Step 2 — paste into Midjourney |
| `runway_prompt` | Step 3 — paste into Runway Visual Prompt Node |
| `scene.description` | Scene context reference |
| `sfx.background[]` | Background SFX layers |
| `sfx.midground[]` | Midground SFX layers |
| `sfx.foreground[]` | Foreground SFX layers |
| `sfx.random_sfx[]` | Random event SFX list |

### seo.json
| Key | Used for |
|-----|----------|
| `titles.recommended` | SEO Title field |
| `description.full` | SEO Description field (inject via JS) |
| `tags.all` | SEO Tags (comma-joined) |
| `thumbnail.text_options[0].main_line` | Thumbnail Text field |
| `pinned_comment.text` | Post-upload: pin as first comment |
| `chapter_markers[]` | Add to description after upload |

---

*End of guideline — update this file when new limitations or workarounds are discovered.*
