# Channel Launch Plan — Classical

> Kênh YouTube nhạc **classical instrumental gốc** — 100% nhạc do AI tạo (Suno chính, ElevenLabs dự phòng), không vocal, không cover. Dùng skill `music-video` để sản xuất data cho từng video.
> Cập nhật: 2026-05-15

---

## Mục lục

1. [Tổng quan kênh](#1-tổng-quan-kênh)
2. [Brand Identity](#2-brand-identity)
3. [Content Strategy — Theme Library](#3-content-strategy--theme-library)
4. [Đặc điểm âm thanh](#4-đặc-điểm-âm-thanh)
5. [Prompt Templates](#5-prompt-templates)
6. [SEO Templates](#6-seo-templates)
7. [Thumbnail & Visual Guidelines](#7-thumbnail--visual-guidelines)
8. [Production Pipeline — Step by Step](#8-production-pipeline--step-by-step)
9. [Tool Stack & Chi phí](#9-tool-stack--chi-phí)
10. [Automation Script — Hướng dẫn sử dụng](#10-automation-script--hướng-dẫn-sử-dụng)
11. [Content Calendar — 3 tháng đầu](#11-content-calendar--3-tháng-đầu)
12. [KPI & Success Metrics](#12-kpi--success-metrics)
13. [Monetization Checklist](#13-monetization-checklist)

---

## 1. Tổng quan kênh

| Tiêu chí | Classical |
|---|---|
| **Focus** | Nhạc classical instrumental gốc cho học tập, đọc sách, tập trung sâu, thư giãn |
| **Audience** | 18–55, sinh viên, knowledge workers, người đọc sách, độ tuổi rộng hơn lofi — "classical music for studying" là search term khổng lồ |
| **Video length** | 1–3 giờ compilation (chủ lực) · 30–60 phút mix · single piece 3–4 phút |
| **Upload frequency** | 3–4 video/tuần (1–2 compilation dài + 1 mix + single/Short luân phiên) |
| **RPM ước tính** | $5–$10 (audience lớn tuổi hơn, advertiser-friendly, geo US/UK/EU mạnh) |
| **Advertiser category** | Education, e-learning, productivity apps, finance, books/reading, wellness |
| **Music style** | Classical instrumental — solo piano, string quartet, piano trio, harpsichord/baroque chamber, string orchestra. Có form, có melody phát triển, dynamics thật (crescendo/diminuendo), rubato. KHÔNG drums, KHÔNG percussion, KHÔNG electronic, KHÔNG vocal |
| **Visual style** | Elegant + timeless — grand piano trong sảnh nắng, candlelit study với sách cũ, misty landscape, ornate concert room, sheet music trên giá. Painterly hoặc warm photoreal, low motion loop |
| **Time to monetize** | 3–5 tháng |
| **Launch order** | **Tháng 1** (cùng đợt với Lofi / Jazz / EDM, hoặc launch sau Lofi nếu chạy tuần tự) |

### Vì sao nhạc gốc instrumental — không cover

Pivot từ mô hình cover sang **nhạc gốc do AI tạo** (Suno/ElevenLabs):
- **Không Content ID, không license** — sáng tác gốc tạo bằng Suno Premier, bạn sở hữu output. Không có publisher claim, không cần sync license, không license vault.
- **Không rủi ro vocal/publicity** — instrumental thuần, không có giọng người thật → không dính ELVIS Act, NO FAKES Act, hay vấn đề consent.
- **Public domain là sân chơi rộng** — Chopin, Debussy, Bach, Satie và toàn bộ era cổ điển đã hết hạn bản quyền. Prompt mô tả lineage theo ERA/STYLE (Romantic-era nocturne, Baroque counterpoint), không tái tạo một tác phẩm cụ thể đã biết → an toàn tuyệt đối.
- **Scale dễ** — một identity nhạc → generate vô hạn piece. Không bị giới hạn bởi catalogue có sẵn.
- **Thị trường đã chứng minh** — các kênh "classical music for studying" lớn nhất chạy compilation 1–3 giờ, hàng triệu view mỗi video, audience cực kỳ loyal.

---

## 2. Brand Identity

**Tên kênh:** *(gợi ý, chọn 1)*
- `Lamplight Classical`
- `The Reading Room`
- `Nocturne Hall`
- `Quiet Conservatory`
- `Ivory & Dust`

**Tagline:** *"Timeless instrumental music to study, read, and focus to."*

**Brand colors:**
- Primary: Soft gold `#C9A24B`
- Secondary: Warm ivory `#F2E8D5`
- Accent: Muted slate blue `#6E7F9E` (dùng cho text trên thumbnail / chi tiết)
- Background: Deep warm charcoal `#1A1814`

**Brand voice:**
- Trang nhã, điềm tĩnh — như một thủ thư mời bạn vào một căn phòng yên tĩnh đầy sách
- Mô tả nhạc qua hình ảnh và cảm xúc ("a single piano line unfolding like candlelight on old pages")
- Không hype, không exclamation marks; tôn trọng truyền thống cổ điển nhưng vẫn ấm và dễ tiếp cận, không học thuật khô khan

**Channel art:**
- Avatar: minimal icon — một chiếc đàn grand piano nhìn nghiêng hoặc một ngọn nến, nền gold `#C9A24B`, icon ivory
- Banner: ảnh grand piano trong sảnh nắng hoặc study candlelit + tagline serif thanh lịch, safe area 1546×423

---

## 3. Content Strategy — Theme Library

Trên kênh nhạc gốc, "theme" không phải bài hát có sẵn — mà là **mood/concept** dùng làm brief cho skill `music-video`. Mỗi theme là một series identity: cùng sub-genre + harmonic era + tempo band + instrumentation, vary form/melody/mood theo từng piece.

#### Tier 1 — Core mood themes (Upload ưu tiên, 50%+ content)

| Theme | Title Formula | Function | Video Length |
|---|---|---|---|
| Romantic piano for studying | Classical Music for Studying · Romantic Piano · {N} Hour | Deep focus, học tập | 1–2h compilation |
| Baroque clarity for deep work | Baroque Music for Focus · {N} Hour of Bright Classical | Deep work, sáng/ngày | 1–2h compilation |
| Impressionist piano for reading | Classical Music for Reading · Impressionist Piano · {N} Hour | Đọc sách, thư giãn nhẹ | 1h mix |
| Cinematic strings for focus | Classical Music for Focus · Cinematic Strings · {N} Hour | Focus cảm xúc, học tập | 1–2h compilation |
| Candlelight nocturnes | Classical Music for Sleep & Calm · Candlelight Nocturnes · {N} Hour | Tối, wind-down, thư giãn | 1–3h compilation |

#### Tier 2 — Seasonal & contextual themes (Medium volume, low competition)

| Theme | Title Formula | Video Length |
|---|---|---|
| Chamber music for exam season | Classical Music for Exam Prep · String Quartet · 2 Hour | 2h |
| Winter classical by the fire | Classical Music for Cozy Winter Days · Piano & Fireplace · 1 Hour | 1h |
| Morning baroque for productivity | Morning Classical · Baroque Music to Start Your Day · 1 Hour | 1h |
| Classical for writing & journaling | Classical Music for Writing · Soft Piano & Strings · 1 Hour | 1h |
| Rainy day classical piano | Classical Piano for a Rainy Day · Calm Music for Reading · 1 Hour | 1h |

#### Tier 3 — Experimental / single pieces

| Theme | When to post |
|---|---|
| Single hero piece (3–4 phút, một bản nocturne/prelude đặc biệt làm Short bait) | 1 single/tuần |
| Long-form 3-hour study compilation | 1/tháng, cuối tháng |
| Exam-season focus marathon (3h+) | Tháng 4–5 & 11–12 |
| Classical piano + rain sounds blend | Test mỗi quý 1 lần |

#### Upload Mix hàng tuần

```
Tuần 1: Tier 1 (1–2h compilation) + Tier 1 (1h mix) + Tier 2 (1h mix) + 1 single/Short
Tuần 2: Tier 1 (1h mix) + Tier 2 (1h mix) + Tier 3 (3h compilation) + 1 single/Short
Tuần 3: Tier 1 (1–2h compilation) + Tier 1 (1h mix) + Tier 2 (1h mix) + 1 single/Short
Tuần 4: Tier 1 + Tier 2 + Tier 3 (3h compilation) + Review
...repeat
```

---

## 4. Đặc điểm âm thanh

**Nguyên tắc âm thanh:**
- Classical instrumental — CÓ form (nocturne / prelude / étude / adagio / ABA), CÓ melody phát triển theo thời gian (khác hẳn loop phẳng của lofi). Melody hát được, voice leading sạch.
- Tempo thường 56–96 BPM tùy sub-genre; key vary theo từng piece (Romantic chuộng minor giàu chromatic, Baroque chuộng major sáng)
- Instrumentation: solo grand piano (workhorse) HOẶC string quartet / piano trio / harpsichord-baroque chamber / string orchestra + light woodwinds
- Harmonic era là quyết định lớn nhất: Baroque / Classical / Romantic / Impressionist / Minimalist — mỗi era có chord vocabulary riêng
- Performance feel: **rubato và dynamics là authenticity lever lớn nhất** — crescendo/diminuendo thật, expressive timing, không quantize cứng, không nén phẳng như pop
- Reverb concert-hall hoặc intimate-room — không gian thật, không dry chết
- 100% instrumental — Suno Instrumental toggle ON, không vocal
- Master target **-15 đến -17 LUFS** — classical cần dynamic range rộng, KHÔNG over-compress. Solo piano nghiêng -16/-17, cinematic orchestral -15.

**Volume mix (trong 1 piece — ví dụ piano trio):**
```
Lead voice (grand piano / lead violin): 0dB reference
Secondary voice (cello / supporting strings): -4dB
Inner voices / accompaniment: -7dB
Sustain pedal wash / room bloom: -14dB
Hall reverb tail: -18dB
Room tone / air: -28dB
```
> Lưu ý: không có "drum bus", không có "bass synth", không có "vinyl crackle". Dynamic range giữa pp và ff phải nghe được — đó chính là chất classical.

**Compilation strategy:** compilation 1 giờ ≈ 12–18 piece riêng biệt cùng series identity, crossfade vào nhau. KHÔNG loop 1 piece 4 phút × 15. Mỗi piece có intro mềm + ending lắng (không cold-stop, không cadence cắt cụt) để crossfade sạch giữa các bản.

---

## 5. Prompt Templates

> Kênh này dùng skill **`music-video`** để sản xuất toàn bộ data mỗi video. Skill có 3 workflow: **Music** (Suno + ElevenLabs fallback, qua 2-persona Producer + Artist), **Visual** (Midjourney + Runway), **SEO**. Phần dưới là preset gọi nhanh cho kênh Classical.

### 5.1 Suno AI — Music Prompts (qua skill music-video)

Gọi skill: `music-video` → workflow Music → genre `classical`. Skill chạy 2-persona interview:
- **Producer** quyết: sub-genre, BPM, key, structure (nocturne/prelude/ABA…), instrumentation, mix, master LUFS, compilation strategy
- **Artist** (a classical composer and concert pianist) quyết: form, harmonic era (Baroque / Classical / Romantic / Impressionist / Minimalist), voice leading, melodic development, rubato & dynamics, reference lineage, emotional arc

**Preset "Romantic piano for studying" — Style of Music (paste vào Suno):**
```
solo classical piano, ~66 BPM, D minor, nocturne form with a lyrical singing melody, single grand piano in an intimate close-miked room, expressive rubato and natural crescendo and diminuendo, warm sustain pedal bloom, in the Romantic-era nocturne tradition, tender and introspective, instrumental
```

**Title:** `Lamplight Nocturne` (đặt theo concept, không có duration token)

**Exclude Styles:**
```
vocals, lyrics, drums, percussion, electronic, synth, pop, beat
```

**Lyrics field:** để trống.

**ElevenLabs Music — fallback prompt:**
```
A tender, introspective Romantic-era solo piano nocturne at around 66 BPM in D minor — a single grand piano in an intimate close-miked room, with a lyrical singing melody, expressive rubato, and natural crescendo and diminuendo. Warm sustain pedal bloom. Purely instrumental, no vocals or percussion. Starts and ends gently so it crossfades into a study compilation.
```

> Các preset khác (Baroque clarity, Impressionist drift, Chamber focus, Cinematic orchestral) — xem per-genre preset table trong `skills/music-video/references/music_prompt.md`.

### 5.2 Midjourney — Visual Prompts (qua skill music-video)

Gọi skill: `music-video` → workflow Visual → genre `classical`.

**Style prefix chung:**
```
--ar 16:9 --style raw --v 6.1 --q 2
```

**Preset "Candlelit study":**
```
an elegant candlelit study at night, a worn leather armchair beside a tall shelf of old leather-bound books, a single candle and an open book on a small wooden table, warm pools of light, dust motes hanging in the air, ivory and soft gold tones with a muted slate-blue shadow, painterly photorealistic 35mm film grain, shallow depth of field, no people, timeless and quiet atmosphere --ar 16:9 --style raw --v 6.1 --q 2
```

> Quy tắc: không người trong khung, không chữ trên ảnh, không brand thật.

### 5.3 Runway Gen-4 — Animation Prompts (qua skill music-video)

Gọi skill: `music-video` → workflow Visual → Runway block. Áp dụng quy tắc static-camera (memory `feedback_runway_static_camera.md`). Classical có thể nhận một push-in 5 giây gần như không nhận ra — không bao giờ kết hợp với chuyển động khác.

**Preset "Candlelit study":**
```
Prompt: "Locked-off tripod shot, zero camera movement throughout, or an imperceptible slow push-in. The candle flame flickers very gently in place above the table. Dust motes drift slowly upward in place within the pool of warm light, staying inside that zone. The warm light glow pulses faintly in place. The books, the armchair, and the table stay completely still. Nothing else moves. Elegant, slow, seamless study loop."
Settings: Motion intensity: 2-3/10, Duration: 5s (loop), Camera: Locked-off (or imperceptible push-in)
```

---

## 6. SEO Templates

### 6.1 Title Formulas

**Classical:**
```
Classical Music for [Function] · [Sub-genre/Mood] · [Duration]
```

**Ví dụ thực tế:**
- `Classical Music for Studying · Romantic Piano · 2 Hours`
- `Baroque Music for Focus · 1 Hour of Bright Classical`
- `Classical Music for Reading · Impressionist Piano · 1 Hour`
- `Classical Music for Deep Work · Cinematic Strings · 2 Hour Mix`
- `Classical Music for Sleep & Calm · Candlelight Nocturnes · 3 Hours`

**Rules:**
- ✅ "Classical Music" + function keyword ("Studying", "Focus", "Reading", "Deep Work") trong 3–4 từ đầu
- ✅ Duration cuối title cho mix/compilation ("2 Hours", "1 Hour")
- ✅ Separator ` · ` (middle dot)
- ❌ Không emoji trong title
- ❌ Không "AI" trong title (CTR giảm)
- ❌ Không tên nhà soạn nhạc cụ thể trong title ("Chopin", "Debussy") — dùng era/sub-genre ("Romantic Piano", "Baroque")
- ❌ Không ALL CAPS, không đánh số Vol.

### 6.2 Description Template

```
[Hook: genre + function + mood + duration. 1 câu.]

[Vibe paragraph: nhạc cảm giác thế nào, nghe để làm gì, nhạc cụ gì dẫn dắt, mood arc. 3–5 câu.]

[Use line: 1 câu về loop / nghe nền cả buổi học / pair với hoạt động nào.]

─────────────────────────────────────
🎵 MUSIC
─────────────────────────────────────
Genre: Classical instrumental
Instruments: Grand piano · string quartet · light woodwinds
Key / Tempo: D minor · 66 BPM
Feel: Expressive rubato · natural dynamics · Romantic-era phrasing

─────────────────────────────────────
🎨 VISUAL
─────────────────────────────────────
Scene: An elegant candlelit study with old books at night
Mood: Timeless · elegant · warm · quiet

─────────────────────────────────────
⏱ TRACKLIST / CHAPTERS
─────────────────────────────────────
[chapter per piece hoặc fixed block 10–15 phút]

─────────────────────────────────────
💡 BEST FOR
─────────────────────────────────────
• Studying and exam prep
• Deep work and concentration
• Reading and writing
• Journaling and reflection
• Background for focus sessions
• Calm evening wind-down

─────────────────────────────────────
🎧 LISTENING TIPS
─────────────────────────────────────
[2–3 câu về volume, headphones vs speakers, expect dynamic range — nhạc có lúc khẽ lúc đầy]

─────────────────────────────────────
📌 MORE FROM THIS CHANNEL
─────────────────────────────────────
[Links tới compilation classical khác của kênh]

#ClassicalMusic #ClassicalMusicForStudying #PianoMusic #StudyMusic #RelaxingMusic #ClassicalPiano #FocusMusic #BaroqueMusic #InstrumentalMusic #MusicForReading #ClassicalMusicForSleep #PianoForStudying #CalmMusic #ConcentrationMusic #ClassicalForFocus
```

### 6.3 Tag List Master

**Classical — 500 ký tự tags:**
```
classical music, classical music for studying, piano music, relaxing classical music, study music, classical music for sleep, instrumental, baroque music, classical piano, classical music for reading, focus music, classical music for focus, music for studying, relaxing music, calm music, piano for studying, classical study music, deep focus music, background music, classical music 1 hour, instrumental music, concentration music, romantic piano, impressionist piano, string quartet music
```
(Adjust mood-specific tags cho từng video.)

---

## 7. Thumbnail & Visual Guidelines

**Kích thước:** 1280×720px

**Composition:**
- Full-bleed visual từ Midjourney (cùng scene với background loop → consistency)
- Text overlay nhỏ-vừa, bottom-left hoặc bottom-center
- Loại bỏ clutter — thumbnail classical nên trang nhã, "thở", một mood rõ ràng

**Text style:**
- Font: serif thanh lịch (Cormorant Garamond / EB Garamond / Playfair Display) — timeless, không cứng
- Màu: Warm ivory `#F2E8D5` với drop shadow nhẹ, hoặc soft gold `#C9A24B` cho từ nhấn
- Kích thước: "Classical Music" ~44pt, function+duration ~24pt
- Vị trí: bottom-left, margin 60px

**Mood:** Elegant, timeless, "a quiet place to think". Người nhìn vào phải thấy muốn ngồi xuống, mở sách, và tập trung.

**Không làm:**
- ❌ Chữ to bold đỏ chói (sai genre hoàn toàn)
- ❌ Mặt người / avatar người thật / chân dung nhà soạn nhạc
- ❌ Quá nhiều element cạnh tranh
- ❌ Màu neon, lạnh gắt (đó là kênh EDM)
- ❌ Ảnh sheet music nhòe của một tác phẩm nổi tiếng có thể nhận ra

**Template Canva setup:**
```
Nền: ảnh Midjourney scene (1280×720)
Overlay: gradient transparent → #1A1814 (warm charcoal) 30% opacity, bottom 35%
Text block: bottom-left, serif font thanh lịch, ivory/gold
```

---

## 8. Production Pipeline — Step by Step

### Tổng thời gian mỗi compilation 1–2 giờ: 100–170 phút (gồm batch 12–18 piece)

#### Bước 1 — Chọn theme & brief (10 phút)
```
1. Chọn theme tuần này từ Theme Library (Section 3)
2. Xác định series identity: sub-genre classical, harmonic era, key family, tempo band, instrumentation, mood
3. Đây là input cho skill music-video workflow Music
```

#### Bước 2 — Generate music data qua skill music-video (15 phút)
```
1. Gọi skill: music-video → workflow Music → genre classical
2. Skill chạy 2-persona interview (Producer + classical composer/concert pianist Artist) cho SERIES IDENTITY
3. Skill xuất: Suno Style/Title/Exclude + ElevenLabs fallback + Producer/Artist notes
4. File lưu: working/{theme-slug}/json/ + md/
5. Với compilation 1–2h: lặp lại phần config nhẹ cho 12–18 piece variation (giữ identity, đổi form/melody/mood/key)
```

#### Bước 3 — Generate nhạc trên Suno (40–50 phút cho batch 12–18 piece)
```
1. Mở Suno → Custom Mode, Instrumental ON
2. Paste Style of Music + Title + Exclude Styles từ skill output
3. Generate 2–4 variation mỗi piece → chọn bản tốt nhất (kiểm tra: có dynamics thật không? rubato nghe người không?)
4. Nếu Suno fail/rate-limit → fallback ElevenLabs Music với prompt từ skill
5. Download WAV tất cả piece
6. Đặt tên: classical_{theme-slug}_{NN}.wav
```

#### Bước 4 — Compile + master (Audacity/Audition, 25–30 phút)
```
1. Import 12–18 piece vào timeline
2. Sắp xếp theo mood arc (mở đầu lắng → giữa giàu dynamics → kết tĩnh)
3. Crossfade 3–5s giữa các piece (dài hơn lofi vì ending classical lắng dần)
4. Master bus: KHÔNG over-compress — chỉ normalize nhẹ, giữ dynamic range, LUFS target -15 đến -17
5. Export WAV compilation: classical_{theme-slug}_MIX.wav
```

#### Bước 5 — Generate visual qua skill music-video (20 phút)
```
1. Gọi skill: music-video → workflow Visual → genre classical
2. Skill xuất Midjourney prompt + Runway prompt + creative brief
3. Midjourney: generate → upscale → classical_{theme-slug}_visual.png
4. Runway Gen-4: upload PNG + Runway prompt → motion 2-3/10 (cho phép imperceptible push-in) → loop 5s
5. Download: classical_{theme-slug}_loop.mp4
```

#### Bước 6 — Ghép video (CapCut, 20 phút)
```
1. New project 1920×1080, 24fps
2. Import: visual_loop.mp4 + MIX.wav
3. Loop visual đến khớp audio length, crossfade 0.5s
4. Fade-in 2s, fade-out 4s (classical cần fade dài hơn — tôn trọng phần lắng cuối)
5. Export: 1920×1080, 24fps, 16Mbps, MP4 H.264
6. Tên: classical_{theme-slug}_FINAL.mp4
```

#### Bước 7 — Generate SEO qua skill music-video (10 phút)
```
1. Gọi skill: music-video → workflow SEO → genre classical
2. Skill đọc paired music + visual JSON, xuất: title + 4 alt, description, 40 tags, 3 thumbnail text, pinned comment, chapters
3. File lưu: working/{theme-slug}/json/ + md/
```

#### Bước 8 — Thumbnail + Shorts cut (15 phút)
```
1. Thumbnail Canva: visual.png + text từ skill SEO output
2. Shorts: cắt 60s đoạn hay nhất từ MIX (chọn một câu nhạc trọn vẹn, không cắt giữa phrase) → vertical 1080×1920 + text overlay
```

#### Bước 9 — Upload & Schedule (10 phút)
```
1. YouTube Studio → Upload FINAL.mp4
   - Title, description, tags, chapters từ skill SEO output
   - Thumbnail, playlist
   - ✅ Tick "Altered or synthetic content" (AI disclosure)
   - Schedule theo content calendar
2. Pin comment từ skill output
```

### Batch Production (Khuyến nghị)

```
Thứ 2 (3h): Skill music-video — generate music data cho 3-4 theme tuần này
Thứ 3 (3.5h): Batch Suno generation — tất cả piece
Thứ 4 (3h): Batch compile + master tất cả compilation
Thứ 5 (3h): Skill music-video — visual + SEO; Midjourney + Runway; CapCut ghép
Thứ 6 (1h): Thumbnail + upload schedule cả tuần
```

**Tổng thời gian/tuần:** ~14 giờ cho 3–4 video + Shorts

---

## 9. Tool Stack & Chi phí

### Classical Channel Stack (~$90/tháng)

| Tool | Mục đích | Chi phí/tháng |
|---|---|---|
| Suno Premier | Music generation chính — own commercial rights | $30 |
| ElevenLabs Creator | Music fallback khi Suno fail / cần variation | $22 |
| Midjourney Standard | Visual + thumbnail | $30 |
| Runway Standard | Image-to-video loop | $15 |
| Audacity / Adobe Audition | Compile + master (giữ dynamic range, không over-compress) | Free / $22 |
| CapCut Pro | Video editing | $10 |
| TubeBuddy Lite | Keyword research | $9 |
| Canva Pro | Thumbnail | $13 |
| **Total** | (Audacity free, ElevenLabs có thể bỏ nếu Suno đủ) | **~$90–$135/tháng** |

### Optional Tools (nâng cấp sau tháng 3)

| Tool | Khi nào cần | Chi phí |
|---|---|---|
| DistroKid | Khi muốn đưa compilation/piece lên Spotify | $23/năm |
| Magnific AI | Upscale thumbnail 4K-8K cho hero video | $39/tháng |
| iZotope RX | Khi cần clean up artifact từ Suno output (piano pedal noise, smear) | $99 one-time |
| Adobe Audition (full) | Khi cần mastering chính xác hơn cho dynamic range classical | $22/tháng |

---

## 10. Automation Script — Hướng dẫn sử dụng

File: `pipeline.py` (extend từ ASMR/Soundscapes pipeline với `--channel classical`)

### Cài đặt

```bash
pip install rich click colorama
python pipeline.py --help
```

### Các lệnh chính

#### Tạo metadata cho 1 video
```bash
python pipeline.py generate \
  --channel classical \
  --theme "romantic-piano-studying" \
  --length 120min \
  --date 20260601
```

#### Quản lý upload queue
```bash
python pipeline.py queue add \
  --channel classical \
  --file classical_romantic-piano-studying_FINAL.mp4 \
  --date 2026-06-01 \
  --time 14:00

python pipeline.py queue list
python pipeline.py queue done --id 3
```

#### Đặt tên file hàng loạt
```bash
python pipeline.py rename --folder ./raw_exports --channel classical
```

#### Xem content calendar
```bash
python pipeline.py calendar --channel classical --month 2026-06
```

> Lưu ý: phần generate music/visual/SEO data thực tế do skill `music-video` đảm nhiệm; `pipeline.py` lo phần queue, naming, calendar, upload orchestration.

---

## 11. Content Calendar — 3 tháng đầu

### Tháng 1 — Launch (Setup + Test)

**Tuần 1:**
| Ngày | Video | Theme |
|---|---|---|
| T2 | Setup | Brand assets, channel art, test skill music-video |
| T4 | Upload 1 | Classical Music for Studying — Romantic Piano — 2 Hours |
| T6 | Upload 2 | Baroque Music for Focus — 1 Hour |

**Tuần 2:** Classical for Reading — Impressionist Piano 1h / Cinematic Strings for Focus 2h / single hero nocturne + Short

**Tuần 3:** Romantic Piano for Studying 1h (variation) / Candlelight Nocturnes 1h / Chamber Music for Exam Season 2h

**Tuần 4 — Review:**
- Dừng 1 ngày để review analytics
- Video nào có AVD cao nhất? → Double down tháng 2
- Theme nào có CTR cao nhất? → Làm thêm variation
- Điều chỉnh upload schedule nếu cần

**Mục tiêu Tháng 1:**
- ✅ 10–12 video uploaded
- ✅ Xác định được top 3 performing themes
- ✅ Watch hours target: 500h (compilation dài → watch time cao hơn lofi)

---

### Tháng 2 — Scale + Optimize

**Classical — Upload 4 video/tuần:**
- 2 video variation của top theme từ Tháng 1
- 1 video theme mới (test)
- 1 long-form 3h compilation

**Tháng 2 targets:**
- ✅ 16 video (running total: 28)
- ✅ Watch hours: 1,800h (cumulative)
- ✅ Subscribers: 200–500
- ✅ Bắt đầu Shorts: 1 Short/ngày cắt từ compilation đã có

---

### Tháng 3 — Monetize

**Classical: Upload 4 video/tuần, focus quality + watch time**

**Theme focus Tháng 3:**
```
Week 1: 3-Hour Classical Music for Deep Work Compilation
Week 2: Exam Season Focus Marathon (3h+)
Week 3: Romantic Piano for Studying (variation của top theme)
Week 4: Cozy Winter / Seasonal Classical — seasonal timing
```

**Tháng 3 targets:**
- ✅ 4K+ watch hours, 1K+ subscribers → Apply YPP
- ✅ Đăng ký DistroKid → đưa top compilation lên Spotify
- ✅ Bắt đầu Pinterest boards cho visual content

---

### Shorts Strategy

**Format:** Cắt 58–60 giây từ compilation chính (một câu nhạc trọn vẹn, không cắt giữa phrase)

**Classical Shorts:**
- Tiêu đề: "1 Minute of [Mood] Classical Piano — Full Mix on the Channel"
- Call to action: "Full 2-hour compilation on the channel →"

**Upload Shorts:** Hàng ngày, 8:00 PM EST (peak US study time)

---

## 12. KPI & Success Metrics

### Metrics cần track mỗi tuần (30 phút review)

#### Performance Metrics
| Metric | Target (Tháng 3) |
|---|---|
| Total watch hours | 4,000h |
| Subscribers | 1,000 |
| Average View Duration | > 25 phút (cho compilation 1–2h) |
| CTR (Click-through rate) | > 4% |
| Impressions/tuần | Growing 10%+ |

#### Content Metrics
| Metric | Xem ở đâu | Đọc như thế nào |
|---|---|---|
| Average View Duration | YouTube Analytics > Content | Compilation < 15 phút AVD → nhạc không giữ chân, re-evaluate Suno prompt qua skill |
| CTR | YouTube Analytics > Reach | Dưới 2%: thay thumbnail. Dưới 1%: thay title |
| Revenue per view | Monetize sau → RPM | Target $5–10, nếu thấp → check geo audience |
| Traffic source | Analytics > Reach | Search + Suggested > 60% là tốt; "classical music for studying" là search term lớn |
| Returning viewers % | Analytics > Audience | > 25% = audience đang bind với channel sound |

### Dấu hiệu cần can thiệp ngay

- ❗ CTR < 1% sau 500 impressions → Thay thumbnail ngay
- ❗ AVD < 12 phút cho compilation 1–2h → Nhạc có vấn đề (piece quá giống nhau / mood arc kém / dynamics bị nén phẳng / Suno output generic)
- ❗ Watch hours stagnant 2 tuần → Thử theme mới, tăng upload frequency
- ❗ Subscribe rate giảm → Có video nào mismatch channel sound không (ví dụ một piece có percussion lọt vào)?

---

## 13. Monetization Checklist

### YouTube Partner Program — Apply khi đủ điều kiện

- [ ] 1,000 subscribers
- [ ] 4,000 public watch hours (trong 12 tháng qua)
- [ ] Không có community guideline strikes
- [ ] 2-step verification bật
- [ ] Đã tick "Altered or synthetic content" trên mọi video AI

### YouTube Policies — Phải pass tất cả

- [ ] **Inauthentic content**: Mọi video có animated visual (không phải static image) + nhạc gốc có human creative direction (qua skill 2-persona interview)
- [ ] **Reused content**: Mỗi compilation là batch piece riêng biệt, không có 2 video share > 30% cùng audio
- [ ] **AI disclosure**: Tick "Altered/synthetic content" 100% video
- [ ] **Advertiser-friendly**: Không content nhạy cảm
- [ ] **Content ID**: Sáng tác gốc Suno Premier — bạn sở hữu output, không bị claim. Vẫn check claim checker lần đầu để chắc.

### Compliance — nhẹ hơn nhiều so với mô hình cover

Vì là nhạc gốc instrumental:
- [ ] **Suno Premier active** tại thời điểm generate (lưu screenshot — chứng minh commercial rights cho output)
- [ ] **ElevenLabs**: nếu dùng fallback, đảm bảo plan có commercial license
- [ ] **AI disclosure** đầy đủ trên YouTube
- [ ] **Public-domain inspiration is fine** — sáng tác lấy cảm hứng từ era cổ điển (Chopin, Debussy, Bach, Satie) và phong cách lịch sử là hoàn toàn hợp lệ. Quy tắc: prompt mô tả lineage theo ERA/STYLE ("Romantic-era nocturne tradition", "Baroque counterpoint"), KHÔNG bao giờ "in the style of [tác phẩm nổi tiếng cụ thể]" theo cách tái tạo một bản đã biết. Tên nhà soạn nhạc công cộng dùng làm cảm hứng được; sao chép một tác phẩm cụ thể thì không.
- [ ] KHÔNG cần: license vault, sync license, vocal contract, Content ID dispute workflow — mô hình cover cũ đã bỏ

### Sau khi monetize — Optimize RPM

1. **Tăng video length** — compilation 2–3h > mix 1h về watch time per upload; classical audience nghe rất dài
2. **Q4 push** — tháng 11–12 CPM cao 2–3x; upload nhiều hơn + seasonal themes (winter classical, fireplace)
3. **Geo targeting** — audience US/UK/EU/AU/CA có CPM cao nhất; SEO title tiếng Anh thuần
4. **No mid-roll** trên compilation dài — audience study/focus hatewatch nếu bị ngắt; chỉ pre-roll

### Dòng doanh thu thứ 2 — Spotify

Sau tháng 3, đưa top piece/compilation lên Spotify qua DistroKid:
- Chọn 12–15 piece hay nhất, đóng thành album "Classical for Studying — Focus Collection Vol.1"
- Category: Classical / Instrumental / Piano
- AI disclosure: tick DDEX flag
- Revenue: ~$0.003–0.005/stream — passive 100%, có thể vào editorial playlist classical focus / peaceful piano

---

*Dùng kết hợp với:*
- *Skill `music-video` (`skills/music-video/`) — sản xuất data cho từng video*
- *`Channel_Launch_Plan_Lofi_Acoustic.md`, `Channel_Launch_Plan_Jazz.md`, `Channel_Launch_Plan_EDM.md` (3 kênh còn lại)*
- *`pipeline.py` (automation — queue / naming / calendar / upload)*

*Cập nhật lần cuối: 2026-05-15*
