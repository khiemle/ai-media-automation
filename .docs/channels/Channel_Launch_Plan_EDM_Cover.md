# Channel Launch Plan — EDM / Remix Cover

> Kênh AI cover EDM/Electronic — biến catalogue US/UK pop thành EDM-style covers. **Rủi ro Content ID cao nhất** trong 2 kênh; áp dụng tier strategy + remix clause + pivot plan B (xem cảnh báo dưới).
> Cập nhật: 2026-05-10

---

## ⚠️ Đọc trước khi triển khai

EDM/Remix là kênh rủi ro Content ID cao nhất theo `Brief_canh_tranh_AI_Cover_Suno_2026.docx` Section 9.2. Áp dụng 3 chiến thuật giảm rủi ro:
1. **Bias mạnh sang Tier C** (bài ít nổi tiếng), KHÔNG remix Tier A hits (24K Magic, Toxic, Dance Monkey...) trong Tháng 1–3.
2. **Re-arrangement sâu** — đổi BPM, key, structure → tăng khoảng cách fingerprint với master gốc.
3. **Pivot plan B** — sau 6 tháng nếu Content ID không kiểm soát được → re-launch là "EDM Originals" với composition gốc độc quyền từ đối tác.

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

| Tiêu chí | EDM / Remix Cover |
|---|---|
| **Focus** | EDM-style re-arrangement của catalogue cover (ưu tiên Tier C bài ít nổi tiếng) |
| **Audience** | 16–30, EDM/festival/pop fan, gym/drive/party listeners |
| **Video length** | 3–4 phút single visualizer · 30–60 phút mix set |
| **Upload frequency** | 2 single/tuần + 1 mix set/2 tuần + Shorts daily |
| **RPM ước tính** | $3–$6 |
| **Advertiser category** | Energy drinks, fashion, mobile games, sports apparel, lifestyle apps |
| **Music style** | Future bass / synthwave / big room / tropical house, 124-130 BPM, sidechain pumping, vocal chops |
| **Visual style** | Neon, dynamic motion, color shifts, synthwave/festival aesthetic |
| **Time to monetize** | 5–8 tháng (Content ID rát hơn Lofi) |
| **Launch order** | **Tháng 1** (song song Lofi) — nhưng có sẵn pivot plan B |

### Vì sao đây là kênh test #2 — và cảnh báo

EDM/Remix vốn được pick bởi user, nhưng **không phải lựa chọn rủi ro thấp**. Lý do vẫn launch song song với Lofi:
- Test 2 audience khác hẳn (chill/lofi vs. high-energy EDM) → discover đâu là demand thật cho catalogue và vocalist
- Build EDM identity sớm cho phép pivot sau (ví dụ "EDM Originals" khi có composition độc quyền)
- Audience EDM tiêu thụ nhanh, share Shorts/Reels mạnh → discovery loop khác hẳn Lofi

**Risk acceptance:** sẵn sàng chấp nhận rằng Tháng 1–3 có thể nhiều Content ID claim, ad revenue về publisher chiếm 100%. Mục tiêu giai đoạn này KHÔNG phải doanh thu mà là **build audience signal + Spotify discovery**.

---

## 2. Brand Identity

**Tên kênh:** *(gợi ý, chọn 1)*
- `Voltage Cover`
- `Neon Replay`
- `BRIGHT/CUT`
- `After Hours Cover`
- `Pulse Replay`

**Tagline:** *"Songs you know. Drop you didn't."*

**Brand colors:**
- Primary: Neon magenta `#FF2A8E`
- Secondary: Electric cyan `#00E5FF`
- Accent: Hot white `#FFFFFF` (dùng cho text trên thumbnail)
- Background: Pure black `#000000`

**Brand voice:**
- Confident, hyped (đối lập hẳn Lofi)
- Caps lock cho chorus hook trong mô tả ("THIS DROP HITS DIFFERENT")
- Description ngắn gọn, đập trực tiếp — không storytelling dài

**Channel art:**
- Avatar: glitch geometric mark — magenta + cyan + black, sharp angles, contrast cao
- Banner: dark void background với neon line accents + tagline bold sans-serif (Bebas Neue / Druk Wide), căn safe area 1546×423

**Vocal personas (EDM aliases):**
Cùng 4 vocalist (ALLEN_1..4) như Lofi nhưng REBRAND để tách identity trên 2 kênh:
- ALLEN_1 → `AYDN` — series chính: AFTER HOURS (synthwave) + VOLT (electro pop)
- ALLEN_2 → `MIRA` — series chính: AFTER HOURS + NEON (tropical house)
- ALLEN_3 → `KOLE` — series chính: BRIGHT/CUT (future bass) + PULSE (big room)
- ALLEN_4 → `S.E.R.A` — series chính: PULSE + NEON

Mỗi alias có Spotify artist profile riêng (yêu cầu DistroKid Musician+ để có nhiều profile).

**Series-by-sub-genre (KHÁC Lofi — chia theo sound chứ không theo vocalist):**

| Series | Sub-genre EDM | Mood | Vocalist nào fit |
|---|---|---|---|
| `BRIGHT/CUT` | Future Bass / Melodic Dubstep | Energetic, festival drop | KOLE, AYDN |
| `AFTER HOURS` | Synthwave / Retrowave | Nighttime drive, retro | MIRA, AYDN |
| `PULSE` | Big Room / Mainstage | Anthemic, EDC-style | KOLE, S.E.R.A |
| `NEON` | Tropical House | Beach, summer chill | MIRA, S.E.R.A |
| `VOLT` | Electro Pop | Polished radio-ready | tất cả |

Mỗi single thuộc 1 series → mỗi 5 single là 1 mix set series compilation.

---

## 3. Content Strategy — Theme Library

Catalogue: cùng 77 bài như Lofi channel (`working-music/music-vocals/vocal usuk/Vocal us uk Cover/ALLEN_[1-4]/`). Khác Lofi ở chỗ **chia theo series sub-genre EDM** (BRIGHT/CUT, AFTER HOURS, PULSE, NEON, VOLT) thay vì theo vocalist.

#### Format mix — mỗi bài khai thác qua 5 format

| # | Format | Thời lượng | Mục đích | Upload ở đâu |
|---|---|---|---|---|
| 1 | **Single visualizer** | 3–4 phút | Doanh thu YouTube + push Spotify | YouTube long-form + Spotify |
| 2 | **Mix Set / DJ-style** | 30–60 phút | "[Vocalist] EDM Mix Vol.X" — boost watch hours | YouTube long-form (1 video/2 tuần) |
| 3 | **YouTube Shorts** | 30–60 giây | Discovery drop highlight | YouTube Shorts (hàng ngày) |
| 4 | **TikTok / Reels** | 15–30 giây | "Drop hit", viral trend hookable | TikTok + Instagram Reels (hàng ngày) |
| 5 | **Spotify Canvas** | 8 giây vertical loop | Spotify discovery enhance — must-have cho EDM mobile audience | Spotify (qua DistroKid Canvas) |

