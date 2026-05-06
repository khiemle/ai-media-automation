# Visual Prompt — Bamboo Engawa Rain · Study Focus

**Video:** Bamboo Forest Wind — Japanese Ambience for Study
**Paired Suno prompt:** `suno-prompt_20260506-0158_study-focus_d-dorian_koto.md`
**Generated:** 2026-05-06

---

## Scene spec

| | |
|---|---|
| **Chủ đề** | Rừng tre — không khí Nhật Bản buổi chiều mưa |
| **Góc nhìn** | Hiên engawa truyền thống, ngồi trên sàn gỗ nhìn ra rừng tre |
| **Tiền cảnh** | Không có — tối giản, thiền định |
| **Thời gian** | Buổi chiều, bầu trời xám-trắng khuếch tán |
| **Thời tiết** | Mưa nhẹ, mù nhẹ trong rừng |
| **Phong cách** | Cinematic thực tế, 35mm, tông Kodak Portra (lạnh hơn, xanh lá hơn) |
| **Màu sắc** | Xanh lá rừng sâu · Xám-trắng bầu trời · Nâu gỗ ấm · Xanh-xám sương mù |
| **Loop** | Static cinemagraph — chỉ tre, mưa, sương mù chuyển động |

---

## Midjourney Prompt

Paste into Midjourney:

```
Traditional Japanese engawa wooden porch looking out onto dense bamboo forest in soft afternoon rain, no people, no foreground objects, bamboo stalks filling mid-ground and distance, misty grey-white diffuse overcast sky visible through bamboo canopy, fine diagonal rain streaks across the frame, small drips falling from engawa roof edge, cool forest-green tones, warm honey-brown wooden floor planks, diffuse soft light from above with no harsh shadows, 50mm lens, eye-level sitting perspective from engawa floor, extreme depth through bamboo rows into mist, 35mm film, Kodak Portra 400 slight cool push, Roger Deakins diffuse lighting, soft grain, wabi-sabi mood, hyper-detailed bamboo texture and wood grain, mist layered between bamboo rows, Japanese aesthetic, cinematic still frame --ar 16:9 --style raw --v 6.1 --q 2
```

**Gợi ý re-roll:** nếu Midjourney thêm người hoặc đồ vật lên sàn → thêm `--no people, no objects, no furniture` vào cuối. Nếu ảnh quá tối → thêm `soft diffuse daylight, bright grey sky`.

---

## Runway Gen-4 Prompt

Paste vào Runway khi dùng ảnh Midjourney làm input:

```
Bamboo stalks sway very gently in a soft lateral breeze from right to left, individual leaves trembling slightly at their own pace. Fine rain falls diagonally at a slow and steady rate across the entire frame, uniform and unhurried. Small drips fall irregularly from the engawa roof edge at the very top of frame, two or three seconds apart. Mist drifts imperceptibly deeper into the bamboo grove, barely visible movement. The wooden engawa floor remains completely motionless. Static camera, absolutely no camera movement. Slow, hypnotic, meditative pace. Designed for seamless looping. Rain and bamboo motion only.
```

**Runway settings:**
```
Motion intensity: 2 / 10
Duration: 5s (sẽ loop trong editor)
Camera motion: Static
Loop strategy: Static cinemagraph — crossfade end→start nếu cần
```

---

## Creative Brief

Người xem ngồi trên hiên engawa bằng gỗ của một ngôi nhà Nhật truyền thống, nhìn thẳng vào rừng tre dày đặc trong một buổi chiều mưa nhẹ. Không có gì giữa họ và khu rừng — không đồ vật, không điểm neo — chỉ có sàn gỗ và khoảng không gian mở ra trước mắt. Bầu trời xám trắng khuếch tán ánh sáng đều khắp, biến mọi thứ thành tông xanh lá mát lành.

Mưa rơi đều, xiên nhẹ trong gió. Từng cây tre uốn cong và lắc lư theo nhịp riêng. Vài giọt nước rơi từ mái hiên phía trên. Sương mù lãng đãng sâu trong rừng. Bốn chuyển động này — mưa, lắc lư, giọt rơi, sương — mỗi thứ chạy theo nhịp của riêng nó, không có đỉnh điểm và không có hồi kết.

Cảnh loop hoàn hảo vì không có yếu tố nào có điểm bắt đầu hay kết thúc rõ ràng. Mưa đã rơi trước khi clip bắt đầu và sẽ tiếp tục sau khi nó kết thúc. Hoàn toàn phù hợp với âm thanh koto thưa thớt và gió qua rừng tre của track nhạc đi kèm.

---

## Loop strategy (2–8 giờ YouTube)

