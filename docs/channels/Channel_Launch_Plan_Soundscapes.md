# Channel Launch Plan — Soundscapes & Ambience

> Kế hoạch chi tiết để triển khai kênh YouTube AI music Soundscapes & Ambience.
> Dùng chung pipeline và automation script với kênh ASMR.
> Cập nhật: 2026-04-29

---

## Mục lục

1. [Tổng quan kênh](#1-tổng-quan-kênh)
2. [Brand Identity](#2-brand-identity)
3. [Content Strategy — Theme Library](#3-content-strategy--theme-library)
4. [Đặc điểm âm thanh Soundscapes channel](#4-đặc-điểm-âm-thanh-soundscapes-channel)
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

| Tiêu chí | Kênh Soundscapes & Ambience |
|---|---|
| **Focus** | Nature environments, study, work, meditation |
| **Audience** | Người làm việc/học tập cần nền âm thanh |
| **Video length** | 2–4 giờ/video |
| **Upload frequency** | 4–5 video/tuần |
| **RPM ước tính** | $7–$9 |
| **Advertiser category** | Productivity, education, software |
| **Music style** | Ambient + nature sfx, subtle melody ok |
| **Visual style** | Beautiful nature, slow parallax |
| **Time to monetize** | 3–5 tháng |
| **Launch order** | **Tháng 1** (song song với ASMR) |

### Lý do tách 2 kênh thay vì gộp

YouTube algorithm hoạt động tốt nhất khi 1 kênh = 1 audience intent. Người search "rain sounds for sleep 8 hours" không cùng intent với người search "forest ambience for studying". Tách kênh giúp:
- Mỗi kênh được suggest đúng audience mục tiêu
- Thumbnail và title formula có thể tối ưu độc lập
- Nếu 1 kênh bị policy issue, kênh kia không bị ảnh hưởng
- Dễ track performance và double-down theo niche riêng

---

## 2. Brand Identity

**Tên kênh:** *(gợi ý, chọn 1)*
- `Ambient Earth`
- `The Soundscape Studio`
- `Natural Drift`
- `World Ambience`

**Tagline:** *"Step Into Another World. Work. Study. Breathe."*

**Brand colors:**
- Primary: Forest green `#2D4A3E`
- Secondary: Sky blue `#7FB3C8`
- Accent: Golden hour `#E8B84B`
- Background: Warm off-white `#F5F0E8` (cho thumbnail style sáng)

**Brand voice:**
- Inspiring, experiential — như travel magazine
- Mô tả địa điểm như đang ở đó: "You're sitting by a mountain stream..."
- Description có sense of place mạnh

---

## 3. Content Strategy — Theme Library

#### Nhóm A — Nature Environments (60% content)

| Theme | Title Formula | Length | Search Intent |
|---|---|---|---|
| Forest stream | Forest Stream Sounds — Study & Focus Ambience {N}h | 3–4h | Study/work |
| Mountain waterfall | Mountain Waterfall ASMR — Nature Ambience for Focus | 3h | Meditation |
| Bamboo forest | Bamboo Forest Wind — Japanese Ambience for Study | 2–3h | Study/aesthetic |
| Rainforest | Amazon Rainforest Sounds — Tropical Ambience | 3h | Relaxation |
| Beach sunset | Beach Sunset Ambience — Waves & Seagulls for Work | 3h | Work/chill |
| Snowy forest | Snowy Forest Ambience — Blizzard & Wind Sounds | 3h | Winter aesthetic |
| Desert wind | Sahara Desert Wind & Sand — Meditation Ambience | 2h | Meditation |

#### Nhóm B — Urban/Café Environments (25% content)

| Theme | Title Formula | Length |
|---|---|---|
| Tokyo back streets | Tokyo Night Ambience — City Rain & Distant Trains | 3h |
| London pub | Cozy British Pub Ambience — Fire & Distant Chatter | 3h |
| New York diner | Classic American Diner Ambience — Morning Sounds | 2h |
| Parisian café (outdoor) | Paris Street Café — Accordion & City Sounds | 3h |
| Seoul study café | Seoul Study Café Ambience — Rain & Soft Music | 3h |

#### Nhóm C — Fantasy/Unique Environments (15% content)

| Theme | Title Formula | Length |
|---|---|---|
| Wizard's library | Ancient Library Ambience — Crackling Fire & Pages | 3h |
| Underwater | Underwater Ambience — Deep Ocean Sounds for Focus | 2h |
| Space station | Space Station Ambience — Hum & Cosmos Sounds | 3h |
| Hobbit hole | Cozy Hobbit Hole Ambience — Fireplace & Rain | 3h |

---

## 4. Đặc điểm âm thanh Soundscapes channel

**Nguyên tắc âm thanh:**
- Melody subtle được phép (khác với ASMR channel) — nhưng không dominate
- Stereo width rộng hơn: tạo cảm giác không gian (spatial audio)
- Mid-range clear: người nghe trong khi làm việc — không bị muffled
- Dynamic range vừa phải: có thể có peak nhẹ khi gió thổi, chim kêu

**Volume mix:**
```
Environment base (stream/wind/city): 0dB reference
Feature sounds (chim, xe, người): -6 đến -10dB (foreground)
Atmosphere (room reverb, distance): -15dB (background)
Music underlayer: -10 đến -14dB (có thể nghe được)
```

---

## 5. Prompt Templates

### 5.1 Suno AI — Soundscapes Channel

#### Forest Stream
```
[Instrumental] babbling mountain stream over smooth rocks, light breeze through pine trees, occasional bird call, subtle ambient music underneath, [No Vocals], peaceful and focused, natural stereo space, fresh morning feel, [Ambient Landscape]
```

#### Tokyo Night
```
[Instrumental] Tokyo rainy street ambience, distant train passing, muffled izakaya sounds, soft shamisen-inspired melody underneath, light jazz inflection, [No Vocals], urban nocturnal, neon-lit atmosphere, cinematic depth, [City Soundscape]
```

#### Fantasy Library
```
[Instrumental] ancient stone library, crackling fireplace, pages turning, distant owl, soft magical ambient undertones, no dominant melody, [No Vocals], mysterious and focused, warm candlelight atmosphere, [Fantasy Ambient]
```

#### Café Study (Seoul/Paris)
```
[Instrumental] indie café morning, espresso machine in distance, soft rain on window, light lo-fi piano bed, gentle cup sounds, [No Vocals], studious and calm, intimate interior acoustics, warm and focused, [Café Ambient]
```

---

### 5.2 Midjourney — Soundscapes Channel Visuals

#### Forest Stream
```
sunlight filtering through misty ancient forest, moss-covered rocks, clear stream in foreground, golden hour, lush greens, ethereal light rays, 4k nature photography, no people --ar 16:9 --v 6.1
```

#### Tokyo Night
```
rainy Tokyo back street at night, red lanterns reflected in wet pavement, empty alley, neon glow, cinematic film photography, Blade Runner atmosphere, no people --ar 16:9 --style raw --v 6.1
```

#### Fantasy Library
```
ancient medieval library interior, towering bookshelves reaching cathedral ceiling, warm candlelight, spiral staircase, floating dust particles, magical atmosphere, digital painting, ultra-detailed --ar 16:9 --v 6.1
```

---

### 5.3 Runway Gen-4 — Animation Prompts

**Soundscapes channel (gentle parallax):**
```
Prompt: "Gentle slow-motion parallax, foreground leaves sway very slightly, stream ripples softly, natural light shifts. Peaceful."
Settings: Motion intensity: 3-4/10, Duration: 5s (loop), Camera: Very slow zoom-out
```

---

## 6. SEO Templates

### 6.1 Title Formulas

**Soundscapes Channel:**
```
[Location/Environment] [Type] — [Use Case] | [Duration] Ambience
```

**Ví dụ thực tế:**
- `Ancient Forest Stream Sounds — Focus & Study | 3 Hour Ambience`
- `Rainy Tokyo Night — Work From Anywhere | 3 Hour City Ambience`
- `Cozy Library Fireplace — Study & Concentration | 3 Hour Ambience`
- `Bamboo Forest Wind — Meditation & Relaxation | 2 Hour Soundscape`
- `Paris Street Café Morning — Work & Focus | 3 Hour Ambience`

**Rules:**
- ✅ Luôn có số giờ cụ thể (8 Hours, 3 Hours, không phải "Long")
- ✅ Include use case (Sleep / Study / Focus / Relax / Meditation)
- ✅ Capitalize mỗi từ quan trọng (Title Case)
- ❌ Không dùng emoji trong title
- ❌ Không dùng ALL CAPS
- ❌ Không đánh số thứ tự (Vol.1, #12)

---

### 6.2 Description Template

```
[Opening line — bạn đang ở đâu, cảm giác gì, 2–3 câu storytelling]

[Environment description: mô tả chi tiết âm thanh, cảnh vật, thời gian trong ngày]

🌿 WHAT YOU'LL HEAR:
• [Primary environment sound]
• [Secondary sound]
• [Subtle music/ambience layer]

⏱️ CHAPTERS:
00:00 — Arrive
[30 min] — Settle in
[1h] — Deep immersion
[2h] — Continued ambience

📍 BEST USED FOR:
Deep focus · Remote work background · Study sessions · Reading · Meditation · Light yoga

🎧 Sounds best with headphones or speakers. Volume: medium-low.

Created with AI sound design tools, curated for immersive environmental experience by [Channel Name].

#AmbientSounds #StudyMusic #FocusMusic #NatureSounds #WorkFromHome #Soundscape #AmbientMusic
```

---

### 6.3 Tag List Master

**Soundscapes Channel — 500 ký tự tags:**
```
ambient sounds, nature sounds, study music, focus music, work from home music, forest sounds, rain ambience, café ambience, lofi ambience, concentration music, background music for work, relaxing ambience, meditation music, soundscape, nature ambience, study with me, deep focus, productivity music, ambient music, binaural sounds
```

---

## 7. Thumbnail & Visual Guidelines

**Composition:**
- Full-bleed nature/environment shot (Midjourney)
- Có thể sáng hơn ASMR (golden hour, green forest)
- Text: 3–5 từ, đặt ở vùng tối của ảnh

**Text style:**
- Font: Montserrat SemiBold hoặc Raleway
- Màu: White với drop shadow nhẹ
- Có thể thêm small location tag (ví dụ: "TOKYO NIGHT")

**Mood theo nhóm content:**
- Nature: Lush, fresh, breathing
- Urban: Moody, cinematic, nighttime
- Fantasy: Magical, warm, detailed

---

## 8. Production Pipeline — Step by Step

### Tổng thời gian mỗi video: 75–100 phút

Giống ASMR pipeline nhưng khác ở các điểm:

#### Bước 1 — Chọn theme & research (5 phút)
```
Vào TubeBuddy → Keyword Explorer → search theme dự kiến
Kiểm tra: Search volume, Competition score
✅ Chọn theme có Volume: Good/Excellent + Competition: Poor/Fair
Ghi lại exact keyword phrase → đây là title chính
```

#### Bước 2 — Tạo nhạc nền (Suno AI, 10 phút)
Dùng template Section 5.1 — có thêm melody layer, stereo width rộng hơn

#### Bước 3 — Layer âm thanh thật (Freesound + Audacity, 20 phút)
```
Track 1 (Environment base): Freesound environment recording → 0dB
Track 2 (Music): Suno AI output → -10 đến -12dB
Track 3 (Feature sfx): Tiếng chim/gió/người → -6dB (occasional)
Track 4 (Room tone): -20dB
```

#### Bước 4 — Tạo visual (Midjourney + Runway, 20 phút)
Motion intensity 3–4/10 thay vì 1–2/10. Có thể thêm parallax zoom-out rất chậm.

#### Bước 5 — Ghép video (CapCut, 15 phút)
```
1. New project → 1920x1080
2. Import: visual.mp4 + MASTER.wav
3. Loop visual đến khớp với audio (2–4h)
4. Thêm fade in 5 giây đầu, fade out 10 giây cuối
5. Export settings:
   - Resolution: 1920x1080
   - Frame rate: 24fps
   - Quality: High (hoặc 16Mbps)
   - Format: MP4 H.264
Video ngắn hơn (2–4h) → file nhỏ hơn (~2–4GB)
```

#### Bước 6 — Chapters (đặc biệt cho Soundscapes)
Soundscapes videos thêm chapters theo thời gian trong ngày:
```
00:00 — Dawn Arrival
30:00 — Morning Settle
1:00:00 — Deep Immersion
2:00:00 — Afternoon Flow
[etc.]
```

#### Bước 7 — Chuẩn bị upload metadata (10 phút)
```
Chạy automation script:
  python pipeline.py generate --channel soundscapes --theme "forest stream" --length 3h --date 20260501

Script sẽ output:
  ✅ Title (3 variations)
  ✅ Description (filled template)
  ✅ Tags (comma-separated)
  ✅ Thumbnail filename suggestion
  ✅ Playlist assignment

Copy vào YouTube Studio
```

#### Bước 8 — Upload & Schedule (5 phút)
```
YouTube Studio → Upload video
- Title: [copy từ script output]
- Description: [copy từ script output]
- Tags: [copy từ script output]
- Thumbnail: Upload ảnh đã tạo ở Bước 4
- Playlist: Thêm vào đúng playlist
- Tick "Altered or synthetic content" ✅
- Schedule: đặt theo content calendar (không upload ngay)
- Visibility: Scheduled → đúng ngày giờ
```

---

### Batch Production (Khuyến nghị)

Làm 4–5 video cùng lúc mỗi tuần — giảm thời gian setup:

```
Thứ 2 (2h): Batch Suno generation — tạo audio cho cả tuần
Thứ 3 (2h): Batch Midjourney + Runway — visual cho cả tuần
Thứ 4 (3h): Batch Audacity mixing — mix tất cả audio
Thứ 5 (2h): Batch CapCut export + metadata generation
Thứ 6 (1h): Upload và schedule cho tuần tới
```

**Tổng thời gian/tuần:** ~10 giờ cho 4–5 video (cả 2 kênh)

---

## 9. Tool Stack & Chi phí

### Soundscapes Channel Stack (~$20/tháng thêm so với ASMR)

Dùng lại hầu hết tools từ ASMR stack. Chỉ cần:
- Nâng Runway lên Standard ($35/tháng) nếu cần nhiều animation credits hơn → +$20
- Hoặc dùng Kling AI ($10/tháng) thay thế

**Tổng chi phí 2 kênh cùng lúc:** ~$68–$78/tháng

### Optional Tools (nâng cấp sau tháng 3)

| Tool | Khi nào cần | Chi phí |
|---|---|---|
| Adobe Audition | Khi muốn mix chuyên nghiệp hơn | $22/tháng |
| AIVA Pro | Nhạc cho Soundscapes với full copyright | $33/tháng |
| VidIQ Boost | Analytics nâng cao + SEO score | $25/tháng |
| DistroKid | Upload nhạc lên Spotify | $23/năm |
| ElevenLabs | Voice narration (nếu add intro narrated) | $22/tháng |

---

## 10. Automation Script — Hướng dẫn sử dụng

File: `pipeline.py` (xem file riêng trong cùng thư mục)

### Cài đặt

```bash
pip install rich click colorama
python pipeline.py --help
```

### Các lệnh chính

#### Tạo metadata cho 1 video
```bash
python pipeline.py generate \
  --channel soundscapes \
  --theme "forest stream morning" \
  --length 3h \
  --date 20260501
```

#### Quản lý upload queue
```bash
# Thêm video vào queue
python pipeline.py queue add \
  --channel soundscapes \
  --file soundscapes_forest-stream_20260501_FINAL.mp4 \
  --date 2026-05-01 \
  --time 14:00

# Xem queue
python pipeline.py queue list

# Mark as uploaded
python pipeline.py queue done --id 3
```

#### Đặt tên file hàng loạt
```bash
# Rename tất cả file trong thư mục theo convention
python pipeline.py rename --folder ./raw_exports --channel soundscapes
```

#### Xem content calendar
```bash
python pipeline.py calendar --channel soundscapes --month 2026-05
```

---

## 11. Content Calendar — 3 tháng đầu

### Tháng 1 — Launch (Setup + Test)

**Tuần 1:**
| Ngày | Video | Theme |
|---|---|---|
| T3 | Upload 1 | Forest Stream Focus — 3h |
| T5 | Upload 2 | Bamboo Forest Wind — 2h |
| T7 | Upload 3 | Mountain Waterfall — 3h |

**Tuần 2:** Ancient Library 3h / Rainy Tokyo Night 3h / Beach Sunset 3h

**Tuần 3:** Paris Street Café 3h / Amazon Rainforest 3h / London Pub 2h

**Tuần 4 — Review:**
- Dừng 1 ngày để review analytics
- Video nào có AVD (Average View Duration) cao nhất? → Double down tháng 2
- Theme nào có CTR cao nhất? → Làm thêm variation
- Điều chỉnh upload schedule nếu cần

**Mục tiêu Tháng 1:**
- ✅ 12 video Soundscapes
- ✅ Xác định được top 3 performing themes
- ✅ Watch hours target: 300h

---

### Tháng 2 — Scale + Optimize

**Focus:** Double down themes hoạt động tốt từ Tháng 1

**Soundscapes — Upload 5 video/tuần:**
- 2 video variation top theme
- 2 video themes khác trong top 3
- 1 video fantasy/unique (test audience)

**Tháng 2 targets:**
- ✅ 20 video (running total: 32)
- ✅ Watch hours: 800h (cumulative)
- ✅ Subscribers: 50–200
- ✅ Bắt đầu Shorts: 1 Short/ngày từ content đã có (clip 60 giây từ video dài)

---

### Tháng 3 — Monetize

**Focus:** Đạt threshold YPP (1K subs + 4K watch hours)

**Soundscapes: Upload 4–5 video/tuần**

**Soundscapes theme focus Tháng 3:**
```
Week 1: Spring Forest Awakening — seasonal
Week 2: Cherry Blossom Garden Japan — seasonal (April aesthetic)
Week 3: Seoul Spring Café — geographic + seasonal combo
Week 4: Fantasy Garden — fantasy series launch
```

**Tháng 3 targets:**
- ✅ Soundscapes: 2K+ watch hours, 600+ subscribers
- ✅ Đăng ký DistroKid → Upload top 5 tracks lên Spotify
- ✅ Bắt đầu Pinterest boards cho visual content

---

### Shorts Strategy

**Format:** Cắt 58–60 giây từ video chính

**Soundscapes Shorts:**
- Tiêu đề: "This [Location] Ambience = Instant Focus 🎧"
- Call to action: "Full 3-hour version on the channel →"

**Upload Shorts:** Hàng ngày, 9:00 AM giờ địa phương target audience (EST nếu target US market)

---

## 12. KPI & Success Metrics

### Metrics cần track mỗi tuần (30 phút review)

#### Performance Metrics
| Metric | Soundscapes Target (Tháng 3) |
|---|---|
| Total watch hours | 2,000h |
| Subscribers | 600 |
| Average View Duration | > 45 phút (cho video 3h) |
| CTR (Click-through rate) | > 4% |
| Impressions/tuần | Growing 10%+ |

#### Content Metrics
| Metric | Xem ở đâu | Đọc như thế nào |
|---|---|---|
| Average View Duration | YouTube Analytics > Content | Video nào dưới 20% AVD → xem xét xóa hoặc optimize |
| CTR | YouTube Analytics > Reach | Dưới 2%: thay thumbnail. Dưới 1%: thay title |
| Revenue per view | Monetize sau → RPM | Target $7–9, nếu thấp → adjust content category |
| Traffic source | Analytics > Reach | Search % phải > 50% (tốt) |
| Returning viewers % | Analytics > Audience | > 20% = channel đang build loyal audience |

### Dấu hiệu cần can thiệp ngay

- ❗ CTR < 1% sau 500 impressions → Thay thumbnail ngay
- ❗ AVD < 15 phút cho video 3h → Audio có vấn đề (check layer, check sudden sounds)
- ❗ Watch hours stagnant 2 tuần → Thử theme mới, tăng upload frequency
- ❗ Subscribe rate giảm → Check xem có video nào mismatch theme không

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
- [ ] **Advertiser-friendly**: Không có content nhạy cảm, không NSFW
- [ ] **Content ID**: Nhạc Suno không bị claim (check qua YouTube's claim checker)

### Sau khi monetize — Optimize RPM

1. **Tăng video length** — Video 10h > 8h về watch time, RPM tương đương nhưng revenue/video cao hơn
2. **Tháng cuối năm (Q4)** — CPM tăng 2–3x. Upload nhiều hơn tháng 10–12
3. **Geo targeting** — Audience US/UK/Australia có CPM cao nhất. SEO title tiếng Anh, không mix ngôn ngữ
4. **No mid-roll ads** — ASMR/sleep content: tắt mid-roll ads (người xem hatewatch nếu bị ngắt giữa giấc ngủ). Chỉ dùng pre-roll

### Dòng doanh thu thứ 2 — Spotify

Sau tháng 3, upload top tracks lên Spotify qua DistroKid:
- Chọn 10 track hay nhất từ mỗi kênh
- Album name: "[Channel Name] — Soundscapes Collection Vol. 1"
- Category: Ambient / New Age / Nature Sounds
- Revenue: ~$0.003–0.005/stream → cần 100K streams/tháng để đáng kể nhưng passive 100%

---

*Dùng kết hợp với `pipeline.py` và `Channel_Launch_Plan_ASMR.md`.*
*Cập nhật lần cuối: 2026-04-29*