#### Phân bổ tuần

```
Thứ 3: Single visualizer #1 (Tier 1 — Tier C catalogue)
Thứ 6: Single visualizer #2 (Tier 1 — Tier C catalogue)
Mỗi 2 tuần (Thứ 7): Mix Set 30-60 phút

Daily: 1 Short + 1 TikTok/Reels (cắt từ pipeline)
```

#### Tier 1 — Tier C catalogue × EDM Series (Launch trước, rủi ro thấp nhất)

Bài ít nổi tiếng + EDM re-arrangement → fingerprint xa master gốc → ít claim. Core uploads Tháng 1–3.

| Theme | Title Formula | Series | Vocalist | Video Length |
|---|---|---|---|---|
| Bad Child | Bad Child — KOLE (Future Bass Cover) | BRIGHT/CUT | KOLE | 3:30 |
| Doll House | Doll House — MIRA (Synthwave Cover) | AFTER HOURS | MIRA | 3:30 |
| Long Drives | Long Drives — AYDN (Tropical House Cover) | NEON | AYDN | 3:30 |
| Rx | Rx — KOLE (Melodic Dubstep Cover) | BRIGHT/CUT | KOLE | 3:30 |
| Void | Void — MIRA (Synthwave Cover) | AFTER HOURS | MIRA | 3:30 |
| Talking Body | Talking Body — MIRA (Tropical House Cover) | NEON | MIRA | 3:30 |
| Death | Death — KOLE (Melodic Dubstep Cover) | BRIGHT/CUT | KOLE | 3:30 |
| MAMA SAID | MAMA SAID — AYDN (Electro Pop Cover) | VOLT | AYDN | 3:30 |
| Sunrise | Sunrise — S.E.R.A (Tropical House Cover) | NEON | S.E.R.A | 3:30 |
| Walking Away | Walking Away — AYDN (Synthwave Cover) | AFTER HOURS | AYDN | 3:30 |
| Shy Away | Shy Away — KOLE (Future Bass Cover) | BRIGHT/CUT | KOLE | 3:30 |

#### Tier 2 — Tier B catalogue (Sau khi verify sync + remix clause)

Hits trung bình. KHẮT KHE: phải verify sync rights + remix clause cụ thể từng bài.

| Theme | Title Formula | Series | Video Length |
|---|---|---|---|
| Cool Kids | Cool Kids — S.E.R.A (Big Room Cover) | PULSE | 3:30 |
| Heathens | Heathens — KOLE (Melodic Dubstep Cover) | BRIGHT/CUT | 3:30 |
| Marvin Gaye | Marvin Gaye — MIRA (Tropical House Cover) | NEON | 3:30 |
| Sorry | Sorry — AYDN (Future Bass Cover) | BRIGHT/CUT | 3:30 |
| Prayer in C | Prayer in C — S.E.R.A (Big Room Cover) | PULSE | 3:30 |
| 7 Years | 7 Years — KOLE (Melodic Dubstep Cover) | BRIGHT/CUT | 3:30 |
| Hey There Delilah | Hey There Delilah — MIRA (Synthwave Cover) | AFTER HOURS | 3:30 |

#### Tier 3 — Tier A catalogue (CẤM trong Tháng 1–3, đợi pivot)

Hits cực lớn — DO NOT TOUCH cho EDM giai đoạn 1, kể cả khi có sync letter. Đợi đến Q3 2026 với catalogue gốc độc quyền từ đối tác.

| Theme | When to post |
|---|---|
| 24K Magic / A Sky Full of Stars / Locked Out of Heaven | KHÔNG release single EDM trong Tháng 1–3 |
| Careless Whisper / Toxic / Dance Monkey | KHÔNG release. Có thể trong mix set rất xa |
| Heathens / Wonderful Tonight / Stressed Out | Đợi sync + remix clause double-verified |

#### Long-form Mix Set (luân phiên 2 tuần)

| Theme | When to post |
|---|---|
| `KOLE — BRIGHT/CUT Mix Vol.[N] | Future Bass Compilation` | Mỗi 4 tuần (compile từ singles BRIGHT/CUT) |
| `MIRA — AFTER HOURS Mix Vol.[N] | Synthwave Drive Compilation` | Mỗi 4 tuần |
| `AYDN — NEON Mix Vol.[N] | Tropical House Beach Compilation` | Mùa hè Tháng 5–8 |
| `S.E.R.A — PULSE Mix Vol.[N] | Festival Anthem Compilation` | Cuối tuần lễ hội (Tháng 6–9) |

#### Upload Mix hàng tuần

```
Tuần 1: Tier 1 (single Tier C BRIGHT/CUT) + Tier 1 (single Tier C AFTER HOURS) + Shorts daily
Tuần 2: Tier 1 (single Tier C NEON) + Tier 1 (single Tier C BRIGHT/CUT) + Mix Set 30-60 phút + Shorts daily
Tuần 3: Tier 1 (single) + Tier 2 (single Tier B đã verify) + Shorts daily
Tuần 4: Tier 1 (single) + Tier 1 (single) + Mix Set + Shorts daily
...repeat
```

---

## 4. Đặc điểm âm thanh

**Nguyên tắc âm thanh:**
- BPM tăng lên 124–130 (chuẩn EDM festival), trừ tropical house 100–110
- Key thường shift major hoặc up-tune để tạo drop năng lượng cao
- Side-chain compression nặng trên drop (4-on-floor kick → pumping pad/lead)
- Reese bass hoặc supersaw lead trên chorus drop
- Vocal chops (cắt vocal thành melodic hook) ở pre-drop hoặc bridge break
- Build → drop → break → drop structure rõ ràng
- Master target **-9 LUFS** (hot, EDM standard), true-peak ≤ -1dBTP

**Volume mix (master final):**
```
Drop section:
  Lead synth/supersaw: 0dB reference
  Vocal lead: -3dB (vocal must cut through drop)
  Reese/sub bass: -4dB
  Kick (4-on-floor): -3dB (sidechain pumping)
  Snare/clap layered: -7dB
  Hi-hats festival shuffle: -12dB
  FX (riser, impact, white noise): -6dB

Verse section:
  Vocal: 0dB
  Pluck/lead arp: -8dB
  Drum loop minimal: -10dB
  Pad: -16dB
```

