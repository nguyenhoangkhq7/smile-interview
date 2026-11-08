# Simli cho phỏng vấn giọng nói

Simli thay hoàn toàn avatar GLB/Three.js và cơ chế nhép miệng cũ. STT, AI V2,
TTS OpenRouter và phụ đề người dùng vẫn dùng luồng phỏng vấn hiện tại.

Luồng đầu ra: TTS PCM → resample liên tục về PCM16 little-endian, mono, 16 kHz
→ Simli Compose → video và audio qua WebRTC/LiveKit → thẻ video/audio trên trang.
Không phát thêm bản TTS bằng Web Audio ở máy người dùng, tránh tiếng kép và lệch hình/tiếng.

## Cấu hình để chạy thật

1. Tạo tài khoản tại https://app.simli.com/ và lấy API key từ dashboard.
2. Chọn một avatar có sẵn hoặc tạo avatar trong Simli, lấy Face ID. Xem
   https://docs.simli.com/api-reference/preset-faces để chọn preset.
3. Thêm vào `ai-service/.env` (file này không đưa vào Git):

```dotenv
SIMLI_API_KEY=your_simli_api_key
SIMLI_FACE_ID=your_simli_face_id
```

Không đặt key trong `NEXT_PUBLIC_*` và không dán key vào chat. Hai giá trị này
khác với key OpenRouter. Giữ TTS ở định dạng `pcm`; cấu hình HeyGen TTS hiện tại
vẫn trả PCM 44.100 Hz, frontend chuyển sang 16.000 Hz cho Simli mà không cần đổi model.

4. Từ gốc dự án, build/recreate các dịch vụ để nạp cả mã và `.env` mới:

```powershell
docker compose up -d --build ai-service backend web-app
```

Nếu mã đã được cập nhật và bạn chỉ vừa điền/thay key hoặc Face ID, chỉ cần
`docker compose up -d --build ai-service`, sau đó tải lại trang.

5. Tải lại trang, chọn phỏng vấn giọng nói, bấm **Bắt đầu trò chuyện**, cấp quyền
   micro. Sau khi Simli trả khung video đầu tiên, AI mới bắt đầu đọc câu hỏi.

Khi thiếu cấu hình, ứng dụng báo dịch vụ Simli chưa sẵn sàng; không bật micro,
không gọi TTS, không quay về avatar 3D cũ. Video thật chưa thể kiểm tra khi chưa có key/Face ID.

## API và vòng đời

- `GET /api/v2/sessions/{id}/interview/voice/config` có `avatar.provider=simli`,
  `avatar.configured` và `avatar.sample_rate=16000`. Không trả API key hoặc Face ID.
- `POST .../voice/avatar-session`: body `{turn_id, expected_state_version}`.
  Backend xác thực chủ phiên, chế độ VOICE, turn/version hiện tại và hạn phiên;
  tự tính thời lượng tối đa còn lại. Response chỉ có `session_token`, `Cache-Control: no-store`.
- AI service gọi `POST https://api.simli.ai/compose/token` bằng header
  `x-simli-api-key`; Face ID chỉ lấy từ cấu hình máy chủ. Endpoint nội bộ
  `/api/v2/voice/avatar-session` không được đưa ra public gateway.
- Dùng `simli-client@3.2.0`, transport LiveKit mặc định. Không cần tự thuê LiveKit
  server hay cấp LiveKit key cho đường tích hợp browser này.
- Một phiên Simli được dùng cho nhiều câu hỏi. Chỉ gửi giọng đọc AI sang Simli;
  audio micro chỉ đi vào STT, không được gửi nhầm cho avatar.
- Nói chen hoặc chọn **Dừng** hủy request TTS, ngừng gửi các gói audio cũ,
  mute đầu ra ngay và gọi `ClearBuffer()`. Lần đọc sau mở lại audio.
- Kết thúc/rời trang, lỗi khởi động, mất kết nối hoặc hết hạn phỏng vấn đều đóng
  SDK, media stream và micro. Startup tối đa 35 giây; không tự tạo phiên trả phí
  mới để retry. Người dùng bấm bắt đầu lại khi cần; bản text đã nhận diện được giữ.
- **Tạm dừng micro** chỉ ngừng nghe, không kết thúc phiên Simli. Phiên Simli vẫn
  có thể tính usage khi chờ; **Kết thúc phiên** hoặc rời trang sẽ đóng kết nối.
  `maxIdleTime` tối đa 300 giây và không vượt thời gian phỏng vấn còn lại.

Simli có hạn mức/chi phí riêng với OpenRouter. Kiểm tra hạn mức trên dashboard;
không thể suy ra rằng Simli miễn phí vì TTS đang dùng model `:free`.

## Kiểm thử

Các kiểm thử sau không dùng key hoặc tiêu tốn phút Simli:

```powershell
# ai-service
python -B -m pytest tests_voice -q
# backend
.\mvnw.cmd -Dtest=EvidenceVoiceTest test
# web-app
node scripts/voice-audio-test.mjs
node scripts/simli-audio-test.mjs
```

Browser test toàn luồng dùng stand-in SDK chỉ trong development:

```powershell
$env:SIMLI_TEST_DRIVER='1'
npm run dev -- -p 3219
# terminal khác:
node scripts/voice-smoke.mjs http://localhost:3219
node scripts/evidence-smoke.mjs http://localhost:3219
```

Production luôn dùng SDK thật, bỏ qua `SIMLI_TEST_DRIVER`. Để kiểm tra UX thiếu
cấu hình mà không mở phiên thật: `node scripts/voice-smoke.mjs http://localhost:3000 --unconfigured`.
Video trong browser test được đánh dấu **SIMLI · TEST STREAM**, không phải hình
ảnh trả về từ Simli. Mock tests không chứng minh nhép miệng/độ trễ video thật.

Tài liệu chính thức: https://docs.simli.com/api-reference/javascript và
https://github.com/simliai/simli-client .

## Trạng thái xác minh

Đã đạt 21 kiểm thử Python voice/Simli, 9 kiểm thử backend voice, TypeScript/ESLint,
audio unit tests và browser test toàn luồng với SDK giả lập. Đã kiểm tra startup
chậm qua nhiều lần rerender, ngắt lời, PCM theo chunk, đóng phiên và hồi quy text.
Build production thành công; ba container đã cập nhật. Browser test production
xác nhận UX chưa cấu hình và chế độ text. Kiểm tra image production không có SDK
giả lập hoặc model GLB cũ. Máy chủ hiện báo `avatar.configured=false`; chưa gọi
Simli thật hoặc tiêu tốn phút Simli vì chưa có API key/Face ID.