1. **Generate ảnh Midjourney** → chọn ảnh đẹp nhất trong 4 lần render
2. **Upload vào Runway Gen-4** → dùng prompt trên, motion intensity 2/10, 5 giây
3. **Re-roll 2–3 lần** nếu cần cho đến khi chuyển động tự nhiên và không bị giật
4. **Kiểm tra loop:**
   - Cắt 1 giây cuối + 1 giây đầu → crossfade 0.5s → phải không nghe/thấy seam
   - Mưa phải chảy liên tục, tre không quay về vị trí giống hệt quá rõ ràng
5. **Trong editor (Premiere / DaVinci / ffmpeg):** loop clip 5 giây ~1440 lần cho video 2 giờ

```bash
# ffmpeg — loop 5-giây clip thành video 2 giờ với crossfade
ffmpeg -stream_loop 1439 -i bamboo_engawa_5s.mp4 \
  -vf "fade=t=in:st=0:d=0.5,fade=t=out:st=7199.5:d=0.5" \
  -t 7200 -c:v libx264 -crf 18 -preset slow \
  bamboo_engawa_2hr.mp4
```

---

## SFX Sound Design

*Thiết kế âm thanh môi trường theo từng lớp. Tất cả các âm thanh phải ở mức không khiến người nghe chú ý. Nguyên tắc: người nghe không bao giờ nhận ra âm thanh đang chạy — chỉ cảm thấy không gian sống động.*

---

### Layer 1 — Background (luôn bật, suốt toàn bộ video)

**Tiếng mưa nhẹ trên mái và lá tre — liên tục, đều đặn**
- Texture: broadband hiss thấp, không có giọt riêng lẻ, không có nhịp
- Cảm giác: như "im lặng" — lấp đầy room-tone mà không tạo ra bất kỳ chú ý nào
- Mix level: khoảng -30 dB so với nhạc — nghe như là "không khí của phòng"
- Loop: crossfade-based hoặc infinitely sustained — không có seam
- ❌ Không có sấm, không có gió mạnh đột ngột

> 🔍 **English prompt:**
> ```
> continuous soft rain hiss on bamboo leaves and roof, broadband texture no individual drops audible,
> no rhythm no pitch, steady and uniform throughout, no thunder no wind gusts,
> infinitely loopable ambient bed, very quiet background level (-30 dB relative to music)
> ```
> *Search: Freesound.org · Pixabay Sound · Epidemic Sound · Artlist*

---

### Layer 2 — Midground (mỗi 10–25 giây, không đều)

Những âm thanh định nghĩa "đây là rừng tre trong mưa". Xuất hiện đủ thường xuyên để cảm giác sống động, nhưng không đủ đều để não nhận ra nhịp.

1. **Giọt mưa trên lá tre riêng lẻ** — vài giọt nặng hơn rơi từ lá xuống lá bên dưới, 0.5–1s, không có attack sắc, fade-out ngay. Mỗi 12–18s.
   > 🔍 **English prompt:**
   > ```
   > rain drops falling from bamboo leaf to lower leaf, soft onset no sharp attack,
   > 0.5–1 second duration, natural drip tail, gentle fade-out, mid-distance,
   > sparse isolated events not rhythmic, quiet mid level
   > ```

2. **Tre kẽo kẹt nhẹ trong gió** — tiếng gỗ tre cọ vào nhau rất khẽ, thấp, 1–2s. Mỗi 15–22s.
   > 🔍 **English prompt:**
   > ```
   > bamboo stalks rubbing together gently in wind, low-pitched wooden creak,
   > soft onset gradual fade-out, 1–2 second duration, no sharp crack,
   > mid-distance outdoor, sparse irregular interval
   > ```

3. **Giọt nước từ mái hiên rơi xuống sàn đá** — một giọt nặng, rõ hơn một chút, rơi vào đá hoặc đất ướt bên ngoài, 0.3s. Mỗi 20–30s.
   > 🔍 **English prompt:**
   > ```
   > single heavy raindrop falling from roof eave onto wet stone ground,
   > 0.3 second duration, soft impact no harsh transient, short wet decay,
   > mid-foreground distance, isolated single event
   > ```

- Mix level: ~-18 đến -12 dB so với nhạc
- Tất cả entries: fade-in 0.3–0.5s, fade-out 0.5–1s — không có hard cut

---

### Layer 3 — Foreground (mỗi 45–60 giây, thưa thớt)

*(Cảnh này không có vật tiền cảnh — nên layer này rất thưa, chỉ 1–2 âm thanh gần gũi nhất)*