---

## 5. Prompt Templates

> Cùng framework 3 vai trò (Producer / Songwriter / Artist) như Lofi nhưng thay đổi parameter triệt để. EDM cần **drop hit hard**, prompt phải direct production rất cụ thể.

### 5.1 Suno AI — Music/Audio Prompts

**Format chung (cho cover song trong Suno Custom Mode):**
- Ô **Style of Music** = ghép 3 layer (Producer + Songwriter + Artist)
- Ô **Lyrics** = lyric gốc
- Ô **Voice** = voice đã verified của vocalist
- Ô **Exclude Styles** = `acoustic, lofi, slowed, ballad, country, classical, jazz, organic instruments only, screamed harsh vocals, rap, trap, drill`

#### Framework 3 vai trò — EDM context

**Vai trò Producer** quyết định production palette:

| Yếu tố | Cách viết | Ví dụ EDM |
|---|---|---|
| Sub-genre cụ thể | Một sub-genre EDM, không "EDM" chung chung | `melodic future bass cover` / `synthwave cover` |
| BPM | Theo sub-genre | `128 BPM` (future bass/big room) hoặc `100 BPM` (tropical house) |
| Key direction | Often raise 1–2 semitone for brightness | `up-tuned 2 semitones to E major` |
| Instrumentation | Cụ thể synth + drums | `supersaw lead, reese sub bass, plucked sine bass, sidechained pad, 4-on-floor kick, layered snare with snap, festival hi-hat shuffle, white noise riser, impact crash` |
| Mix character | EDM-specific | `heavy sidechain pumping on drop, wide stereo mid-band, hot-mastered to -9 LUFS` |
| Reverb / space | Festival / club | `wide hall reverb on lead, tight room on vocal, dub delay on accents` |
| Production reference | Era/genre KHÔNG tên producer cụ thể | `produced like a 2017-era melodic future bass record` |

**Vai trò Songwriter** quyết định structural & emotional — EDM REQUIRES re-arrangement sâu (khác Lofi giữ form gần gốc):

| Yếu tố | Cách viết | Ví dụ |
|---|---|---|
| Arrangement form | EDM structure cụ thể | `intro 8 bars, verse 1 stripped beat, pre-chorus build with riser, drop chorus 16 bars full production, verse 2 same as v1, second drop, breakdown bridge, final drop, outro fade` |
| Tempo arc | Energy curve | `low energy verse, building pre-chorus, MAXIMUM energy drop, dynamic break, return to drop, outro reduce` |
| Drop concept (cốt lõi EDM) | Direct rõ | `drop is melodic future bass with chopped vocal hook from main lyric line, supersaw lead carries original melody up an octave` |
| Emotional palette | EDM-friendly | `euphoric, anthemic, neon-lit nostalgia` / `peak-time festival, hands up` (big room) |
| Structural changes | Make transformative | `verse melody simplified to 4-note hook, chorus melody preserved but harmonized with synth stack, bridge fully instrumental drop with vocal chops` |

**Vai trò Artist (Singer)** — vocal direction trong context EDM:

| Yếu tố | Cách viết | Ví dụ |
|---|---|---|
| Vocal character | Bright, processed | `bright forward vocal in pre-chorus, fuller belt in drop, heavy autotune-stylized melisma in bridge` |
| Delivery pace | On-grid hơn Lofi | `on-grid syncopated, energetic from second verse onward` |
| Dynamics | Low verse → big chorus | `intimate mic-close verse, projected belt chorus, scream-belt final chorus` |
| Vocal processing | EDM signature | `light pitch correction, doubled in chorus, harmony stack on drop, vocal chop sample for break section` |
| Vocal effects | Heavy automation | `wide reverb on hook, slap delay on adlibs, telephone EQ effect on bridge intro` |
| Vocal chops (signature EDM) | Make explicit | `chopped vocal phrase from chorus hook, repitched to lead, used as melodic motif in instrumental break` |
| Phrasing reference | Era KHÔNG tên ca sĩ cụ thể | `phrasing in spirit of 2017 festival pop vocal` |

> ⚠️ Cùng cảnh báo Lofi: CẤM tên ca sĩ còn sống ("like Halsey", "Selena Gomez-style") — ELVIS Act risk.

#### Combined Suno prompt — template ghép cho EDM

**Ô "Style of Music":**
```
[Producer]: melodic future bass cover, 128 BPM, up-tuned 2 semitones to E major, 
supersaw lead, reese sub bass, plucked sine bass, sidechained pad, 
4-on-floor kick, layered snare with snap, festival hi-hat shuffle, 
white noise riser, impact crash, heavy sidechain pumping on drop, 
wide stereo mid-band, hot-mastered, wide hall reverb on lead, 
produced like a 2017-era melodic future bass record.

[Songwriter]: intro 8 bars rising pad, verse 1 stripped beat with pluck, 
pre-chorus 8-bar build with riser, drop chorus 16 bars full production, 
chopped vocal hook on instrumental break, second verse same as first, 
big drop, breakdown bridge, final drop, outro fade. 
Euphoric, anthemic, neon-lit nostalgia.

[Artist]: bright forward vocal in pre-chorus, projected belt chorus, 
scream-belt final chorus, on-grid syncopated phrasing, 
light pitch correction, doubled in chorus, harmony stack on drop, 
chopped vocal phrase from main hook used as melodic motif in break. 
Wide reverb on hook, slap delay on adlibs, telephone EQ on bridge intro. 
Phrasing in spirit of 2017 festival pop vocal.
```

---

### 5.2 Midjourney — Visual Prompts

**Style prefix chung:**
```
--style raw --ar 16:9 --q 2 --v 6.1 --stylize 250
```

#### BRIGHT/CUT series (Future Bass / Melodic Dubstep)
```
abstract neon pink and cyan light grid stretching to vanishing point, 
glowing geometric particles floating, dark void background, 
chromatic aberration on edges, synthwave aesthetic, ultra-high contrast, 
volumetric light beams, 4k cinematic, no people, no text 
--ar 16:9 --style raw --v 6.1 --stylize 250
```

#### AFTER HOURS series (Synthwave / Retrowave)
```
1980s retrofuturist highway at sunset, neon palm tree silhouettes, 
gridded purple sunset, distant chrome buildings, magenta haze, 
synthwave aesthetic, deep teal sky with stars, anamorphic lens flare, 
no people, no text, ultra cinematic --ar 16:9 --style raw --v 6.1 --stylize 250
```

