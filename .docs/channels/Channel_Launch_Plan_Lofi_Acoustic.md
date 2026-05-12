# Channel Launch Plan — Lofi / Acoustic Cover

> Kênh AI cover Lofi/Acoustic — tái diễn giải các bài US/UK pop bằng vocal đã ký hợp đồng và composition đã có quyền tác giả qua đối tác.
> Cập nhật: 2026-05-10

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

| Tiêu chí | Lofi / Acoustic Cover |
|---|---|
| **Focus** | Lofi acoustic re-imagining của catalogue US/UK pop covers |
| **Audience** | 18–34, Gen Z + late Millennials, study/work/relax/late-night listeners |
| **Video length** | 3–5 phút single · 30–60 phút compilation · 1–8h ambient loop |
| **Upload frequency** | 3 video/tuần (1 single + 1 lyric + 1 long-form) |
| **RPM ước tính** | $4–$8 |
| **Advertiser category** | Productivity, education, wellness, lifestyle apps |
| **Music style** | Acoustic + lofi: real piano/guitar, brushed drums, vinyl crackle, vocal foreground, intimate close-mic |
| **Visual style** | Warm cozy — bedroom/café/rainy window, low motion ambient loop |
| **Time to monetize** | 4–6 tháng (cover song = sync license workflow phức tạp) |
| **Launch order** | **Tháng 1** (test #1, ưu tiên trước EDM channel) |

### Vì sao Lofi/Acoustic là kênh test #1

Theo `Brief_canh_tranh_AI_Cover_Suno_2026.docx`:
- **Content ID rủi ro thấp nhất** — acoustic tempo + key change làm fingerprint khác biệt rõ với master gốc, vẫn có thể bị flag nhưng tỷ lệ thấp hơn EDM/Remix.
- **Audience bao dung với loop dài** — Lofi Girl ($3.5M/năm, 15M sub) chứng minh format ambient compilation hấp thụ tốt cover/instrumental.
- **Spam filter Spotify thân thiện hơn** — playlist chill/lofi có nhiều cover acoustic hợp pháp; không bị tag "spammy uploader" nếu cadence vừa phải.
- **RPM ổn định** — ad category là productivity/wellness/edu, advertiser-friendly.

---

## 2. Brand Identity

**Tên kênh:** *(gợi ý, chọn 1)*
- `Slow Lights`
- `Velvet Acoustic`
- `Window Light Sessions`
- `Soft Replay`
- `The Quiet Cover`

**Tagline:** *"Songs you love. Slowed down. Made warm."*

**Brand colors:**
- Primary: Warm cream `#F5E6D3`
- Secondary: Soft terracotta `#C97B5A`
- Accent: Forest green `#3F5641` (dùng cho text trên thumbnail)
- Background: Off-white linen `#FAF6EF`

**Brand voice:**
- Intimate, thoughtful — như một DJ đêm khuya kể chuyện
- Mô tả nhạc qua hình ảnh giác quan (a coffee shop at 11pm, raindrops on a bedroom window)
- Description luôn mời người nghe đặt mình vào một không gian cụ thể

**Channel art:**
- Avatar: minimal mark — vòng tròn lệch tâm + tia sáng nhỏ (gợi vinyl/mặt trăng), nền cream `#F5E6D3`, mark forest green `#3F5641`
- Banner: ảnh window-side coffee scene + tagline serif italic (Cormorant Garamond) căn giữa safe area 1546×423

**Vocal personas (AI vocalists as IP):**
Bốn vocalist (ALLEN_1..4) được đặt nghệ danh riêng, build identity nhất quán xuyên series:

| Vocalist folder | Alias | Series concept | Ví dụ episode title |
|---|---|---|---|
| ALLEN_1 | `Aiden` | *"Bedside Lights"* — bài hát hát lúc 1 giờ sáng | "Aiden — Marvin Gaye (Bedside Lights ep.04)" |
| ALLEN_2 | `Mara` | *"Window Sessions"* — gần gũi, phòng khách acoustic | "Mara — Wonderful Tonight (Window Sessions ep.02)" |
| ALLEN_3 | `Cole` | *"Quiet Roads"* — hơi raspy, đường vắng đêm khuya | "Cole — Another Love (Quiet Roads ep.07)" |
| ALLEN_4 | `Sera` | *"Daydream Tape"* — dreamy, soft reverb | "Sera — Heathens (Daydream Tape ep.03)" |

Series number tăng dần theo thời gian → builds back-catalogue + binge-watching behavior.

---

## 3. Content Strategy — Theme Library

Catalogue: 77 bài tại `working-music/music-vocals/vocal usuk/Vocal us uk Cover/ALLEN_[1-4]/`. Mỗi bài có 1 file `[SONG]_VOCAL.wav` (acapella).

#### Format mix — mỗi bài được khai thác qua 6 format

| # | Format | Thời lượng | Mục đích | Upload ở đâu |
|---|---|---|---|---|
| 1 | **Single visualizer** | 3–5 phút | Doanh thu YouTube ad + push lên Spotify | YouTube long-form + Spotify (qua DistroKid) |
| 2 | **Lyric video** | 3–5 phút | Engagement cao, audience hát theo, search "song name lyrics" | YouTube long-form (re-release 1 tuần sau single) |
| 3 | **Compilation** | 30–60 phút | "Best of [Vocalist]" — boost watch hours | YouTube long-form (1 video/2 tuần) |
| 4 | **Ambient loop** | 1–8 giờ | Background work/study, chiến thuật Lofi Girl | YouTube long-form (1 video/4 tuần) |
| 5 | **YouTube Shorts** | 30–60 giây | Discovery, viral hook | YouTube Shorts (hàng ngày) |
| 6 | **Reel/TikTok** | 15–30 giây | Discovery + drive Spotify stream | TikTok + Instagram Reels (hàng ngày) |

#### Phân bổ tuần (3 video upload chính + Shorts hàng ngày)

```
Thứ 2: Single visualizer (Tier 1 — Tier C catalogue)
Thứ 4: Lyric video của single tuần trước
Thứ 6: Compilation HOẶC Ambient loop (luân phiên 2 tuần)

Daily: 1 Short (cắt từ pipeline)
TikTok/Reels: 1 clip/ngày, slightly different cut từ Short
```

#### Tier 1 — Tier C catalogue (Launch trước, rủi ro Content ID thấp nhất)

Bài ít nổi tiếng — Content ID fingerprint thưa, publisher ít gắt. Đây là core uploads (50%+ content) trong Tháng 1.

| Theme | Title Formula | Vocalist gợi ý | Video Length |
|---|---|---|---|
| Rx | Rx — Cole (Lofi Acoustic Cover) | Cole | 4 phút |
| Void | Void — Mara (Lofi Acoustic Cover) | Mara | 4 phút |
| Doll House | Doll House — Sera (Lofi Acoustic Cover) | Sera | 4 phút |
| Gingerbread Man | Gingerbread Man — Cole (Acoustic Cover) | Cole | 4 phút |
| MAMA SAID | MAMA SAID — Aiden (Lofi Acoustic Cover) | Aiden | 4 phút |
| Talking Body | Talking Body — Mara (Acoustic Cover · Slowed) | Mara | 4 phút |
| Long Drives | Long Drives — Aiden (Lofi Acoustic Cover) | Aiden | 4 phút |
| All Yourn | All Yourn — Mara (Lofi Acoustic Cover) | Mara | 4 phút |
| Bad Child | Bad Child — Cole (Acoustic Cover · Slowed) | Cole | 4 phút |
| Sunrise | Sunrise — Sera (Lofi Acoustic Cover) | Sera | 4 phút |
| Walking Away | Walking Away — Aiden (Acoustic Cover) | Aiden | 4 phút |

#### Tier 2 — Tier B catalogue (Sau khi verify sync license cụ thể)

Hits trung bình. Release sau khi đối tác composition xác nhận sync rights cụ thể từng bài.

| Theme | Title Formula | Video Length |
|---|---|---|
| House of Memories | House of Memories — Aiden (Lofi Acoustic Cover) | 4 phút |
| Another Love | Another Love — Cole (Lofi Acoustic Cover) | 4 phút |
| Hey There Delilah | Hey There Delilah — Cole (Acoustic Cover) | 4 phút |
| Heathens | Heathens — Sera (Acoustic Cover · Slowed) | 4 phút |
| 7 Years | 7 Years — Aiden (Lofi Acoustic Cover) | 4 phút |
| Prayer in C | Prayer in C — Sera (Acoustic Cover) | 4 phút |
| Wonderful Tonight | Wonderful Tonight — Mara (Acoustic Cover) | 4 phút |
| Stressed Out | Stressed Out — Cole (Lofi Acoustic Cover) | 4 phút |
| We Don't Talk Anymore | We Don't Talk Anymore — Aiden (Lofi Cover) | 4 phút |
| Marvin Gaye | Marvin Gaye — Aiden (Acoustic Cover · Slowed) | 4 phút |

#### Tier 3 — Tier A catalogue / Long-form / Seasonal

Tier A hits (24K Magic, A Sky Full of Stars, Careless Whisper, Toxic, Dance Monkey) — **chỉ release sau khi có sync letter cụ thể từng bài + đã monetize**. Trong giai đoạn pre-monetize, dùng các bài Tier A trong COMPILATION/LOOP (audio mức rủi ro thấp hơn so với single visualizer).

Long-form format (luân phiên mỗi 2-4 tuần):
- Compilation 30-60 phút "Best of [Vocalist]"
- Ambient loop 1-8h "Lofi Acoustic Covers Compilation"

| Theme | When to post |
|---|---|
| "Late Night Sleep Acoustic Covers — 8h" loop | Quanh năm, evergreen |
| "Rainy Day Acoustic Covers — 4h" loop | Spring/Fall |
| "Christmas Acoustic Covers" compilation | Tháng 12 |
| "Study With Me Acoustic Covers — 3h" loop | Tháng 4–5 & 11–12 (exam season) |

#### Upload Mix hàng tuần

```
Tuần 1: Tier 1 (single) + Tier 1 (lyric version 1 tuần sau) + Tier 1 (single)
Tuần 2: Tier 1 (single) + Tier 1 (lyric) + Long-form compilation
Tuần 3: Tier 1 (single) + Tier 2 (single) + Tier 1 (lyric)
Tuần 4: Tier 1 (single) + Tier 1 (lyric) + Ambient loop long-form
...repeat
```

---

## 4. Đặc điểm âm thanh

**Nguyên tắc âm thanh:**
- BPM giảm 10–25% so với bản gốc (ví dụ "24K Magic" 107 BPM → 75 BPM acoustic)
- Key có thể giảm 1–2 nửa cung để hợp với vocal mới
- Stripped instrumentation: nylon guitar + upright piano + brushed drums + soft bass + subtle pad
- Vinyl crackle layer rất nhẹ (-22dB) — signature lofi
- Mix character: warm tape saturation, slight low-pass trên 8kHz, intimate close-mic vocal
- Master target -14 LUFS (Spotify standard), không over-compress

**Volume mix:**
```
Lead vocal (vocal AI cover): 0dB reference
Acoustic guitar rhythm: -8dB
Upright piano: -10dB
Soft DI bass: -12dB
Brushed drums: -14dB
Ambient pad: -18dB
Vinyl crackle bed: -22dB
Room tone: -24dB
```

---

## 5. Prompt Templates

> Đây là phần quan trọng nhất với kênh AI cover. Prompt Suno được tổ chức theo **framework 3 vai trò** (Producer / Songwriter / Artist) — bạn vẫn ghép tất cả vào một string Suno duy nhất, nhưng tách mental layers giúp prompt cohesive thay vì throw mood adjectives.

### 5.1 Suno AI — Music/Audio Prompts

**Format chung (cho cover song trong Suno Custom Mode):**
- Ô **Style of Music** = ghép 3 layer (Producer + Songwriter + Artist) như template dưới
- Ô **Lyrics** = dán lyric gốc của bài
- Ô **Voice** = chọn voice đã verified của vocalist tương ứng (xem Section 8 Bước 2)
- Ô **Exclude Styles** = `dance, EDM, drum machine, autotune, electronic drums, distorted guitar, screamed vocals, rap`

#### Framework 3 vai trò khi soạn prompt

**Vai trò Producer** quyết định production palette:

| Yếu tố | Cách viết | Ví dụ |
|---|---|---|
| Sub-genre cụ thể | Không chỉ "lofi" | `lo-fi acoustic indie folk cover` |
| BPM | Số rõ ràng | `75 BPM` |
| Key direction | Major/minor + down-tune nếu cần | `in original key down-tuned 1 semitone` |
| Instrumentation | 4–6 nhạc cụ chính | `nylon-string guitar, upright piano, brushed drums, soft DI bass, ambient pad` |
| Mix character | Texture từ ngữ cụ thể | `warm tape saturation, slight low-pass at 8kHz, vinyl crackle bed, intimate close-mic vocal` |
| Reverb / space | Cảm giác không gian | `small room reverb, dry vocal in foreground` |
| Production reference | Era/genre KHÔNG tên ca sĩ còn sống | `produced like a Bon Iver-era folk record` |

**Vai trò Songwriter** quyết định structural & emotional framework (re-arrangement, KHÔNG viết mới — bài đã có):

| Yếu tố | Cách viết | Ví dụ |
|---|---|---|
| Arrangement form | Giữ nguyên / đơn giản hóa | `arrangement stays close to original verse-chorus, stripped to half tempo` |
| Tempo arc | Dynamic shape | `gentle build through verse 1, soft drop into chorus, intimate bridge, fade outro` |
| Emotional palette | Multi-layer adjective | `nostalgic, late-night, slightly melancholic but warm — not sad` |
| Melodic sensibility | Cách melody xử lý lyric | `melody faithful to original but with longer sustained notes; breath placement relaxed` |
| Touchstones | Album/producer era — KHÔNG tên cụ thể | `in the spirit of Sufjan Stevens "Carrie & Lowell"` |
| Outro behavior (quan trọng cho loop) | Mô tả ending | `final chord rings out 8 seconds, no hard stop — designed to flow into next track` |

**Vai trò Artist (Singer)** quyết định vocal direction cho bài cụ thể (Suno Voice đã có "tone color", prompt direct DELIVERY):

| Yếu tố | Cách viết | Ví dụ |
|---|---|---|
| Vocal character | Quality adjective | `breathy intimate verse, fuller chest in chorus, falsetto on bridge` |
| Delivery pace | Rhythmic feel | `laid-back, slightly behind the beat — never rushed` |
| Dynamics | Soft → loud arc | `whisper-quiet first verse, gradual rise to medium dynamics in chorus, return to whisper outro` |
| Harmonies | Solo / doubled / stacked | `solo verse, light double-tracked harmony in chorus (not full stacks)` |
| Vocal effects | Dry/wet | `dry vocal in foreground, light plate reverb tail, subtle slap delay on phrase ends` |
| Phrasing reference | Era — CẤM tên ca sĩ còn sống | `phrasing in the spirit of late-2000s indie folk female vocal` |

> ⚠️ **CẤM trong vocal prompt:** tên ca sĩ nổi tiếng còn sống cụ thể ("like Taylor Swift", "Drake-style"). Đây là vùng ELVIS Act + NO FAKES Act — bạn có thể bị nhắm dù vocal có consent. Luôn dùng "in the spirit of [era/genre]".

#### Combined Suno prompt — template ghép

**Ô "Style of Music" — ghép Producer + Songwriter + Artist:**
```
[Producer]: lo-fi acoustic indie folk cover, 75 BPM, in original key down-tuned 1 semitone, 
nylon-string guitar, upright piano, brushed drums, soft DI bass, ambient pad, 
warm tape saturation, slight low-pass at 8kHz, vinyl crackle bed, small room reverb, 
produced like a Bon Iver-era folk record.

[Songwriter]: arrangement stays close to original verse-chorus, half tempo, 
gentle build, soft drop into chorus, intimate bridge, fade outro with chord ringing 8 seconds. 
Nostalgic, late-night, melancholic but warm. In the spirit of Sufjan Stevens "Carrie & Lowell".

[Artist]: breathy intimate verse, fuller chest in chorus, light falsetto on bridge, 
laid-back behind-the-beat, whisper-quiet rise to medium dynamics, 
solo verse with light double-tracked harmony in chorus. 
Dry vocal foreground, plate reverb tail, slap delay on phrase ends.
```

---

### 5.2 Midjourney — Visual Prompts

**Style prefix chung:**
```
--style raw --ar 16:9 --q 2 --v 6.1
```

Mỗi series có 1 visual concept consistent — dùng cùng prompt structure cho mọi bài thuộc series đó (chỉ adjust object/season nhỏ), tạo brand recognition.

#### Aiden series — "Bedside Lights" (1AM intimate)
```
1AM bedroom warm dim lamp on bedside table, vinyl record player turning, 
unmade bed with soft cotton sheets, half-empty mug of tea, raindrops streaking window beyond, 
warm cream and terracotta tones, photorealistic 35mm film grain, 
shallow depth of field, no people, intimate solitary atmosphere 
--ar 16:9 --style raw --v 6.1
```

#### Mara series — "Window Sessions" (afternoon contemplative)
```
afternoon golden hour through linen curtains, vintage upright piano in living room corner, 
worn velvet armchair, open notebook with handwritten lyrics, dust motes in light beam, 
warm beige and forest green palette, photorealistic 35mm, soft focus background, 
no people, contemplative quiet --ar 16:9 --style raw --v 6.1
```

#### Cole series — "Quiet Roads" (late-night drive)
```
empty rural highway at 2AM, headlights cutting through light fog, 
single yellow streetlight pool ahead, silhouette of pine trees, 
faint stars above, deep teal and amber tones, cinematic photography, 
slight motion blur on roadside, no people, lonely contemplation 
--ar 16:9 --style raw --v 6.1
```

#### Sera series — "Daydream Tape" (dreamy soft pastels)
```
sunlit attic window with billowing sheer curtain, vintage cassette tape on wooden floor, 
dried flowers in glass jar, soft pastel cream and lavender palette, 
hazy bokeh light, dreamy soft focus, photorealistic with painterly tone, 
no people, nostalgic afternoon --ar 16:9 --style raw --v 6.1
```

> **Quy tắc visual:** không có người trong khung (tránh implication vocalist = nhân vật ảnh); không chữ trên ảnh (overlay khi làm thumbnail); không logo brand thật.

---

### 5.3 Runway Gen-4 — Animation Prompts

Áp dụng quy tắc static-camera (xem memory `feedback_runway_static_camera.md`): camera directive ở token đầu tiên, dùng "in place" anchor, kết thúc "Nothing else moves." Motion intensity thấp (2–3/10) cho Lofi.

#### Aiden / Bedside Lights
```
Prompt: "Static camera. Nothing else moves except vinyl record turning slowly in place, lamp light flickering very gently, raindrops streaking window. No camera pan, no zoom, no parallax, no tilt. Nothing else moves."
Settings: Motion intensity: 2/10, Duration: 5s (loop), Camera: Static
```

#### Mara / Window Sessions
```
Prompt: "Static camera. Nothing else moves except dust motes drifting slowly through light beam in place, linen curtain breathing gently. No camera pan, no zoom, no parallax, no tilt. Nothing else moves."
Settings: Motion intensity: 2/10, Duration: 5s (loop), Camera: Static
```

#### Cole / Quiet Roads
```
Prompt: "Static camera. Nothing else moves except light fog drifting slowly across road in place, single streetlight glowing steady, faint stars twinkling. No camera pan, no zoom, no parallax, no tilt. Nothing else moves."
Settings: Motion intensity: 3/10, Duration: 5s (loop), Camera: Static
```

#### Sera / Daydream Tape
```
Prompt: "Static camera. Nothing else moves except sheer curtain billowing softly in place, sunlight beam shifting slowly, dust motes drifting. No camera pan, no zoom, no parallax, no tilt. Nothing else moves."
Settings: Motion intensity: 3/10, Duration: 5s (loop), Camera: Static
```

**Loop seamless trick:** xuất 5s từ Runway → CapCut: lay loop 50 lần (4 phút visualizer) hoặc 360 lần (30 phút compilation) với crossfade 0.5s.

---

## 6. SEO Templates

### 6.1 Title Formulas

**Lofi / Acoustic Cover:**
```
[Song] — [Vocalist Alias] ([Variant] Cover)
```

Variants: `Lofi Acoustic`, `Acoustic · Slowed`, `Lofi · Stripped`

**Ví dụ thực tế:**
- `Marvin Gaye — Aiden (Lofi Acoustic Cover)`
- `Wonderful Tonight — Mara (Acoustic Cover)`
- `Another Love — Cole (Lofi Acoustic Cover · Slowed)`
- `Heathens — Sera (Acoustic Cover · Slowed)`
- `House of Memories — Aiden (Lofi Acoustic Cover)`

Long-form titles:
- `Aiden — Best Acoustic Covers Vol.1 | Late Night Pop Hits`
- `Lofi Acoustic Covers — 8 Hour Study Compilation | Mixed Vocalists`

**Rules:**
- ✅ Tên bài gốc luôn ở đầu (search intent của audience)
- ✅ Tên vocalist alias làm by-line (build IP nhất quán)
- ✅ Variant cover dùng `Lofi Acoustic` / `Acoustic` / `Slowed` cố định
- ❌ Không emoji trong title
- ❌ Không "AI" trong title (CTR giảm 20–40% theo benchmark Outlierkit)
- ❌ Không tên ca sĩ gốc trong title (audience search bằng tên bài là đủ, tránh implication ca sĩ gốc tham gia)

---

### 6.2 Description Template

```
[Opening hook — 1–2 dòng sensory mô tả không gian: "Late night, raindrops on the window, the lamp still on..."]

A lo-fi acoustic re-imagining of "[Song]", performed by [Vocalist Alias].
Slowed to [BPM] BPM, stripped to [instruments], recorded for late nights.

🎧 STREAM ON SPOTIFY:
[Smart link]

📀 ABOUT THIS COVER:
This is an officially licensed cover — the underlying composition is licensed 
from the rights holder, and the vocal performance is by [Vocalist Alias], 
who consented to the use of their voice in this AI-assisted production.

⏱️ TIMESTAMPS:
00:00 — [Song]
[N:NN] — Bridge
[N:NN] — Outro

🎤 SERIES: [Series Name] — Episode [N]
[Brief 1-line description of the series]

🎚️ PRODUCTION:
Vocal: [Vocalist Alias]
Composition: licensed from [partner]
Production: AI-assisted (Suno) with human post-production
Visual: AI-generated, animated (Runway)

✅ All rights cleared. Composition licensed, vocal consented.
✅ AI-assisted: this video contains synthetic music. (YouTube AI label applied.)

Subscribe for new acoustic covers every Mon · Wed · Fri →

#LofiCover #AcousticCover #[SongTitleNoSpaces] #SlowedAcoustic #LateNightLofi #LoFi #ChillMusic
```

---

### 6.3 Tag List Master

**Lofi / Acoustic Cover — 500 ký tự tags:**
```
lofi cover, acoustic cover, lofi acoustic, slowed cover, [song name], [song name] cover, [song name] acoustic, late night music, study music, chill music, sad acoustic, indie folk cover, soft cover, sleepy acoustic, lofi pop, lofi hits, mellow cover, bedroom pop cover, cozy music, late night vibes
```
(Replace `[song name]` với từng bài cụ thể trên mỗi upload.)

---

### 6.4 Spotify metadata

Khi upload qua DistroKid (xem Section 13 — Multi-stream revenue), set metadata như sau:

| Field | Value |
|---|---|
| Track name | `[Song] (Lofi Acoustic Cover)` |
| Primary artist | `[Vocalist Alias]` (ví dụ "Aiden") — KHÔNG ghi tên ca sĩ gốc |
| Featured | Để trống |
| Songwriter credit | Tên đầy đủ của songwriter gốc (theo composition rights letter) |
| Producer credit | `[Channel Brand]` |
| ISRC | DistroKid auto-gen |
| Cover art | 3000×3000 từ Midjourney upscale |
| Genre | Folk / Acoustic |
| Sub-genre | Indie Folk |
| **AI disclosure** | ✅ Tick "AI-generated content" + DDEX flag |

---

## 7. Thumbnail & Visual Guidelines

**Kích thước:** 1280×720px

**Composition:**
- 100% full-bleed visual từ Midjourney (cùng prompt với visualizer background → consistency)
- Text overlay nhỏ, bottom-left, không phủ trên chủ thể của ảnh
- Watermark series ở góc dưới phải

**Text style (nếu có):**
- Font: Cormorant Garamond Italic (italic gợi note tay, "song book" feel)
- Màu: Off-white `#FAF6EF` với drop shadow nhẹ `#000000` 25% opacity
- Kích thước: tên bài ~48pt, by-line vocalist ~24pt
- Vị trí: bottom-left, margin 60px từ rìa

**Mood:** Warm, intimate, like a late-night room where someone is playing music quietly for themselves.

**Không làm:**
- ❌ Chữ to bold sans-serif (làm thumbnail trông như EDM channel)
- ❌ Background gradient phẳng (mất warmth)
- ❌ Avatar mặt người (audience nhầm = vocalist)
- ❌ Stock photo
- ❌ Bright primary colors (đỏ, xanh điện, vàng chói)

**Template Canva setup:**
```
Nền: Midjourney upscale ảnh series (1280×720, có thể 4× lên 5120×2880 rồi crop)
Overlay: Linear gradient transparent → #1A1408 (warm dark) 30% opacity, bottom 35%
Text block: Bottom-left 60px margin, Cormorant Garamond Italic
Watermark: Bottom-right 40px margin, "[Series Name] · ep.[N]" 18pt
```

---

## 8. Production Pipeline — Step by Step

### Tổng thời gian mỗi single video: 80–110 phút

#### Bước 1 — Chọn bài & license vault check (5 phút)
```
1. Mở catalogue spreadsheet → pick bài tuần này theo content calendar
2. Verify tier:
   - Tier 1 (Tier C) → OK release immediately
   - Tier 2 (Tier B) → kiểm tra hợp đồng đối tác có sync letter CỤ THỂ cho bài này
   - Tier 3 (Tier A) → KHÔNG release single trong Tháng 1, dùng trong compilation thôi
3. License vault check: folder license_vault/[song_slug]/ phải có đủ 5 file:
   - 01_composition_rights.pdf (letter từ đối tác)
   - 02_vocal_contract.pdf (hợp đồng vocalist + điều khoản AI)
   - 03_vocal_sample.wav (file đã upload Suno + verification)
   - 04_suno_subscription.png (screenshot Pro/Premier active)
   - 05_ai_disclosure_draft.txt
4. Nếu thiếu bất kỳ file nào → BLOCK upload, không tiếp tục.
5. Copy lyric gốc từ official source.
```

#### Bước 2 — Tạo Suno Voice cho vocalist (chỉ 1 lần / vocalist, 30 phút)
```
1. Đảm bảo Suno Premier active.
2. Suno → Create → Voices → Create new voice
3. Upload file [vocalist]_VOCAL.wav (≥15s, ≤4 phút, càng acapella càng tốt)
4. Suno generate verification phrase
5. SCHEDULE buổi 30 phút với vocalist (chính chủ):
   - Vocalist đọc verification phrase, record on phone, gửi back
   - Bạn upload vào Suno verification step → Suno match identity
6. Voice verified → giữ private trong account, lưu voice_id vào catalogue spreadsheet
```

#### Bước 3 — Generate cover bằng Suno (15 phút)
```
1. Suno → Create → Custom mode
2. Style of Music: dán prompt 3-layer ghép (Section 5.1)
3. Lyrics: dán lyric gốc
4. Voice: chọn voice của vocalist tương ứng
5. Title: theo SEO formula Section 6.1
6. Exclude Styles: dán list cấm
7. Generate 4 variations
8. Listen sample 30s mỗi variation → chọn 1 best
9. Extend nếu cần (target 3:30–4:30)
10. Download cả MP3 và WAV
11. Tên file: lofi_[vocalist-short]_[song-slug]_v1.wav
    Ví dụ: lofi_aiden_marvin-gaye_v1.wav
```

#### Bước 4 — Post-production audio (Audacity, 20 phút)
```
1. Mở WAV trong Audacity
2. Vocal de-essing nếu chói: Effect → Equalization → -3dB at 6kHz
3. Light compression: Effect → Compressor → ratio 2:1, threshold -18dB
4. Tape saturation (free: Klanghelm IVGI plugin) → drive 15-25% trên master
5. LUFS normalization về -14 LUFS
6. Add fade-in 0.5s, fade-out 3s
7. Export WAV 48kHz/24-bit: lofi_[vocalist]_[song]_MASTER.wav
8. Export MP3 320kbps cho Spotify: lofi_[vocalist]_[song]_SPOTIFY.mp3
```

#### Bước 5 — Tạo visual Midjourney + Runway (20 phút)
```
1. Midjourney → dán prompt Section 5.2 theo series vocalist
2. Generate 4 variations → upscale tốt nhất
3. Save: lofi_[vocalist]_[song]_visual.png

4. Runway Gen-4:
   - Upload PNG
   - Prompt theo Section 5.3 (static-camera rule)
   - Motion: 2-3/10, Duration: 5s, Camera: Static
   - Generate
5. Download MP4: lofi_[vocalist]_[song]_loop.mp4
6. Verify: không sudden movement, loop seamless
```

#### Bước 6 — Ghép visualizer (CapCut, 15 phút)
```
1. New project 1920×1080, 24fps
2. Import: visual_loop.mp4 + MASTER.wav
3. Audio: drag MASTER.wav vào timeline
4. Visual loop: drag vào timeline → duplicate đến khớp audio length, crossfade 0.5s
5. Audio: fade-in 0.5s, fade-out 3s
6. Optional title card 3s đầu: "[Song] — [Vocalist]" Cormorant Italic
7. Export:
   - Resolution: 1920×1080, 24fps, Bitrate 16Mbps, MP4 H.264
8. Tên: lofi_[vocalist]_[song]_FINAL.mp4
```

#### Bước 7 — Lyric video version (CapCut, 25 phút)
```
1. Duplicate dự án FINAL.mp4
2. Add text track:
   - Cormorant Garamond Italic 56pt, off-white + soft shadow
   - Fade-in 0.3s mỗi line, hold đúng theo lyric timing
3. Sync lyric với audio:
   - CapCut "Auto captions" → manual fix timing
4. Export: lofi_[vocalist]_[song]_LYRIC.mp4
```

#### Bước 8 — Thumbnail + Shorts cut (15 phút)
```
1. Thumbnail (Canva):
   - 1280×720, background visual.png, overlay gradient bottom 35%
   - Text "[Song]\n— [Vocalist]" Cormorant Italic
   - Watermark "[Series] · ep.[N]"
   - Export PNG

2. Spotify cover 3000×3000 (Canva): crop từ visual upscale + tiny text bottom

3. Shorts cut 60s:
   - Highlight chorus + 1 verse line từ FINAL.mp4
   - Vertical 1080×1920 crop
   - Text overlay "[Song] full cover →"
   - Export MP4
```

#### Bước 9 — Metadata + AI disclosure (10 phút)
```
1. Chạy automation:
   python pipeline.py generate \
     --channel lofi \
     --vocalist aiden \
     --song marvin-gaye \
     --tier B
2. Pipeline output: title 3 variations, description filled, tags, Spotify metadata
3. License vault check:
   python pipeline.py vault check --channel lofi --song marvin-gaye
   → phải PASS đủ 5 file
```

#### Bước 10 — Upload + Schedule (10 phút)
```
1. YouTube Studio → Upload FINAL.mp4
   - Title, description, tags từ pipeline
   - Thumbnail, playlist (Series tương ứng)
   - ✅ Tick "Altered or synthetic content"
   - Schedule theo content calendar

2. (1 tuần sau) Upload LYRIC.mp4 với "[Song] (Lyrics)"

3. DistroKid → Upload SPOTIFY.mp3 (metadata Section 6.x, ✅ AI tick)

4. TikTok / Reels: Upload SHORT.mp4 với hashtag
```

---

### Batch Production (Khuyến nghị)

```
Thứ 2 (3h): Batch Suno generation — 3-4 bài tuần này
Thứ 3 (2h): Batch post-production audio cho tất cả
Thứ 4 (3h): Batch Midjourney + Runway visual cho tất cả
Thứ 5 (3h): Batch CapCut FINAL + LYRIC + SHORT
Thứ 6 (1h): Metadata generate + upload schedule cho cả tuần
```

**Tổng thời gian/tuần:** ~12 giờ cho 3 single + 3 lyric + 7 short

---

## 9. Tool Stack & Chi phí

### Lofi / Acoustic Cover Stack (~$95–$117/tháng)

| Tool | Mục đích | Chi phí/tháng |
|---|---|---|
| Suno Premier | AI cover generation với Voices feature | $30 |
| Midjourney Standard | Thumbnail + visualizer visual (200 fast hours) | $30 |
| Runway Standard | Image-to-video animation (motion loop) | $15 |
| Audacity / Adobe Audition | Audio post-production | Free / $22 |
| CapCut Pro | Video editing + auto-caption lyric | $10 |
| TubeBuddy Lite | Keyword research + SEO score | $9 |
| DistroKid Standard | Spotify/Apple/Tidal distribution | $1.92 ($23/năm) |
| Canva Pro | Thumbnail + Spotify cover art | $13 |
| **Total** | | **~$95–$117/tháng** |

### Optional Tools (nâng cấp sau tháng 3)

| Tool | Khi nào cần | Chi phí |
|---|---|---|
| Magnific AI | Khi cần thumbnail 4K-8K siêu nét cho hero releases | $39/tháng |
| ElevenLabs | Nếu kênh muốn host narration giới thiệu series | $22/tháng |
| Splice | Sample library cho post-production layering nâng cao | $13/tháng |
| Notion / Asana | License vault management + content calendar | Free / $10 |
| DistroKid Musician+ | Khi mỗi vocalist alias cần Spotify profile riêng | $36/năm |

---

## 10. Automation Script — Hướng dẫn sử dụng

File: `pipeline.py` (extend từ ASMR/Soundscapes pipeline với --channel lofi)

### Cài đặt

```bash
pip install rich click colorama
python pipeline.py --help
```

### Các lệnh chính

#### Tạo metadata cho 1 video
```bash
python pipeline.py generate \
  --channel lofi \
  --vocalist aiden \
  --song marvin-gaye \
  --tier B \
  --date 20260601
```

Output:
```
📺 TITLE OPTIONS:
  1. Marvin Gaye — Aiden (Lofi Acoustic Cover)
  2. Marvin Gaye — Aiden (Acoustic Cover · Slowed)
  3. Marvin Gaye — Aiden (Lofi Cover · Bedside Lights ep.04)

📝 DESCRIPTION: [filled template saved to output/lofi_aiden_marvin-gaye_desc.txt]
🏷️  TAGS: [saved to output/lofi_aiden_marvin-gaye_tags.txt]
📁 FILENAME: lofi_aiden_marvin-gaye_FINAL.mp4
🎵 SUNO PROMPT: [3-layer ghép saved to output/lofi_aiden_marvin-gaye_suno.txt]
🖼️  MIDJOURNEY PROMPT: [aiden series saved]
🎬 RUNWAY PROMPT: [aiden series saved]
```

#### License vault check
```bash
python pipeline.py vault check --channel lofi --song marvin-gaye
# Returns PASS/FAIL với detail file nào còn thiếu
```

#### Quản lý upload queue
```bash
python pipeline.py queue add \
  --channel lofi \
  --file lofi_aiden_marvin-gaye_FINAL.mp4 \
  --date 2026-06-01 \
  --time 14:00

python pipeline.py queue list
python pipeline.py queue done --id 3
```

#### Đặt tên file hàng loạt
```bash
python pipeline.py rename --folder ./raw_exports --channel lofi
```

#### Xem content calendar
```bash
python pipeline.py calendar --channel lofi --month 2026-06
```

---

## 11. Content Calendar — 3 tháng đầu

### Tháng 1 — Launch (chỉ Tier 1, build channel signal)

**Tuần 1:** (Setup tuần, 1 video launch)
| Ngày | Video | Theme |
|---|---|---|
| T2 | Setup | Tạo Suno Voices cho 4 vocalist |
| T4 | Upload 1 | Cole — Bad Child (Tier 1, single 4 phút) |
| T6 | Upload 2 | Short cut từ Bad Child |

**Tuần 2:** Mara — Talking Body (single) / Cole — Bad Child (lyric) / Aiden — Long Drives (single)

**Tuần 3:** Sera — Doll House (single) / Mara — Talking Body (lyric) / Cole — Rx (single)

**Tuần 4 — Review:**
- Dừng 1 ngày để review analytics
- Video nào có AVD cao nhất? → Double down tháng 2
- Theme nào có CTR cao nhất? → Làm thêm variation
- Điều chỉnh upload schedule nếu cần

**Mục tiêu Tháng 1:**
- ✅ 8 single + 4 lyric video (12 video chính)
- ✅ Xác định được top 3 vocalist + top 3 themes
- ✅ Watch hours target: 200h

---

### Tháng 2 — Scale + Optimize + Spotify push

**Lofi — Upload 3 video/tuần:**
- 1 single mới (mix Tier 1 + Tier 2 đã verify sync)
- 1 lyric video (1 tuần sau single)
- 1 long-form (compilation HOẶC ambient loop, luân phiên)

**Long-form kế hoạch:**
- Tuần 1: `Aiden — Best Acoustic Covers Vol.1 | Late Night Pop Hits` (compilation 30 phút)
- Tuần 3: `Lofi Acoustic Covers — 1 Hour Late Night | Mixed Vocalists`

**Spotify push:**
- Tuần 2: Upload 5 single tốt nhất Tháng 1 qua DistroKid
- Submit editorial pitch: "Acoustic Covers" / "Lofi Beats" / "Chill Hits"
- Build Spotify artist profile riêng cho mỗi vocalist (Aiden, Mara, Cole, Sera)

**Tháng 2 targets:**
- ✅ 12 video chính (running total: 24)
- ✅ Watch hours: 800h (cumulative)
- ✅ Subscribers: 200–500
- ✅ Bắt đầu Shorts: 1 Short/ngày từ content đã có

---

### Tháng 3 — Monetize (ambient loop push)

**Lofi: Upload 4 video/tuần** — long-form ambient loop là chìa khóa watch hours.

**Theme focus Tháng 3:**
```
Week 1: Lofi Acoustic Covers — 8 Hour Study Compilation | Aiden Series
Week 2: Late Night Lofi Covers — 4 Hour Bedside Mix | Cole + Mara
Week 3: Spring Lofi Acoustic Covers — 8 Hour Soft Pop | Mixed
Week 4: Rainy Acoustic Covers — 6 Hour Window Sessions | Mara
```

**Tháng 3 targets:**
- ✅ 4K+ watch hours, 1K+ subscribers → Apply YPP
- ✅ Spotify monthly listeners: 500+ per alias
- ✅ Đăng ký DistroKid bổ sung nếu chưa, upload bổ sung Tier 2 đã verify

---

### Shorts Strategy

**Format:** Cắt 58–60 giây từ video chính

**Lofi Shorts:**
- Tiêu đề: `[Song] — [Vocalist] · Lofi Cover (60s preview)`
- Call to action: `Full version on the channel →`

**Upload Shorts:** Hàng ngày, 8:00 PM EST (peak time US audience)

---

## 12. KPI & Success Metrics

### Metrics cần track mỗi tuần (30 phút review)

#### Performance Metrics
| Metric | Target (Tháng 3) |
|---|---|
| Total watch hours | 4,000h |
| Subscribers | 1,000 |
| Average View Duration | > 60% (≥ 2:30 cho single 4:00) hoặc > 30 phút cho loop 4–8h |
| CTR (Click-through rate) | > 4% |
| Impressions/tuần | Growing 10%+ |

#### Content Metrics
| Metric | Xem ở đâu | Đọc như thế nào |
|---|---|---|
| Average View Duration | YouTube Analytics > Content | Single < 40% AVD → re-mix audio hoặc re-cut hook đầu yếu |
| CTR | YouTube Analytics > Reach | < 2%: thay thumbnail. < 1%: thay title |
| Revenue per view | Monetize sau → RPM | Lofi target $4–8, nếu thấp → check geo audience |
| Traffic source | Analytics > Reach | Search > 40% là healthy (cover search intent) |
| Returning viewers % | Analytics > Audience | > 25% = audience đang bind, vocalist identity work |

### Dấu hiệu cần can thiệp ngay

- ❗ Content ID claim trên 1 bài → check license vault NGAY, dispute với composition letter
- ❗ Strike YouTube → take down related videos, audit toàn bộ catalogue, escalate đối tác
- ❗ CTR < 1% sau 500 impressions → thay thumbnail ngay
- ❗ AVD < 30% trên single visualizer → Suno prompt có vấn đề (re-generate với prompt mới)

---

## 13. Monetization Checklist

### YouTube Partner Program — Apply khi đủ điều kiện

- [ ] 1,000 subscribers
- [ ] 4,000 public watch hours (trong 12 tháng qua)
- [ ] Không có community guideline strikes
- [ ] 2-step verification bật
- [ ] Đã tick "Altered or synthetic content" trên mọi video AI

### YouTube Policies — Phải pass tất cả

- [ ] **Inauthentic content**: Mọi video có animated visual (không phải static image)
- [ ] **Reused content**: Không có 2 video nào share > 30% cùng audio
- [ ] **AI disclosure**: Tick "Altered/synthetic content" 100% video
- [ ] **Advertiser-friendly**: Không content nhạy cảm, không NSFW
- [ ] **Content ID**: Nhạc Suno không bị claim sai (check claim checker)

### Cover Song Compliance Gates — KHÁC ASMR/Soundscapes

Vì đây là cover song có publisher rights, mỗi video phải qua compliance gate trước upload:

- [ ] **Composition rights**: hợp đồng đối tác có ghi rõ sync + mechanical + scope global + thời hạn cho từng bài đã upload
- [ ] **Vocal contract** với 6 điều khoản AI: consent training, derivative AI vocal renditions, waiver of publicity, không bắt chước ca sĩ cụ thể còn sống, attribution, revocation rights
- [ ] **Suno subscription** Pro/Premier active tại thời điểm generate (screenshot có timestamp)
- [ ] **Suno Voice** đã verify chính chủ (giữ verification recording)
- [ ] **Tier check** đúng (Tier 1/Tier 2 verified) — KHÔNG Tier 3 (Tier A hits) trong giai đoạn pre-monetize
- [ ] **License vault** đủ 5 file cho bài đó (xem Section 8 Bước 1)
- [ ] **Description** ghi rõ vocal + composition + AI-assisted
- [ ] **No banned imagery** trên thumbnail/visual (không người, không brand, không tên ca sĩ gốc)

Không tick đủ → KHÔNG upload. Set up Notion/Asana với template này làm gate.

#### Content ID claim handling — bảng quyết định

Nếu một bài bị Content ID claim sau upload:

| Tình huống | Xử lý |
|---|---|
| Claim "monetize on behalf of publisher" (publisher lấy ad rev, video vẫn live) | Chấp nhận. Đây là cover license route bình thường khi sync chưa chính thức cho bài đó. |
| Claim "block in [country]" | Dispute với composition rights letter làm bằng chứng. Đính kèm bản license đã có. |
| Strike (full takedown) | Liên hệ đối tác composition NGAY → requesting publisher remove claim. Take video down trong khi xử lý. |
| Multiple strikes 3 tháng | Hold upload Tier A tracks. Review hợp đồng đối tác — có thể scope license chưa đủ. |

#### Quarterly compliance review

Mỗi 3 tháng:
- [ ] Download lại Suno ToS, lưu PDF với timestamp
- [ ] Kiểm tra YouTube AI policy update — search "youtube ai music policy 2026 update"
- [ ] Kiểm tra Spotify policy
- [ ] Audit license vault: check expiry dates trên hợp đồng cho từng bài
- [ ] Theo dõi Sony v Suno tracker (chartlex.com, mckoolsmith.com AI litigation updates)
- [ ] Audit Content ID claim log: tỷ lệ claim/upload — nếu tăng đột biến, đánh giá lại catalogue selection

### Sau khi monetize — Optimize RPM

1. **No mid-roll ads trên ambient loop** — audience hatewatch nếu bị ngắt giữa session study/sleep
2. **Q4 push** — tháng 11–12 CPM cao 2–3x; ưu tiên upload nhiều + push compilation seasonal (Christmas, study finals)
3. **Geo: US/UK/AU/CA** chiếm > 70% audience là tốt (CPM cao nhất); SEO title tiếng Anh thuần
4. **Tăng video length** — compilation 1 giờ > single 4 phút về watch time per upload; ambient loop 8h ROI cao nhất

### Dòng doanh thu thứ 2 — Spotify streaming + Sync license

**Spotify streaming:**
- Upload qua DistroKid sau khi single ra YouTube 1 tuần
- Build artist profile RIÊNG cho mỗi vocalist alias (Aiden, Mara, Cole, Sera)
- Submit editorial pitch trong DistroKid: "Acoustic Covers", "Lofi Beats", "Chill Hits"
- Revenue: ~$0.003–0.005/stream → cần 100K streams/tháng để đáng kể, nhưng passive 100%
- Sau 6 tháng có catalogue ≥30 bài, royalty có thể bằng/vượt YouTube ad rev nếu có 1–2 track lên editorial playlist

**Sync license (chiến lược trung hạn):**
- Sau 6 tháng có 30+ catalogue, mở storefront sync license (Songtradr, Musicbed, hoặc tự làm site)
- Pitch tới indie filmmaker, brand TVC, podcast — phân khúc thư viện Epidemic/Artlist không cạnh tranh hết
- Revenue: $200–$2000/sync — margin cao, không cạnh tranh với kênh ASMR/Soundscapes

**AI vocalist as IP (long-term, sau 12 tháng):**
- Nếu một vocalist (ví dụ Aiden) đạt 50K+ Spotify followers + 100K+ YouTube subs → tài sản IP độc lập
- Spin-off kênh riêng, brand deal, sync premium, release "original" track từ catalogue đối tác

---

*Dùng kết hợp với:*
- *`Channel_Launch_Plan_EDM_Cover.md` (kênh test #2)*
- *`Brief_canh_tranh_AI_Cover_Suno_2026.docx` (legal foundation + policy landscape 2026)*
- *`pipeline.py` (automation script — extend từ ASMR/Soundscapes pipeline)*

*Cập nhật lần cuối: 2026-05-10*