1. **Một giọt mưa lớn rơi ngay gần sàn engawa** — tiếng gõ nhẹ trên gỗ ẩm, 0.3s, gần hơn tất cả các âm thanh khác. Cảm giác như nó rơi ngay cạnh chỗ ngồi. Mỗi ~50s.
   > 🔍 **English prompt:**
   > ```
   > single large raindrop hitting wet wooden porch floor, close-mic foreground presence,
   > soft thud no sharp crack, 0.3 second duration, short damp decay on wet wood,
   > isolated single event, intimate close distance
   > ```

2. **Thân tre gõ nhẹ vào nhau một lần** — hai cái gõ thấp, 0.5s, rồi im lặng hoàn toàn. Mỗi ~55s.
   > 🔍 **English prompt:**
   > ```
   > two bamboo stalks knocking together once, low hollow unpitched knock,
   > two soft impacts 0.5 second total, no resonant pitch, gentle onset hard stop,
   > close-mid distance, single isolated event then silence
   > ```

- ❌ Không bao giờ chồng hai foreground sound cùng lúc
- Volume: có thể tiếp cận gần mức nhạc trong tích tắc, nhưng phải fade out nhanh

---

### Layer 4 — Random SFX List (trigger 1 âm thanh ngẫu nhiên mỗi 60–100 giây)

**Quy tắc phát:** fade-in 0.2–0.5s · fade-out 0.5–1.5s · không bao giờ to hơn nhạc · không lặp lại cùng âm thanh trong vòng 10 phút · shuffle trước khi loop lại danh sách.

**Half-asleep test:** mỗi âm thanh trong danh sách phải "đi qua" mà không kéo người đang nửa ngủ hoặc đang tập trung trở lại.

---

**1. Tiếng quạ xa**
Một tiếng kêu mờ, mềm, từ xa 20m+, 1.5s, tắt trước khi echo tan. Không phải tiếng kêu to.
*Xác nhận đây là rừng thật mà không làm giật mình.*
> 🔍 **English prompt:**
> ```
> single crow call far distance 20 metres, muffled soft low volume,
> 1.5 second duration, fades before echo resolves, no sharp attack,
> outdoor forest reverb, isolated single event not repeated
> ```

---

**2. Gió thổi qua tán tre**
Swell chậm 3s — chỉ là mass leaf movement, không có cọ xát thân cây. Dâng rồi hạ đều.
*Mở rộng không gian âm thanh lên phía trên.*
> 🔍 **English prompt:**
> ```
> wind swell through bamboo canopy, mass leaf movement only no stalk rubbing,
> slow gradual rise over 1.5 seconds hold 0.5 seconds fall over 1.5 seconds,
> 3 second total duration, smooth onset and release no sudden gust,
> mid-distance overhead, no pitch
> ```

---

**3. Tre gõ rỗng**
Hai tiếng gõ thấp, rỗng, khi hai thân tre chạm nhau trong gió, 0.8s. Không có pitch rõ ràng.
*Âm thanh đặc trưng của rừng tre — organic và quen thuộc.*
> 🔍 **English prompt:**
> ```
> two hollow bamboo stalks knocking together in wind, low unpitched hollow knock,
> two soft impacts within 0.8 second total, no resonant musical pitch,
> gentle onset natural decay, mid-distance, organic not percussive
> ```

---

**4. Giọt nước trên lá rộng**
Một giọt mưa rơi vào lá to (như lá chuối hoặc tre lớn), tap mềm + đuôi drip ngắn, 0.4s.
*Textural, gần gũi, không gây chú ý.*
> 🔍 **English prompt:**
> ```
> single raindrop hitting large broad leaf bamboo or tropical, soft tap impact,
> 0.4 second total, short natural drip tail, no sharp transient,
> close-mid distance, isolated single event quiet level
> ```

---

**5. Chuông chùa rất xa**
Một tiếng strike cực kỳ mờ, gần như chỉ cảm thấy hơn là nghe, decay 2–3s. Chỉ dùng 1 lần mỗi 15 phút.
*Đặt không gian vào văn hóa Nhật một cách tinh tế — không phải nhạc, chỉ là dấu vết.*
> 🔍 **English prompt:**
> ```
> single Japanese temple bell strike extremely distant, barely audible faint presence,
> 2–3 second reverb decay, strike almost felt not heard, very low volume,
> heavy low-pass filter applied above 3kHz, outdoor humid reverb,
> not musical not intrusive single event
> ```
> ⚠️ *Khi dùng: EQ cut toàn bộ trên 3kHz, giảm volume thêm -8 dB so với mặc định.*

---