#### PULSE series (Big Room / Mainstage)
```
massive festival main stage with laser beams cutting through fog, 
golden hour stage lights, crowd silhouette in distance only as dark mass, 
neon pyro sparks, ultra-wide angle photography, dynamic perspective, 
high contrast, no individual people visible, only festival atmosphere 
--ar 16:9 --style raw --v 6.1 --stylize 250
```

#### NEON series (Tropical House)
```
tropical beach at golden hour, palm trees silhouette, magenta-orange sky, 
turquoise water with subtle waves, neon-tinted color grading, 
slow-motion bokeh light particles, cinematic film aesthetic, 
no people, no text --ar 16:9 --style raw --v 6.1
```

#### VOLT series (Electro Pop)
```
clean modern studio with neon strip lighting, glowing wireframe geometric shapes, 
deep purple background with magenta accent, polished minimalist composition, 
high gloss reflective surfaces, no people, no text 
--ar 16:9 --style raw --v 6.1 --stylize 250
```

> **Quy tắc visual:** không người nhận diện được; không chữ trên ảnh; không logo brand thật. OK silhouette/blur/crowd as mass.

---

### 5.3 Runway Gen-4 — Animation Prompts

EDM cho phép motion mạnh hơn Lofi (3–5/10). Áp dụng quy tắc static-camera với motion intensity cao hơn:

#### BRIGHT/CUT
```
Prompt: "Static camera. Nothing else moves except light grid pulsing slowly with magenta glow shifting in place, geometric particles drifting slightly. No camera pan, no zoom, no parallax, no tilt. Nothing else moves."
Settings: Motion intensity: 4/10, Duration: 5s (loop), Camera: Static
```

#### AFTER HOURS
```
Prompt: "Static camera. Nothing else moves except sunset gradient shifting very slowly, neon palm silhouettes holding steady, lens flare shimmering in place. No camera pan, no zoom, no parallax, no tilt. Nothing else moves."
Settings: Motion intensity: 3/10, Duration: 5s (loop), Camera: Static
```

#### PULSE
```
Prompt: "Static camera. Nothing else moves except laser beams pulsing slowly through fog in place, stage lights flickering rhythmically, crowd silhouette holding still. No camera pan, no zoom, no parallax, no tilt. Nothing else moves."
Settings: Motion intensity: 5/10, Duration: 5s (loop), Camera: Static
```

#### NEON
```
Prompt: "Static camera. Nothing else moves except light bokeh particles drifting slowly in place, distant water shimmer subtle, palm silhouettes holding. No camera pan, no zoom, no parallax, no tilt. Nothing else moves."
Settings: Motion intensity: 3/10, Duration: 5s (loop), Camera: Static
```

#### VOLT
```
Prompt: "Static camera. Nothing else moves except wireframe shape rotating slowly in place, neon strip flickering gently. No camera pan, no zoom, no parallax, no tilt. Nothing else moves."
Settings: Motion intensity: 4/10, Duration: 5s (loop), Camera: Static
```

**Beat-synced flash technique (advanced):** sau khi có Runway loop, dùng CapCut tạo lớp "flash" (white frame 30% opacity, 2-frame duration) đặt theo bar drops của track → tăng engagement EDM rất rõ.

---

## 6. SEO Templates

### 6.1 Title Formulas

**EDM / Remix Cover (single):**
```
[Song] — [Vocalist Alias] ([Sub-genre] Cover)
```

Sub-genre options: `Future Bass`, `Synthwave`, `Big Room`, `Tropical House`, `Electro Pop`, `Melodic Dubstep`

**Ví dụ thực tế:**
- `Bad Child — KOLE (Future Bass Cover)`
- `Doll House — MIRA (Synthwave Cover)`
- `Long Drives — AYDN (Tropical House Cover)`
- `Cool Kids — S.E.R.A (Big Room Cover)`
- `MAMA SAID — AYDN (Electro Pop Cover)`

Mix set titles:
- `KOLE — BRIGHT/CUT Mix Vol.1 | Future Bass Hits`
- `MIRA — AFTER HOURS Mix Vol.1 | Synthwave Compilation`

**Rules:**
- ✅ Tên bài gốc đầu (search intent của audience)
- ✅ Vocalist EDM alias làm by-line (build identity tách Lofi channel)
- ✅ Sub-genre EDM ở cuối (search intent thứ 2: future bass/synthwave fans)
- ❌ KHÔNG "Remix" trong title (dùng "Cover" để rõ pháp lý — license là cover, không phải remix master gốc)
- ❌ Không emoji
- ❌ Không "AI" trong title
- ❌ Không tên ca sĩ gốc

---

### 6.2 Description Template

```
[1 dòng hook đập, all-caps OK cho hook: "THIS DROP HITS DIFFERENT."]

A [sub-genre] re-imagining of "[Song]" — performed by [Vocalist Alias].
[BPM] BPM. Drop at [time].

🎧 STREAM ON SPOTIFY:
[Smart link]

📀 ABOUT THIS COVER:
Officially licensed cover. Composition rights cleared via [partner].
Vocal performance by [Vocalist Alias] — consented to AI-assisted production.

⏱️ TIMESTAMPS:
00:00 — Intro
[N:NN] — Verse
[N:NN] — Build
[N:NN] — DROP
[N:NN] — Bridge

🎤 SERIES: [BRIGHT/CUT | AFTER HOURS | PULSE | NEON | VOLT] — Episode [N]

🎚️ PRODUCTION:
Vocal: [Vocalist Alias]
Composition: licensed from [partner]
Production: AI-assisted (Suno) with human post-production
Master: -9 LUFS for streaming hotness

✅ All rights cleared. Composition licensed. Vocal consented.
✅ AI-assisted: this video contains synthetic music (YouTube AI label applied).

Subscribe for new EDM covers every Tue · Fri →

#EDMCover #[SubGenre]Cover #[SongTitleNoSpaces] #FestivalCover #ElectronicCover
```

---

### 6.3 Tag List Master

**EDM / Remix Cover — 500 ký tự tags:**
```
edm cover, future bass cover, melodic dubstep cover, [song name], [song name] cover, [song name] edm, [song name] remix, synthwave cover, electronic cover, festival cover, big room cover, tropical house cover, neon cover, edm pop cover, drop cover, melodic future bass, future bass remix, edc style, mainstage music, edm hits 2026
```
(Replace `[song name]` cho từng bài.)

---

### 6.4 Spotify metadata

Khi upload qua DistroKid Musician+ (xem Section 13 — Multi-stream revenue), set metadata như sau:

| Field | Value |
|---|---|
| Track name | `[Song] (Future Bass Cover)` hoặc theo sub-genre (Synthwave/Big Room/Tropical House Cover) |
| Primary artist | `[Vocalist EDM Alias]` ("KOLE", "AYDN", "MIRA", "S.E.R.A") |
| Songwriter credit | Tên đầy đủ songwriter gốc theo composition rights letter |
| Producer credit | `[Channel Brand]` |
| Cover art | 3000×3000 từ Midjourney upscale (series visual) |
| Genre | Electronic |
| Sub-genre | Future Bass / Synthwave / Big Room / Tropical House / Electro Pop (theo series) |
| **AI disclosure** | ✅ Tick "AI-generated content" + DDEX flag |
| **Remix disclosure** | ✅ Tick "Cover/Remix" trong DistroKid |
| Canvas (8s loop) | Vertical 1080×1920, upload riêng qua DistroKid Canvas tool |

---

### 6.5 Spotify Canvas — vertical 8s loop (riêng EDM, critical cho mobile)

Canvas là loop 1080×1920 chiếu trong app Spotify khi track được play. Critical cho EDM (audience trẻ, mobile-first — Spotify Canvas tăng save rate 30–50% theo benchmark):
- Crop visual loop 5s thành vertical (cropped center) → loop 1.6× = 8s
- Hoặc generate riêng vertical từ Midjourney với `--ar 9:16` + chính prompt series
- Audio: tối đa 8s; không có audio overlay (Canvas chỉ là visual layer trên track của bạn)
- Upload qua DistroKid Canvas tool (cần Musician+ plan)
- Format: MP4 H.264, ≤8s, ≤15MB
- Loop seamless: 1 frame đầu = 1 frame cuối

---

## 7. Thumbnail & Visual Guidelines

**Kích thước:** 1280×720px

**Composition:**
- Full-bleed visual từ Midjourney (cùng prompt với visualizer background)
- Text BIG BOLD trên overlay neon glow — đối lập hẳn Lofi minimal text
- Drop indicator: chữ "DROP" hoặc waveform icon ở góc dưới phải

**Text style:**
- Font: Bebas Neue Bold hoặc Druk Wide Bold (sans-serif đậm, không serif italic như Lofi)
- Màu: Hot white `#FFFFFF` với neon glow magenta `#FF2A8E` blur 8px outer glow
- Kích thước: tên bài ~80pt, by-line vocalist alias ~36pt
- Vị trí: center hoặc bottom-third, có thể tilt nhẹ 5° cho dynamic

**Mood:** High-energy, neon-saturated, instant impact. Thumbnail phải đập ngay khi lướt.

**Không làm:**
- ❌ Gradient mềm/pastel (mất EDM energy)
- ❌ Serif font (lẫn với Lofi channel)
- ❌ Người nhận diện được trong khung
- ❌ Title gợi "remix bản gốc của X" — dùng "Cover", không "Remix"
- ❌ Logo brand thật / merch của ca sĩ gốc

**Template Canva setup:**
```
Nền: Midjourney upscale ảnh series (1280×720)
Overlay: Linear gradient transparent → #000000 25% opacity center-only (giữ neon contrast)
Text block: Center hoặc bottom-third, Bebas Neue Bold, white + magenta outer glow
Watermark: "DROP" tag góc dưới phải hoặc waveform icon
```

---

## 8. Production Pipeline — Step by Step

### Tổng thời gian mỗi single video: 100–130 phút (dài hơn Lofi do EDM mastering & beat-synced visuals)

#### Bước 1 — Chọn bài & license vault check (5 phút)
```
1. Chỉ chọn từ Tier 1 (Tier C) trong giai đoạn 1
2. Verify license_vault_edm/[song]/ có đủ 6 file (KHÁC Lofi: thêm file 06):
   - 01_composition_rights.pdf
   - 02_vocal_contract.pdf
   - 03_vocal_sample.wav
   - 04_suno_subscription.png
   - 05_ai_disclosure_draft.txt
   - 06_remix_clause_check.pdf  ← MỚI: xác nhận composition license CHO PHÉP derivative re-arrangement (đổi BPM, key, genre)
3. Nếu thiếu file 06 (remix clause) → REQUEST từ đối tác, KHÔNG release cho EDM
4. Pick series + vocalist alias theo theme library
```

#### Bước 2 — Đảm bảo Suno Voice đã verified (share với Lofi)
```
Voice đã verify cho Lofi channel reuse 100% cho EDM. Cùng voice ID, prompt khác.
Nếu chưa: thực hiện workflow Voice setup từ Lofi plan Bước 2.
```

#### Bước 3 — Generate EDM cover bằng Suno (20 phút)
```
1. Suno → Custom mode
2. Style of Music: dán prompt EDM 3-layer (Section 5.1)
3. Lyrics: lyric gốc
4. Voice: voice của vocalist (alias)
5. Generate 8 variations (EDM khó hơn — drop hit-or-miss, cần nhiều variation)
6. Listen từng variation, focus DROP:
   - Drop có punch không?
   - Vocal chop có catchy không?
   - Build có rõ không?
7. Chọn variation tốt nhất
8. Extend nếu cần (target 3:00–4:00)
9. Download WAV
10. Tên file: edm_[vocalist-alias]_[song-slug]_[series]_v1.wav
    Ví dụ: edm_kole_bad-child_bright-cut_v1.wav
```

#### Bước 4 — Post-production EDM mastering (Logic/Ableton/Audacity, 30 phút)
```
1. Mở WAV trong DAW
2. EQ master bus:
   - High-pass at 30Hz (sub clean)
   - Boost air at 10kHz +1.5dB
3. Sidechain check: kick punch through?
4. Stereo widener trên 200Hz–8kHz (mid-side processing)
5. Sub-bass mono dưới 100Hz
6. Limiter master (iZotope Ozone Elements):
   - Target -9 LUFS integrated
   - True-peak -1dBTP
7. A/B compare với reference EDM track cùng sub-genre
8. Export WAV 48kHz/24-bit: edm_[vocalist]_[song]_MASTER.wav
9. Export MP3 320kbps: edm_[vocalist]_[song]_SPOTIFY.mp3
```

#### Bước 5 — Visual Midjourney + Runway (25 phút)
```
1. Midjourney → prompt theo series (Section 5.2)
2. Generate 4 variations → upscale tốt nhất (Magnific nếu muốn 4K-8K)
3. Save: edm_[vocalist]_[song]_visual.png

4. Runway Gen-4:
   - Upload PNG
   - Prompt theo Section 5.3 (static-camera, motion 3-5/10)
   - Duration: 5s, Camera: Static
5. Download MP4: edm_[vocalist]_[song]_loop.mp4
6. Verify loop seamless
```

