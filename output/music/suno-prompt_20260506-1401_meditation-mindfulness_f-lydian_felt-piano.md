# Suno Prompt — Amazon Forest · Felt Piano Meditation

**Suno Custom Mode settings**
- Model: v4 (or v4.5 if available)
- Custom Mode: ON
- Instrumental: ON

---

### Style of Music (paste into Style field)
```text
ambient meditation music, felt piano, warm string ensemble pad, F Lydian mode, 62 BPM, slow harmonic rhythm, long reverb tail, intimate close-mic piano, sparse non-repeating melodic phrases, no percussion, no beat, no vocals, gentle contemplative atmosphere, soft analog warmth, Yellow Brick Cinema inspired, no intro no outro mid-texture start mid-texture end
```

### Title (paste into Title field)
```text
Amazon Forest · Felt Piano Meditation
```

### Lyrics field
Leave empty. If vocal-like sounds leak into the output, paste this single line:
```text
[Instrumental] [No Vocals] [Wordless]
```

### Exclude Styles (paste into Exclude Styles field)
```text
drums, percussion, beat, bass line, rhythm section, vocals, singing, choir, choral, lyrics, EDM, electronic dance, pop, rock, jazz, blues, hip hop, trap, dubstep, orchestral swell, dramatic build, intro fanfare, outro fade, nature sounds, rain sounds, bird calls, spoken word, voice, fast tempo, upbeat, energetic, strings pizzicato, harpsichord, music box
```

---

### Composer's notes
- **Function:** Meditation / Mindfulness
- **Key / mode:** F Lydian — raised 4th tạo cảm giác mở rộng, nhẹ nhàng, không có tension
- **Tempo:** 62 BPM — chậm đủ để não chuyển sang alpha-wave nhưng không gây buồn ngủ
- **Primary:** Felt Piano · **Bed:** Warm String Ensemble Pad · **Texture:** None (SFX rừng chạy riêng ở track ngoài)
- **Loop-safety:** Harmonic centre ổn định trên F, motif piano thưa không lặp đều nhịp, không fade-in/out, mid-texture start và end. An toàn để loop 40–50 lần cho video 3 giờ YouTube.
- **Paired visual:** `2026-05-06_soundscapes_amazon-rainforest-tropical-ambience.md`
- **Why this works:** Felt piano có sustain tự nhiên ngắn → khi kết hợp với reverb dài, note tan biến trước khi có thể trở thành melodic hook đáng nhớ. F Lydian's raised 4th mang cảm giác kỳ diệu, rộng lớn — phù hợp với cảnh rừng già Amazon chiều vàng.

---

### Post-generation quality check

**High priority — kiểm tra trước khi publish:**
- [ ] Không nghe thấy bất kỳ drumbeat, percussion, hoặc rhythmic pulse nào
- [ ] Không có vocals, choir, hơi thở, hoặc âm thanh giọng người
- [ ] Piano phrases tan vào reverb trước khi bắt đầu lại — không có lặp lại rõ ràng
- [ ] F Lydian tonal centre được giữ xuyên suốt — không có modulation đột ngột
- [ ] Dynamic phẳng từ đầu đến cuối — không có build-up hay crescendo

**Loop-safety check (bắt buộc cho 3h YouTube):**
- [ ] **Crossfade test:** fade từ clip-end sang clip-start trong 5 giây → không nghe ra điểm nối
- [ ] Không có giai điệu nào có thể hum lại sau 1 lần nghe
- [ ] Không có sonic event đơn lẻ nào sẽ gây chú ý nếu xuất hiện mỗi 4 phút trong 3 giờ
- [ ] Track bắt đầu và kết thúc ở giữa texture — không có "intro silence" hoặc "outro fade"

---

### Extension và looping strategy cho deliverable 3 giờ

**Bước 1 — Generate seed:**
Paste prompt vào Suno Custom Mode → generate 3–5 variations → chọn variation nào pass QC checklist tốt nhất.

**Bước 2 — Extend:**
Dùng Suno Extend từ điểm ~3:20 của mỗi clip (không phải cuối clip — tránh fade). Extend 10–12 lần để đạt ~45–50 phút audio unique.

**Bước 3 — Loop trong post-production:**
```bash
# ffmpeg loop để đạt đúng 3 giờ (10800 giây)
ffmpeg -stream_loop -1 -i your_45min_track.mp3 -t 10800 -c copy amazon_forest_3h.mp3
```
Hoặc trong DAW (Premiere, Final Cut, DaVinci): đặt 45-min block lên timeline, duplicate 3–4 lần, áp crossfade 5s tại mỗi điểm nối. Người nghe đang thiền định — loop không bị phát hiện với felt piano + pad configuration này.

---

*Generated: 2026-05-06 14:01 | Paired visual: 2026-05-06_soundscapes_amazon-rainforest-tropical-ambience*
