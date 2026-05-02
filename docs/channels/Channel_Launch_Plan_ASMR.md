# Channel Launch Plan — ASMR Sleep & Relax

> Kế hoạch chi tiết để triển khai kênh YouTube AI music ASMR Sleep & Relax.
> Dùng chung pipeline và automation script với kênh Soundscapes.
> Cập nhật: 2026-04-29

---

## Mục lục

1. [Tổng quan kênh](#1-tổng-quan-kênh)
2. [Brand Identity](#2-brand-identity)
3. [Content Strategy — Theme Library](#3-content-strategy--theme-library)
4. [Đặc điểm âm thanh ASMR channel](#4-đặc-điểm-âm-thanh-asmr-channel)
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

| Tiêu chí | Kênh ASMR Sleep & Relax |
|---|---|
| **Focus** | Sleep, deep relaxation, stress relief |
| **Audience** | Người mất ngủ, lo âu, cần thư giãn sâu |
| **Video length** | 8–10 giờ/video |
| **Upload frequency** | 3–4 video/tuần |
| **RPM ước tính** | $10–$11 |
| **Advertiser category** | Wellness, pharma, sleep aids |
| **Music style** | Pure texture, no melody, binaural-leaning |
| **Visual style** | Dark, moody, minimal motion |
| **Time to monetize** | 3–4 tháng |
| **Launch order** | **Tháng 1** |

### Lý do tách 2 kênh thay vì gộp

YouTube algorithm hoạt động tốt nhất khi 1 kênh = 1 audience intent. Người search "rain sounds for sleep 8 hours" không cùng intent với người search "forest ambience for studying". Tách kênh giúp:
- Mỗi kênh được suggest đúng audience mục tiêu
- Thumbnail và title formula có thể tối ưu độc lập
- Nếu 1 kênh bị policy issue, kênh kia không bị ảnh hưởng
- Dễ track performance và double-down theo niche riêng

---

## 2. Brand Identity

**Tên kênh:** *(gợi ý, chọn 1)*
- `Deep Sleep Drift`
- `Velvet Night ASMR`
- `The Sleep Sanctuary`
- `Midnight Calm`

**Tagline:** *"8 Hours of Peace. Sleep Deeper Tonight."*

**Brand colors:**
- Primary: Deep navy `#0D1B2A`
- Secondary: Soft lavender `#9B8EC4`
- Accent: Warm amber `#C8956C` (dùng cho text trên thumbnail)
- Background: Near-black `#080C12`

**Brand voice:**
- Calming, quiet authority — như bác sĩ tâm lý nhẹ nhàng
- Không hype, không exclamation marks trong title
- Description viết như hướng dẫn chánh niệm (mindfulness)

**Channel art:**
- Avatar: Icon tối giản (mặt trăng, gợn sóng, lá cây ban đêm) — nền navy, icon lavender
- Banner: Dark gradient + tagline bằng serif font nhẹ (Playfair Display hoặc Cormorant)

---

## 3. Content Strategy — Theme Library

#### Tier 1 — High Search Volume (Upload ưu tiên)

| Theme | Title Formula | Search Intent | Video Length |
|---|---|---|---|
| Rain on window | Rain Sounds for Deep Sleep — {N} Hours | Sleep | 8–10h |
| Thunderstorm | Thunderstorm Sleep Sounds — Heavy Rain & Thunder {N}h | Sleep/anxiety | 8–10h |
| Ocean waves | Ocean Waves White Noise — Sleep, Study, Tinnitus Relief | Sleep/focus | 8–10h |
| Dark screen rain | Rain Sounds for Sleep — Black Screen {N} Hours | Sleep (screen off) | 10h |
| Fireplace + rain | Cozy Fireplace & Rain — Sleep Sounds {N} Hours | Winter/cozy sleep | 8h |

#### Tier 2 — Medium Volume, Low Competition

| Theme | Title Formula | Video Length |
|---|---|---|
| Rainy café (dark) | Dark Rainy Café Ambience for Sleep — {N} Hours | 8h |
| Library at night | Nighttime Library ASMR — Pages Turning, Distant Rain | 6–8h |
| Train rain | Sleeping on a Train — Rainy Night Sounds {N} Hours | 8h |
| Japanese garden rain | Japanese Rain Garden — Peaceful Sleep Sounds | 8h |
| Crickets + wind | Summer Night Crickets — Gentle Sleep Sounds | 8h |

#### Tier 3 — Seasonal / Trending

| Theme | When to post |
|---|---|
| Winter blizzard sounds | Tháng 10–Tháng 2 |
| Spring rain sounds | Tháng 3–5 |
| Christmas fireplace | Tháng 11–12 |
| Study sounds finals week | Tháng 4–5, Tháng 11–12 |

#### Upload Mix hàng tuần (3–4 video)

```
Tuần 1: Tier 1 + Tier 1 + Tier 2
Tuần 2: Tier 1 + Tier 2 + Tier 3 (nếu seasonal)
Tuần 3: Tier 1 + Tier 1 + Tier 2
...repeat
```

---

## 4. Đặc điểm âm thanh ASMR channel

**Nguyên tắc âm thanh:**
- Không có melody rõ (người ngủ bị đánh thức bởi melody)
- Binaural-leaning: stereo mix nhẹ, không 100% binaural (headphone không phổ biến khi ngủ)
- Dynamic range hẹp: không có đỉnh âm thanh đột ngột
- Sub-bass nhẹ (~40–80Hz): tạo cảm giác ấm, grounding — dùng EQ boost nhẹ
- High-frequency roll-off trên 12kHz: bớt harsh, dễ ngủ hơn

**Volume mix:**
```
Main sound (mưa/sóng): 0dB reference
Secondary layer (xa hơn): -8 đến -12dB
Tertiary (room tone): -18 đến -22dB
Music (nếu có): -15 đến -20dB (barely audible)
```

---

## 5. Prompt Templates

### 5.1 Suno AI — ASMR Channel

**Format chung:**
```
[Instrumental] [style description], [no melody/pure texture], [No Vocals], [mood], [frequency note], [duration intent]
```

**Template theo theme:**

#### Rain/Thunder
```
[Instrumental] heavy rainfall on glass window, distant rolling thunder, no melody, pure texture, [No Vocals], deep and immersive, slight reverb, dark and peaceful, analog warmth, 432Hz, [Sustained Texture]
```

#### Ocean Waves
```
[Instrumental] deep ocean waves on rocky shore, rhythmic surge and pull, sea foam, no melody, pure ambient texture, [No Vocals], hypnotic and meditative, stereo width, low sub-frequency presence, [Sustained Loop]
```

#### Fireplace
```
[Instrumental] crackling wood fireplace, soft ember pops, gentle fire roar, no melody, pure texture, [No Vocals], warm and cozy, intimate room acoustics, low-frequency warmth, [Sustained Ambient]
```

#### White Noise / Sleep
```
[Instrumental] pink noise blend with gentle rain undertone, no melody, pure texture, [No Vocals], smooth and consistent, no sudden changes, sleep-inducing frequency balance, [Continuous Loop]
```

---

### 5.2 Midjourney — ASMR Channel Visuals

**Style prefix chung:**
```
--style raw --ar 16:9 --q 2 --v 6.1
```

**Templates:**

#### Rain Window (Dark)
```
dark bedroom window at night, heavy rain streaks on glass, blurred city lights beyond, deep navy and charcoal tones, moody atmospheric photography, cinematic depth of field, no people --ar 16:9 --style raw --v 6.1
```

#### Thunderstorm
```
dramatic dark storm clouds over open ocean, lightning on horizon, turbulent grey waves, deep shadow photography, no people, atmospheric and powerful, 4k landscape --ar 16:9 --style raw --v 6.1
```

#### Fireplace Night
```
cozy stone fireplace glowing in dark room, warm amber light, single armchair, rain outside window barely visible, intimate interior, dark corners, photorealistic --ar 16:9 --style raw --v 6.1
```

---

### 5.3 Runway Gen-4 — Animation Prompts

**ASMR channel (subtle, sleep-friendly):**
```
Prompt: "Very slow, barely perceptible rain droplets running down glass. No camera movement. No sudden changes. Hypnotic loop."
Settings: Motion intensity: 1-2/10, Duration: 5s (loop), Camera: Static
```

---

## 6. SEO Templates

### 6.1 Title Formulas

**ASMR Channel:**
```
[Sound Description] for [Use Case] — [Duration] | [Modifier]
```

**Ví dụ thực tế:**
- `Rain Sounds for Deep Sleep — 8 Hours | Dark Screen ASMR`
- `Heavy Thunderstorm for Sleep — 10 Hours | No Ads`
- `Ocean Waves White Noise — 8 Hours | Sleep & Tinnitus Relief`
- `Cozy Fireplace & Rain — 8 Hours | Winter Sleep Sounds`
- `Gentle Rain on Window — 10 Hours | Dark Screen Sleep Aid`

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
[Opening line — mô tả cảnh/cảm giác, 1–2 câu gợi hình]

Fall asleep to the sound of [main sound], blended with [secondary sound]. This [N]-hour session is designed for [use case]: deep sleep, stress relief, or simply winding down after a long day.

🌙 WHAT YOU'LL HEAR:
• [Sound layer 1] — continuous and immersive
• [Sound layer 2] — gentle background texture
• [Sound layer 3 if applicable]

⏱️ CHAPTERS:
00:00 — Begin
[1h mark] — Mid session (same sound, slightly quieter)
[Final hour] — Fade preparation

🎵 ABOUT THIS AUDIO:
Created with intention using AI sound design tools. Curated and mastered for sleep optimization by [Channel Name].

✅ Safe for sleep timers — no sudden changes in volume or tone
✅ No ads mid-video
✅ Loops cleanly (playlist-safe)

💤 BEST FOR: Deep sleep · Insomnia relief · Stress & anxiety · White noise · Tinnitus masking · Nap sounds · Relaxation

#SleepSounds #RainSounds #ASMR #DeepSleep #WhiteNoise #SleepAid #RelaxingMusic #AmbientSound
```

---

### 6.3 Tag List Master

**ASMR Channel — 500 ký tự tags:**
```
sleep sounds, rain sounds for sleeping, asmr sleep, white noise, deep sleep music, rain sounds 8 hours, sleep aid, insomnia relief, relaxing sounds, thunderstorm sounds, ocean waves sleep, fireplace sounds, brown noise, pink noise, sleep music, dark screen rain, tinnitus relief, stress relief sounds, anxiety relief, sleep meditation
```

---

## 7. Thumbnail & Visual Guidelines

**Kích thước:** 1280x720px

**Composition:**
- 90%+ là visual atmospheric (ảnh từ Midjourney)
- Text tối thiểu — chỉ 2–3 từ nếu cần
- Không border, không gradient overlay quá nặng

**Text style (nếu có):**
- Font: Cormorant Garamond Italic hoặc Playfair Display
- Màu: Soft white `#F5F0E8` hoặc Lavender `#D4C9E2`
- Kích thước: Nhỏ, tinh tế (không phải big bold)
- Vị trí: Bottom 1/3, canh giữa

**Mood:** Dark, intimate, calming. Người nhìn vào phải cảm thấy buồn ngủ.

**Không làm:**
- ❌ Chữ to đỏ chói
- ❌ Nhiều element cạnh tranh nhau
- ❌ Màu sắc chói (bright yellow, red)
- ❌ Stock photo generic

**Template Canva setup:**
```
Nền: ảnh từ Midjourney (dark atmospheric)
Overlay: Linear gradient từ transparent → #080C12 (20% opacity, bottom 40%)
Text block: Bottom center, small serif font, soft white
```

---

## 8. Production Pipeline — Step by Step

### Tổng thời gian mỗi video: 60–80 phút

#### Bước 1 — Chọn theme & research (5 phút)
```
Vào TubeBuddy → Keyword Explorer → search theme dự kiến
Kiểm tra: Search volume, Competition score
✅ Chọn theme có Volume: Good/Excellent + Competition: Poor/Fair
Ghi lại exact keyword phrase → đây là title chính
```

#### Bước 2 — Tạo nhạc nền (Suno AI, 10 phút)
```
1. Mở Suno.ai → Create → Custom mode
2. Dán prompt từ template Section 5.1
3. Generate 4 variations → nghe nhanh mỗi cái 30 giây
4. Chọn variation tốt nhất
5. Suno "Extend" → kéo dài đến 4 phút
6. Download MP3 gốc
7. Đặt tên file: [channel]_[theme]_[YYYYMMDD]_v1.mp3
   Ví dụ: asmr_rain-thunder_20260501_v1.mp3
```

#### Bước 3 — Layer âm thanh thật (Freesound + Audacity, 20 phút)
```
1. Freesound.org → search: "[theme] recording" → filter Creative Commons
2. Download 2–3 sfx files
   - Rain: search "heavy rain recording stereo"
   - Thunder: search "distant thunder roll"
3. Mở Audacity:
   Track 1 (Music base): Suno MP3 → Loop đến 10h
   Track 2 (Foreground): Sfx chính (mưa) → 0dB, loop
   Track 3 (Midground): Sfx phụ (sấm xa) → -10dB
   Track 4 (Room tone): Pink noise nhẹ → -20dB
4. Mix: Check không có peak trên -3dB
5. Export: WAV 48kHz/24-bit (quality master)
6. Tên file: asmr_rain-thunder_20260501_MASTER.wav
```

#### Bước 4 — Tạo visual (Midjourney + Runway, 20 phút)
```
1. Midjourney → dán prompt từ template Section 5.2
2. Generate → Upscale ảnh đẹp nhất → Download
3. Runway Gen-4:
   - Upload ảnh → Motion: 1–2/10
   - Generate 5s loop
   - Preview: check không có glitch, không có sudden movement
   - Download MP4
4. Tên file: asmr_rain-thunder_20260501_visual.mp4
```

#### Bước 5 — Ghép video (CapCut, 15 phút)
```
1. New project → 1920x1080
2. Import: visual.mp4 + MASTER.wav
3. Loop visual đến khớp với audio (8–10h)
4. Thêm fade in 5 giây đầu, fade out 10 giây cuối
5. Export settings:
   - Resolution: 1920x1080
   - Frame rate: 24fps
   - Quality: High (hoặc 16Mbps)
   - Format: MP4 H.264
6. Tên file output: asmr_rain-thunder_20260501_FINAL.mp4
   Size ước tính: ~5–8GB cho 10h video
```

#### Bước 6 — Chuẩn bị upload metadata (10 phút)
```
Chạy automation script:
  python pipeline.py generate --channel asmr --theme "rain thunder" --length 10h --date 20260501

Script sẽ output:
  ✅ Title (3 variations)
  ✅ Description (filled template)
  ✅ Tags (comma-separated)
  ✅ Thumbnail filename suggestion
  ✅ Playlist assignment

Copy vào YouTube Studio
```

#### Bước 7 — Upload & Schedule (5 phút)
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

### ASMR Channel Stack (~$58/tháng)

| Tool | Mục đích | Chi phí/tháng |
|---|---|---|
| Suno AI Pro | Tạo nhạc nền ambient | $24 |
| Midjourney Basic | Tạo thumbnail/visual | $10 |
| Runway Basic | Animate visual (50 credits) | $15 |
| Audacity | Mix audio | Free |
| CapCut | Ghép video | Free |
| Freesound.org | Sfx thật | Free |
| TubeBuddy Lite | Keyword research | $9 |
| **Total** | | **$58/tháng** |

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
  --channel asmr \
  --theme "heavy rain thunderstorm" \
  --length 10h \
  --date 20260501
```

Output:
```
📺 TITLE OPTIONS:
  1. Heavy Thunderstorm & Rain Sounds for Sleep — 10 Hours | Dark Screen ASMR
  2. Thunderstorm Sleep Sounds — Heavy Rain & Rolling Thunder 10h
  3. Rain & Thunder for Deep Sleep — 10 Hour Sleep Aid

📝 DESCRIPTION: [filled template saved to output/asmr_rain-thunder_20260501_desc.txt]
🏷️  TAGS: [saved to output/asmr_rain-thunder_20260501_tags.txt]
📁 FILENAME: asmr_rain-thunder_20260501_FINAL.mp4
🎵 SUNO PROMPT: [saved to output/asmr_rain-thunder_20260501_suno.txt]
🖼️  MIDJOURNEY PROMPT: [saved to output/asmr_rain-thunder_20260501_mj.txt]
```

#### Quản lý upload queue
```bash
# Thêm video vào queue
python pipeline.py queue add \
  --channel asmr \
  --file asmr_rain-thunder_20260501_FINAL.mp4 \
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
python pipeline.py rename --folder ./raw_exports --channel asmr
```

#### Xem content calendar
```bash
python pipeline.py calendar --channel asmr --month 2026-05
```

---

## 11. Content Calendar — 3 tháng đầu

### Tháng 1 — Launch (Setup + Test)

**Tuần 1:**
| Ngày | Video | Theme |
|---|---|---|
| T2 | Upload 1 | Heavy Rain on Window — 8h |
| T4 | Upload 2 | Thunderstorm Sleep Sounds — 10h |
| T6 | Upload 3 | Ocean Waves White Noise — 8h |

**Tuần 2:** Dark Screen Rain 10h / Fireplace + Rain 8h / Gentle Rain Nighttime 8h

**Tuần 3:** Rain on Tent Camping 8h / Japanese Rain Garden 8h / Summer Night Crickets 8h

**Tuần 4 — Review:**
- Dừng 1 ngày để review analytics
- Video nào có AVD (Average View Duration) cao nhất? → Double down tháng 2
- Theme nào có CTR cao nhất? → Làm thêm variation
- Điều chỉnh upload schedule nếu cần

**Mục tiêu Tháng 1:**
- ✅ 12 video ASMR
- ✅ Xác định được top 3 performing themes
- ✅ Watch hours target: 500h

---

### Tháng 2 — Scale + Optimize

**Focus:** Double down themes hoạt động tốt từ Tháng 1

**ASMR — Upload 4 video/tuần:**
- 2 video variation của top theme (Rain, Thunder)
- 1 video theme mới (test)
- 1 video seasonal (nếu applicable)

**Tháng 2 targets:**
- ✅ 16 video (running total: 28)
- ✅ Watch hours: 1,500h (cumulative)
- ✅ Subscribers: 100–300
- ✅ Bắt đầu Shorts: 1 Short/ngày từ content đã có (clip 60 giây từ video dài)

---

### Tháng 3 — Monetize

**Focus:** Đạt threshold YPP (1K subs + 4K watch hours)

**ASMR: Upload 3–4 video/tuần (maintain nhưng focus vào quality)**

**ASMR theme focus Tháng 3:**
```
Week 1: Heavy Rain Compilation (Best Of) — 10h (playlist compilation)
Week 2: Spring Rain Theme — seasonal timing
Week 3: Study Rain Sounds — target student audience (exam season)
Week 4: Rainy Train Window — unique/different test
```

**Tháng 3 targets:**
- ✅ ASMR: 4K+ watch hours, 1K+ subscribers → Apply YPP
- ✅ Đăng ký DistroKid → Upload top 5 tracks lên Spotify
- ✅ Bắt đầu Pinterest boards cho visual content

---

### Shorts Strategy

**Format:** Cắt 58–60 giây từ video chính

**ASMR Shorts:**
- Tiêu đề: "60 Seconds of [Theme] — Do You Feel Sleepy? 😴"
- Call to action: "Full 8 hours on the channel →"

**Upload Shorts:** Hàng ngày, 9:00 AM giờ địa phương target audience (EST nếu target US market)

---

## 12. KPI & Success Metrics

### Metrics cần track mỗi tuần (30 phút review)

#### Performance Metrics
| Metric | ASMR Target (Tháng 3) |
|---|---|
| Total watch hours | 4,000h |
| Subscribers | 1,000 |
| Average View Duration | > 2h (cho video 8h) |
| CTR (Click-through rate) | > 3% |
| Impressions/tuần | Growing 10%+ |

#### Content Metrics
| Metric | Xem ở đâu | Đọc như thế nào |
|---|---|---|
| Average View Duration | YouTube Analytics > Content | Video nào dưới 20% AVD → xem xét xóa hoặc optimize |
| CTR | YouTube Analytics > Reach | Dưới 2%: thay thumbnail. Dưới 1%: thay title |
| Revenue per view | Monetize sau → RPM | ASMR phải đạt $10+, nếu thấp → adjust content |
| Traffic source | Analytics > Reach | Search % phải > 50% (tốt) |
| Returning viewers % | Analytics > Audience | > 20% = channel đang build loyal audience |

### Dấu hiệu cần can thiệp ngay

- ❗ CTR < 1% sau 500 impressions → Thay thumbnail ngay
- ❗ AVD < 15 phút cho video 8h → Audio có vấn đề (check layer, check sudden sounds)
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
- Album name: "[Channel Name] — Sleep Collection Vol. 1"
- Category: Ambient / New Age / ASMR
- Revenue: ~$0.003–0.005/stream → cần 100K streams/tháng để đáng kể nhưng passive 100%

---

*Dùng kết hợp với `pipeline.py` và `Channel_Launch_Plan_Soundscapes.md`.*
*Cập nhật lần cuối: 2026-04-29*