#### Bước 6 — Beat-synced visualizer (CapCut, 25 phút)
```
1. New project 1920×1080, 30fps (smoother cho EDM motion)
2. Import MASTER.wav + loop.mp4
3. Loop visual đến khớp audio length
4. Identify DROP moment(s) trong audio (visual waveform)
5. Tại MỖI drop: thêm flash effect:
   - White frame 30% opacity, 2 frames
   - Hoặc zoom punch 102% scale, 4 frames
6. Beat-sync hi-hat: subtle vignette pulse mỗi 4 bars
7. Color shift trên drop: brief magenta tint 4 frames
8. Title card 3s đầu (optional): "[SONG] // [VOCALIST]" Bebas Neue + glitch transition
9. Export:
   - 1920×1080, 30fps, Bitrate 20Mbps, MP4 H.264
10. Tên: edm_[vocalist]_[song]_FINAL.mp4
```

#### Bước 7 — Shorts + TikTok cut với hook drop (15 phút)
```
1. Identify 30s DROP section
2. Vertical 1080×1920:
   - Crop center từ FINAL.mp4
   - Audio: waveform spike during drop (visual react)
   - Text overlay top 3 dòng đầu lyric, then BIG "DROP" caption khi drop hit
3. Variation A: 30s drop only (YouTube Shorts)
4. Variation B: 15s build + drop highlight (TikTok)
5. Export: edm_[vocalist]_[song]_SHORT.mp4 và _TIKTOK.mp4
```

#### Bước 8 — Thumbnail + Spotify Canvas (15 phút)
```
1. Thumbnail 1280×720 (Canva):
   - Background visual.png
   - Big bold text trung tâm "[SONG]"
   - Subtitle "[VOCALIST ALIAS] · [SERIES]"
   - Neon glow magenta outer glow trên text
   - "DROP" watermark góc dưới phải
   - Export PNG

2. Spotify Cover 3000×3000: square crop từ visual + minimal text bottom

3. Spotify Canvas 1080×1920 (8s):
   - Vertical crop từ loop.mp4
   - Loop 1.6× = 8s
   - Subtle text overlay "[SONG]"
   - Export canvas.mp4
```

#### Bước 9 — Metadata + AI disclosure (10 phút)
```
1. Pipeline:
   python pipeline.py generate \
     --channel edm \
     --vocalist kole \
     --song bad-child \
     --series bright-cut \
     --tier C
2. License vault check:
   python pipeline.py vault check --channel edm --song bad-child
   → PASS đủ 6 file (bao gồm remix_clause)
```

#### Bước 10 — Upload + Schedule (10 phút)
```
1. YouTube Studio → Upload FINAL.mp4
   - Title, description, tags
   - Thumbnail, playlist (series tương ứng)
   - ✅ AI tick
   - Schedule

2. DistroKid → Upload SPOTIFY.mp3
   - Cover: spotify.png
   - Canvas: canvas.mp4
   - ✅ AI tick
   - ✅ Cover/Remix tick

3. TikTok / Reels: Upload TIKTOK.mp4 (hashtag #edmcover #futurebass #[song])

4. YouTube Shorts: Upload SHORT.mp4
```

---

### Batch Production (Khuyến nghị)

```
Thứ 2 (3h): Batch Suno generation — 2 single EDM tuần này
Thứ 3 (3h): Batch EDM mastering trong DAW cho cả 2
Thứ 4 (2h): Batch Midjourney + Runway visual cho cả 2
Thứ 5 (3h): Batch CapCut FINAL + SHORT + TIKTOK + thumbnail
Thứ 6 (1h): Metadata + upload schedule
```

**Tổng thời gian/tuần:** ~12 giờ cho 2 single + 2 short + 2 TikTok cut

---

## 9. Tool Stack & Chi phí

### EDM / Remix Cover Stack (~$20/tháng thêm so với Lofi — share tool, thêm mastering)

Dùng lại hầu hết tool từ Lofi (Suno Premier, Midjourney, Runway, CapCut, Canva, DistroKid, TubeBuddy). Chỉ cần thêm tool mastering EDM:

| Tool | Mục đích | Chi phí |
|---|---|---|
| (đã có từ Lofi) Suno Premier + Midjourney + Runway + CapCut + Canva + DistroKid + TubeBuddy | Share workflow | (đã trả ~$95/tháng) |
| Logic Pro / Ableton Live Lite | EDM mastering (cần cho hot -9 LUFS master) | $200 one-time (Logic) / $99/năm (Ableton Lite) |
| iZotope Ozone Elements | Master limiter EDM-grade | $79 one-time |
| DistroKid Musician+ | Multiple Spotify artist profile (4 alias) | $36/năm (~$3/tháng) |
| **Incremental cho EDM** | | **~$15–20/tháng** thêm |

**Tổng chi phí 2 kênh cùng lúc:** ~$115/tháng (share + EDM tools).

### Optional Tools (nâng cấp sau tháng 3)

| Tool | Khi nào cần | Chi phí |
|---|---|---|
| Serum / Vital VST | Khi muốn manual produce EDM (không 100% Suno) | $189 one-time / Free |
| Splice Sounds | Sample library drum + vocal chops | $13/tháng |
| Magnific AI | Thumbnail 8K cho hero releases viral | $39/tháng |
| Lalal.ai Pro | Stem split vocal Suno output để re-mix | $13/tháng |

### Reference EDM track library (free)

Để A/B compare khi mastering, build playlist private trên Spotify với 10 reference tracks per sub-genre:
- 10 future bass references → benchmark cho BRIGHT/CUT mastering
- 10 synthwave references → benchmark cho AFTER HOURS
- 10 big room references → benchmark cho PULSE
- 10 tropical house references → benchmark cho NEON
- 10 electro pop references → benchmark cho VOLT

Sử dụng: khi master xong 1 track Suno, A/B compare với 2-3 reference đầu playlist tương ứng. Match LUFS, low-end punch, stereo width của reference — nếu lệch nhiều, re-master.

---

## 10. Automation Script — Hướng dẫn sử dụng

File: `pipeline.py` (share với Lofi/ASMR/Soundscapes, --channel edm)

### Cài đặt

```bash
pip install rich click colorama
python pipeline.py --help
```

### Các lệnh chính

#### Tạo metadata cho 1 video
```bash
python pipeline.py generate \
  --channel edm \
  --vocalist kole \
  --song bad-child \
  --series bright-cut \
  --tier C \
  --date 20260603
```