**6. Tiếng ếch từ bụi tre**
Một tiếng kêu ngắn, mềm, 0.4s, mờ như từ trong bụi cây. Không phải tiếng ếch ao (không có splash).
*Sự sống trong rừng — không đòi hỏi chú ý.*
> 🔍 **English prompt:**
> ```
> single tree frog call soft and short, 0.4 second duration, muffled by dense foliage,
> no water splash no pond context, gentle onset quick natural fade,
> mid-distance from within bamboo undergrowth, quiet unobtrusive level
> ```

---

**7. Mưa tăng nhẹ trong 5 giây**
Background rain hiss tăng ~2 dB rồi trở về — không phải âm thanh mới, chỉ là texture variation. Fade in 2s, hold 1s, fade out 2s.
*Cảm giác gió nhẹ đi qua mưa — rất tự nhiên, không ai đặt câu hỏi.*
> 🔍 **English prompt:**
> ```
> [No audio file needed — volume automation only]
> Automate gain on Layer 1 background rain track:
> +2 dB over 2 seconds → hold 1 second → return to 0 dB over 2 seconds.
> Total duration 5 seconds. Simulates a light gust passing through the rain.
> ```

---

**8. Lá tre rụng qua thân cây**
Một nắm lá nhỏ rơi từ trên xuống, xào xạc nhẹ khi qua các tầng tre, 1.5s.
*Chuyển động rơi nhẹ — matched hoàn hảo với hình ảnh.*
> 🔍 **English prompt:**
> ```
> small cluster of dry leaves falling through bamboo stalks and branches,
> gentle rustling as they pass each layer, 1.5 second duration,
> soft onset builds slightly mid-fall then fades, no sharp impact at end,
> mid-distance overhead to ground, natural dry leaf texture
> ```

---

**9. Sàn engawa kẽo kẹt**
Một tiếng kẽo chậm, thấp của sàn gỗ co lại, 0.7s. Như ngôi nhà đang thở.
*Foreground nhắc nhở người xem rằng họ đang ngồi ở đó — không disturbing.*
> 🔍 **English prompt:**
> ```
> single slow wooden floorboard creak settling, low-pitched aged wood,
> 0.7 second duration, gradual onset no snap no sudden crack,
> smooth natural decay, close foreground distance interior,
> isolated single creak then silence
> ```

---

**10. Giọt nước vào vũng nước xa**
Một giọt rơi vào vũng nước ngoài frame, có echo ngắn của không gian ẩm, 1.2s.
*Thêm chiều sâu không gian mà không lộ nguồn âm thanh.*
> 🔍 **English prompt:**
> ```
> single water drop falling into shallow outdoor puddle, soft impact with short
> wet surface ripple, 1.2 second total with damp outdoor reverb tail,
> no sharp transient, off-screen mid-far distance,
> humid environment natural space, isolated single event
> ```

---

**11. Gió qua ống tre rỗng**
Tiếng thổi nhẹ qua một thân tre rỗng hoặc đầu cắt, tone thấp và mơ hồ, 1s. Không phải một note rõ ràng.
*Âm thanh đặc trưng Nhật Bản, không tonal đủ để cạnh tranh với nhạc.*
> 🔍 **English prompt:**
> ```
> wind passing through hollow bamboo tube or cut end, low breathy resonance,
> 1 second duration, ambiguous pitch no clear musical note,
> sounds like wind not a flute, soft onset and release,
> mid-distance outdoor, non-tonal airy texture only
> ```
> ⚠️ *Loại bỏ nếu file có pitch rõ ràng — chỉ dùng nếu nghe như tiếng gió, không phải tiếng sáo.*

---

**12. Im lặng sâu hơn (room tone swell)**
Không có file âm thanh — chỉ là volume automation. Toàn bộ SFX bus giảm nhẹ 1 dB trong 3s rồi trở về.
*Đôi khi khoảng lặng sâu hơn còn hiệu quả hơn bất kỳ âm thanh nào.*
> 🔍 **English prompt:**
> ```
> [No audio file needed — volume automation only]
> Automate gain on entire SFX bus master:
> -1 dB over 1.5 seconds → immediate return over 1.5 seconds.
> Total duration 3 seconds. Allows music to briefly surface.
> Creates a moment of deeper stillness without adding any sound.
> ```

---

## File pair

| File | Mục đích |
|---|---|
| `suno-prompt_20260506-0158_study-focus_d-dorian_koto.md` | Nhạc — Suno prompt |
| `output/visual_prompts/2026-05-06_soundscapes_bamboo-engawa-rain.md` | Hình ảnh + SFX — Midjourney + Runway + Sound Design |
| `skills/relax-music-visual-prompt/SKILL.md` | Skill đã cập nhật (có SFX layer) |