Output:
```
📺 TITLE OPTIONS:
  1. Bad Child — KOLE (Future Bass Cover)
  2. Bad Child — KOLE (Melodic Future Bass · BRIGHT/CUT ep.04)
  3. Bad Child — KOLE (EDM Cover) — Drop hits at 1:32

📝 DESCRIPTION: [filled template saved]
🏷️  TAGS: [saved]
📁 FILENAME: edm_kole_bad-child_bright-cut_FINAL.mp4
🎵 SUNO PROMPT: [3-layer EDM ghép saved]
🖼️  MIDJOURNEY PROMPT: [bright-cut series saved]
🎬 RUNWAY PROMPT: [bright-cut series saved]
```

#### License vault check (EDM-specific — 6 file)
```bash
python pipeline.py vault check --channel edm --song bad-child
# Returns PASS/FAIL. EDM yêu cầu thêm file 06_remix_clause_check.pdf
```

#### Quản lý upload queue
```bash
python pipeline.py queue add \
  --channel edm \
  --file edm_kole_bad-child_bright-cut_FINAL.mp4 \
  --date 2026-06-03 \
  --time 18:00

python pipeline.py queue list
python pipeline.py queue done --id 5
```

#### Đặt tên file hàng loạt
```bash
python pipeline.py rename --folder ./raw_exports --channel edm
```

#### Xem content calendar
```bash
python pipeline.py calendar --channel edm --month 2026-06
```

---

## 11. Content Calendar — 3 tháng đầu

### Tháng 1 — Launch Tier C only

**Tuần 1:** (Setup tuần)
| Ngày | Video | Theme |
|---|---|---|
| T2 | Setup | Channel art, brand assets, first single prep |
| T3 | Upload 1 | KOLE — Bad Child (BRIGHT/CUT, Tier C, 3:30) |
| T6 | Upload 2 | MIRA — Doll House (AFTER HOURS, Tier C, 3:30) |

**Tuần 2:** AYDN — Long Drives (NEON) / KOLE — Rx (BRIGHT/CUT) / Mix Set Vol.1 (compilation)

**Tuần 3:** S.E.R.A — Cool Kids (PULSE, Tier B đã verify) / MIRA — Talking Body (NEON, Tier C)

**Tuần 4 — Review:**
- Content ID claim status check — bao nhiêu bài bị claim sau 4 tuần?
- Top performing series + vocalist combo
- Drop hit nào viral nhất → double down sub-genre đó
- Điều chỉnh upload schedule nếu cần

**Mục tiêu Tháng 1:**
- ✅ 8 single + 1 mix set (9 video chính)
- ✅ Xác định được top 2 series + top 2 vocalist alias
- ✅ Watch hours target: 150h (lower than Lofi vì AVD EDM ngắn hơn)
- ✅ Content ID claim rate < 40% — nếu > 50% phải re-evaluate

---

### Tháng 2 — Scale + Spotify push

**EDM — Upload 3 video/tuần:**
- 2 single mới (mix Tier C + Tier B verified)
- 1 mix set/2 tuần

**Spotify push (Tuần 2 tháng 2):**
- Upload 5 single tốt nhất Tháng 1 qua DistroKid
- Submit editorial pitch: "Future Bass" / "Synthwave Hits" / "Festival Anthems"
- Build artist profile riêng cho mỗi alias (KOLE, MIRA, AYDN, S.E.R.A) — DistroKid Musician+
- Spotify Canvas active cho mỗi track

**Tháng 2 targets:**
- ✅ 12 single + 2 mix set (running total: 23)
- ✅ Watch hours: 600h (cumulative)
- ✅ Subscribers: 200–500
- ✅ Spotify monthly listeners: 50+ per alias
- ✅ Bắt đầu Shorts daily + TikTok daily

---

### Tháng 3 — Decision point + Monetize push

**Cuối tháng 3 đánh giá CRITICAL:**
- Tỷ lệ Content ID claim < 30%? → Continue, mở dần Tier B
- Tỷ lệ > 50%? → **PIVOT** sang "EDM Originals" với composition gốc của partner (đề nghị 10–20 bài original không phải cover)

**EDM: Upload 3 video/tuần**

**Theme focus Tháng 3:**
```
Week 1: KOLE — BRIGHT/CUT Mix Vol.2 | Future Bass Compilation 1h
Week 2: AYDN — NEON Mix Vol.1 | Tropical House Summer Compilation
Week 3: Festival anthem singles push (PULSE series) — chuẩn bị Summer festival season Q3
Week 4: First ambient EDM loop test — "EDM Workout 4-Hour Mix"
```

**Tháng 3 targets:**
- ✅ 12 single + 4 mix set (running total: 39)
- ✅ Watch hours: 2,500–4,000h → cố gắng apply YPP nếu ≥ 4K
- ✅ Subscribers: 800–1,000
- ✅ Spotify monthly listeners: 200+ per alias
- ✅ Content ID claim rate < 30% trong tháng 3

---

### Shorts Strategy

**Format:** Cắt 30–60 giây drop highlight từ video chính

**EDM Shorts:**
- Tiêu đề: `[Song] — [Vocalist] · DROP (30s preview)`
- Call to action: `Full version on the channel →`

**Upload Shorts:** Hàng ngày, 7:00 PM EST (peak time US audience trẻ EDM)

---

## 12. KPI & Success Metrics

### Metrics cần track mỗi tuần (30 phút review)

#### Performance Metrics
| Metric | Target (Tháng 3) |
|---|---|
| Total watch hours | 2,500–4,000h |
| Subscribers | 800–1,000 |
| Average View Duration | > 50% (≥ 1:45 cho single 3:30) hoặc > 20 phút cho mix set 30-60 phút |
| CTR (Click-through rate) | > 5% (EDM thumbnail high-impact) |
| Impressions/tuần | Growing 15%+ |

#### Content Metrics
| Metric | Xem ở đâu | Đọc như thế nào |
|---|---|---|
| Average View Duration | YouTube Analytics > Content | Single < 40% AVD → drop weak, re-generate Suno với prompt mạnh hơn |
| CTR | YouTube Analytics > Reach | < 2%: thay thumbnail (text more glow, color more contrast). < 1%: thay luôn series visual |
| Content ID claim rate / month | YouTube Studio Copyright | **CRITICAL**: target < 30%. > 50% trong 2 tháng = pivot |
| Successful dispute rate | YouTube Studio Copyright | Target > 70%. > 30% rejected = composition rights letter có gap |
| Spotify save rate | DistroKid stats | > 15% = track có sticking power |
| TikTok views/video | TikTok analytics | > 5K trung bình. Viral spike → push lên Spotify ngay |

### Dấu hiệu cần can thiệp ngay

- ❗ Strike YouTube → take down channel toàn bộ, audit + escalate đối tác composition
- ❗ Spotify pull track → check remix clause với đối tác, có thể redo bài đó sang Lofi version
- ❗ Multiple failed disputes (> 30%) → composition rights letter không đủ → request đối tác ban hành phiên bản đầy đủ hơn với sync + derivative rights ghi rõ
- ❗ Content ID claim rate > 50% trong tháng 3 → trigger PIVOT plan B (re-launch as "EDM Originals")

---

## 13. Monetization Checklist

### YouTube Partner Program — Apply khi đủ điều kiện

- [ ] 1,000 subscribers
- [ ] 4,000 public watch hours (12 tháng qua)
- [ ] Không có community guideline strikes
- [ ] 2-step verification bật
- [ ] Đã tick "Altered or synthetic content" trên mọi video AI

### YouTube Policies — Phải pass tất cả

- [ ] **Inauthentic content**: Mọi video có beat-synced visual + dynamic motion
- [ ] **Reused content**: Mix set không share > 30% với single đã upload (re-mix nhẹ trong compilation)
- [ ] **AI disclosure**: Tick "Altered/synthetic content" 100% video
- [ ] **Advertiser-friendly**: Không content nhạy cảm, không NSFW
- [ ] **Content ID**: Track claim rate hàng tháng < 30%

### Cover Song + EDM Compliance Gates — KHẮT KHE HƠN LOFI

Vì EDM remix có rủi ro Content ID + derivative rights, mỗi video phải qua compliance gate **11 ô** (Lofi có 8):

- [ ] **Composition rights** có sync + mechanical + scope global + thời hạn còn hiệu lực cho bài này
- [ ] **Remix clause** xác nhận (`06_remix_clause_check.pdf`) — derivative re-arrangement OK
- [ ] **Vocal contract** đủ 6 điều khoản AI
- [ ] **Suno subscription** Pro/Premier active tại thời điểm generate
- [ ] **Suno Voice** của vocalist đã verify
- [ ] **Tier C only** trong giai đoạn 1 (hoặc Tier B với sync letter cụ thể)
- [ ] **AI disclosure** trên YouTube + TikTok + Spotify
- [ ] **Description** ghi rõ vocal + composition + AI-assisted
- [ ] **License vault** đủ 6 file (Lofi chỉ 5)
- [ ] **Visual + thumbnail** không có người + không brand thật + không tên ca sĩ gốc
- [ ] **Title dùng "Cover"** không "Remix" (rõ pháp lý: license là cover, derivative re-arrangement OK)

Không tick đủ 11 → KHÔNG upload. Có sẵn template dispute (xem dưới) cho mỗi lần claim.

#### Content ID dispute template (EDM)

```
Subject: Disputed Content ID claim — [Video URL]

The video at [URL] features a fully cleared cover of "[Song]" 
performed by [Vocalist Alias], whose vocal performance is consented.

Underlying composition is licensed from [Partner Company] 
under composition license [LICENSE_REF], which authorizes:
1. Sync rights for video distribution on YouTube
2. Derivative re-arrangement including tempo, key, and genre changes
3. Global geographic scope
4. Term valid through [DATE]

Attached: composition rights letter, vocal contract, AI disclosure record.

Please release this Content ID claim.

Best regards,
[Channel Owner]
```

#### Quarterly compliance review (EDM-specific, khắt khe hơn Lofi)

Mỗi 3 tháng:
- [ ] Download lại Suno ToS, lưu PDF với timestamp
- [ ] Kiểm tra YouTube AI policy + Content ID policy update
- [ ] Kiểm tra Spotify policy + DistroKid AI rules
- [ ] Audit license vault: check expiry dates cho từng bài
- [ ] **Remix clause audit** (KHÁC Lofi): có bài nào đối tác đã rút clause hoặc thay đổi không?
- [ ] Theo dõi Sony v Suno tracker (chartlex.com, mckoolsmith.com AI litigation)
- [ ] **Content ID claim log audit** (CRITICAL): tỷ lệ claim/upload tháng vừa qua → nếu > 50% trong 2 tháng liên tiếp = **trigger pivot plan B** (re-launch as "EDM Originals")
- [ ] Strike count: nếu có bất kỳ strike nào → audit toàn bộ catalogue, có thể xóa video đó luôn

### Sau khi monetize — Optimize RPM

1. **Mid-roll OK trong mix set** — audience EDM bao dung mid-roll, khác Lofi
2. **Q4 push** — festival season recap + holiday + high CPM (tháng 11–12)
3. **Spotify Canvas critical** — increase save rate 30–50% theo benchmark (EDM mobile-first)
4. **TikTok virality moment** — 1 clip viral có thể đẩy track lên Spotify editorial — viral = 100K–1M streams

### Dòng doanh thu thứ 2 — Spotify + Sync premium + Pivot

**Spotify streaming:**
- Upload qua DistroKid Musician+ (4 artist profile riêng cho 4 alias)
- Spotify Canvas vertical loop 8s — must-have cho EDM mobile audience
- Submit editorial: Future Bass, Synthwave Hits, Festival Anthems, Workout Pop
- Revenue: ~$0.003–0.005/stream, EDM viral spike có thể tạo 100K–1M stream nhanh

**Sync license premium (EDM cao hơn Lofi):**
- Sau 6 tháng có catalogue 30+ EDM cover, pitch sync tới gym, sport brand TVC, action film, mobile game
- EDM sync premium $500–$3000/sync — cao hơn Lofi 2–3x

**Pivot plan B — "EDM Originals" (long-term, sau 6 tháng):**
- Đề nghị đối tác composition cung cấp 10–20 bài original (composition mới do partner sở hữu 100%, không phải cover)
- Re-launch channel theme: "EDM Originals featuring [Vocalist Aliases]"
- KHÔNG còn Content ID risk vì composition mới
- Channel signal đã build từ cover giúp originals catch on nhanh
- Đây là exit strategy có sẵn — không phải fallback ngỡ ngàng

---

*Dùng kết hợp với:*
- *`Channel_Launch_Plan_Lofi_Acoustic.md` (kênh test #1, low-risk, launch trước)*
- *`Brief_canh_tranh_AI_Cover_Suno_2026.docx` (legal foundation + cảnh báo EDM Section 9.2)*
- *`pipeline.py` (extend với --channel edm)*

*Cập nhật lần cuối: 2026-05-10*
*Chú ý: kế hoạch này chứa cảnh báo rủi ro cao. Đọc lại Brief Section 4.1 và 9.2 trước khi triển khai. Sẵn sàng pivot sang "EDM Originals" sau 6 tháng nếu Content ID không kiểm soát được (claim rate > 50% liên tục).*
