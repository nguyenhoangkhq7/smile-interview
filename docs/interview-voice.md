# Phỏng vấn V2 bằng giọng nói qua OpenRouter

Phiên mới có lời mở đầu, phần tự giới thiệu không chấm điểm và lời tạm biệt trước trang kết quả cho cả TEXT/VOICE. Xem [luồng hội thoại và hợp đồng lưu trạng thái](interview-lifecycle.md). Các mô tả câu hỏi bên dưới áp dụng cho giai đoạn chuyên môn; phiên cũ giữ nguyên luồng đang chạy.

Luồng: micro → nhận diện giọng nói → bản nháp câu trả lời → API V2 hiện có → câu hỏi tiếp theo → TTS streaming → Simli video/audio realtime.

## Nhận diện ưu tiên độ chính xác

STT chỉ dùng **một model: `openai/gpt-transcribe` qua OpenRouter**. Mỗi request preview hoặc final gọi provider đúng một lần, không gọi model thứ hai để đối chiếu, không bắt chọn giữa hai bản chữ. Biến cũ `OPENROUTER_STT_VERIFIER_MODEL` không còn được đọc. Không dùng LLM viết lại nội dung hay sửa kiến thức của ứng viên. Model được giữ vì đã nhận đúng câu tổng hợp Việt–Anh trên môi trường local; đây không phải benchmark giọng thật.

- Capture dùng AudioContext 16 kHz và worklet 1.024 mẫu; trình duyệt thực hiện resampling. Echo cancellation/noise suppression vẫn bật. VAD hiện vẫn dựa trên năng lượng, chưa phải neural/semantic VAD.
- Khi nói liên tục, đoạn khoảng 4 giây tạo **phụ đề tạm**. Chúng không ghi vào câu trả lời dùng để chấm điểm.
- Audio gốc được giữ trong bộ nhớ, gom đến khi nghỉ hoặc đủ khoảng 24 giây. Bản chính thức nhận diện lại toàn bộ cửa sổ này, thay thế các phụ đề thuộc cửa sổ, không nối kết quả chính thức vào phụ đề cũ. Giới hạn WAV API vẫn là 45 giây. Cửa sổ dài liên tiếp không có overlap; tất cả frame lời nói có đúng một cửa sổ chính thức.
- Backend lấy `jd_skill_id` từ snapshot kỹ năng của phiên (được tạo từ CV/JD) và câu hỏi đã lưu; AI service bổ sung một số tên công nghệ liên quan. Không gửi toàn bộ CV/JD, rubric hay đáp án mẫu làm gợi ý. Vocabulary giới hạn 80 mục. MAI dùng `provider.options.azure.phraseList.phrases`, `verbatim` và auto-detect ngôn ngữ để giữ câu Việt–Anh. GPT dùng provider options `languages`, `keywords`, `prompt`; live acceptance không chứng minh provider thực sự áp dụng mọi hint.
- Bản final là kết quả trực tiếp của cùng model trên audio dài hơn, giữ nguyên từ ngữ của ứng viên. Không còn bước so sánh chữ, chuẩn hóa từ đệm để đối chiếu hay model verifier. Final thành công được dùng làm câu trả lời; không hiển thị hộp chọn bản đối chiếu.
- Model lỗi/429 hoặc trả rỗng được coi là lỗi có thể thử lại. Giữ bản ghi để retry, không tự gọi model khác hoặc âm thầm mất lời. Không gắn nhãn kết quả là đã xác minh đúng; trường `verification` trả `not_requested`.
- Preview chưa chạy được bỏ khi cửa sổ chính thức đã sẵn sàng. Queue giới hạn và tự tạm dừng khi quá tải, giữ bản ghi. Tạm dừng, mở hộp thoại và nghe lại câu hỏi flush phần audio còn lại thay vì bỏ mất. Kết quả đến muộn sau đổi turn/rời trang bị bỏ. HTTP client STT tái sử dụng kết nối và đóng khi service shutdown.

Một model vẫn có thể nhận audio ở cả preview và final để có phụ đề sớm và bản chốt đủ ngữ cảnh. Đây không phải mỗi đoạn audio chỉ gửi đúng một lần; đã bỏ chi phí/độ trễ của model đối chiếu. Đây vẫn là STT theo đoạn qua OpenRouter, không phải streaming từng từ.

Kiểm thử: `node scripts/voice-recognition-test.mjs`, `node scripts/voice-audio-test.mjs`, browser smoke cho thay thế preview/giữ audio, Python `tests_voice` (xác nhận đúng một provider call kể cả khi còn biến verifier cũ), backend `EvidenceVoiceTest`/`EvidenceServiceTest`. UI vẫn hiểu contract cũ để không cần cập nhật đồng thời các client; service hiện luôn trả `review_required=false`.

Live check có tính phí: `python -B scripts/verify-voice-openrouter.py --audio-file path/to/mono-16khz.wav`. Không truyền audio riêng tư vào bộ test tự động. Có thể dùng `--save-audio .pytest_cache/voice-test.wav` khi tổng hợp để thử lại STT mà không gọi TTS lần nữa. Mock/synthetic tests không đánh giá được độ chính xác trên giọng thật; cần bộ câu Việt–Anh do người dùng đọc để so sánh model.

## Hai trải nghiệm riêng

Trước khi bắt đầu, người dùng chọn **Bằng văn bản** hoặc **Bằng giọng nói**. `config.interaction_mode` (`TEXT` / `VOICE`) được lưu trong config/snapshot/public state và khóa khi phiên đã bắt đầu. Phiên V2 cũ không có trường này mặc định là `TEXT`; không cần migration DB vì cấu hình đang được lưu dạng JSON.

- **TEXT**: chỉ hiển thị câu hỏi, ô trả lời/code và lịch sử. Không mount hook micro, không tải avatar và không gọi STT/TTS. Backend chặn endpoint giọng nói đối với phiên text.
- **VOICE**: ba vùng chính gồm avatar AI, câu hỏi AI đang hỏi và bản ghi câu trả lời voice chỉ đọc của người dùng. Câu hỏi lấy từ cùng turn đã lưu dùng cho TTS, có cả lời chuyển tiếp khi có. Không có ô nhập text, editor hoặc lịch sử chat trên màn chính. Trạng thái nghe nằm trong thanh điều khiển nhỏ; phụ đề cập nhật khi STT trả về từng đoạn. Câu trả lời vừa gửi được giữ trên màn hình tới khi người dùng bắt đầu trả lời câu tiếp theo.
- **Coding/Debugging trong VOICE**: người dùng giải thích hướng giải, thuật toán, luồng xử lý, trường hợp biên, độ phức tạp, cách kiểm tra hoặc chẩn đoán lỗi bằng lời. Generator được hướng dẫn hỏi tình huống cụ thể, giữ độ sâu kỹ thuật nhưng không đòi code/editor/bảng/biểu đồ. Judge nhận `interaction_mode` để đánh giá lời giải thích, không trừ điểm chỉ vì không nộp code. Nếu tiêu chí thật sự đòi bằng chứng thực thi thì ghi thiếu bằng chứng, không suy diễn đã kiểm chứng code. Chế độ TEXT vẫn làm bài coding bằng code.

Hai giao diện chỉ dùng chung phần quản lý phiên, đánh giá và báo cáo; mã giọng nói được lazy-load riêng.

Avatar hiện dùng **Simli Compose**, thay hoàn toàn model GLB/Three.js cũ. Cần `SIMLI_API_KEY` và `SIMLI_FACE_ID` trên AI service. Xem [hướng dẫn cấu hình và kiểm thử Simli](simli-avatar.md).

Giao diện desktop đặt avatar bên trái, câu hỏi và câu trả lời xếp chồng bên phải. Mobile xếp ba vùng theo chiều dọc; nội dung dài cuộn trong từng vùng. Thanh phụ bên dưới giữ trạng thái và các nút micro, nghe lại, gửi xong, tùy chỉnh. Tiến độ, thời gian còn lại, tùy chọn chuyển lượt và kết thúc phiên được gom vào **Tùy chỉnh cuộc trò chuyện**; kết thúc vẫn có xác nhận. Lỗi mới hiện các thao tác thử lại. Contract STT cũ yêu cầu xác nhận sẽ mở hộp riêng; không chiếm màn chính khi không có vấn đề. Phụ đề cũ không được hiển thị thay cho bản ghi mới đang lỗi.

Tất cả STT/TTS gọi OpenRouter bằng khóa trên AI service. Frontend chỉ gọi backend có JWT; backend kiểm tra chủ phiên, câu hỏi, version và hạn phiên trước khi sử dụng model. Việc bật giọng nói không tạo một engine đánh giá thứ hai, không thay đổi rubric hoặc cách tính báo cáo.

## Cấu hình

Giữ `OPENROUTER_API_KEY` ở `.env` gốc hoặc `ai-service/.env`. Không dùng biến `NEXT_PUBLIC_` cho khóa. AI service đọc `.env` gốc, rồi `ai-service/.env` với ưu tiên cao hơn. Docker Compose cũng truyền hai file này vào AI service.

```dotenv
OPENROUTER_MODEL=qwen/qwen3.7-flash
INTERVIEW_VOICE_ENABLED=true
OPENROUTER_STT_MODEL=openai/gpt-transcribe
OPENROUTER_TTS_MODEL=heygen/heygen-voice-1-turbo:free
OPENROUTER_TTS_VOICE=nadine
OPENROUTER_TTS_FORMAT=pcm
OPENROUTER_TTS_SAMPLE_RATE=44100
```

TTS mặc định dùng `heygen/heygen-voice-1-turbo:free` để develop. Model chỉ đọc tiếng, không nhận diện âm thanh và không tạo avatar. STT Qwen và AI text vẫn tính phí riêng. Theo [OpenRouter](https://openrouter.ai/heygen/heygen-voice-1-turbo%3Afree), bản free có giới hạn tần suất, tối đa 5.000 ký tự mỗi yêu cầu và dự kiến kết thúc ngày 30/11/2026. Server báo lỗi rõ ràng trước khi gọi provider nếu văn bản sau làm sạch vượt giới hạn; không tự cắt mất phần câu hỏi hay chuyển sang model trả phí.

Voice `nadine` thuộc [danh mục giọng HeyGen trên OpenRouter](https://openrouter.ai/api/v1/models?output_modalities=speech). Có thể thay bằng `tabitha`, `bram`, `gareth`, `noelle`, `meredith`, `sabrina`, `lucian`, `weston`, `vincent`. Không dùng `Kore` của Gemini với HeyGen. Chất lượng phát âm tiếng Việt phải được nghe thử trên giọng đã chọn.

Nếu quay lại Gemini: đặt `OPENROUTER_TTS_MODEL=google/gemini-3.8-flash-lite-tts`, `OPENROUTER_TTS_VOICE=Kore`, `OPENROUTER_TTS_FORMAT=pcm`, `OPENROUTER_TTS_SAMPLE_RATE=24000`. Không tự chuyển nhà cung cấp hoặc giọng trình duyệt khi lỗi.

`pcm` được phát trong lúc tải (signed 16-bit little-endian, mono). HeyGen yêu cầu PCM 44,1 kHz; server chặn cấu hình format/tần số không phù hợp để tránh phát sai tốc độ. `mp3` cũng dùng được với model hỗ trợ, nhưng frontend phải tải và giải mã đầy đủ trước khi phát. Frontend chuyển âm thanh micro thành WAV mono 16 kHz để tránh phụ thuộc codec MediaRecorder của trình duyệt; tần số đầu ra TTS độc lập với đầu vào STT.

Tài liệu giao thức:

- https://openrouter.ai/docs/guides/overview/multimodal/stt
- https://openrouter.ai/docs/guides/overview/multimodal/tts

## Chạy và sử dụng

Khởi động lại AI service, backend và web-app theo cách chạy dự án hiện tại. Với Docker Compose từ gốc repo:

```powershell
docker compose up -d --build ai-service backend web-app
```

Ở bước chuẩn bị, chọn **Bằng giọng nói**, bắt đầu phiên, rồi chọn **Bắt đầu trò chuyện** để cấp quyền micro trên HTTPS hoặc localhost. Avatar đọc câu hỏi hiện tại. Người dùng có thể nói chen để dừng tiếng AI; hoặc dùng **Dừng giọng đọc**, **Nghe lại câu hỏi**, **Tạm dừng micro**. Chế độ text bắt đầu trực tiếp với giao diện nhập văn bản.

Mặc định, sau khoảng im lặng 1,2 giây, đoạn nói còn lại được gửi nhận diện. Sau khi nhận diện xong, ứng dụng chờ thêm 1 giây trước khi tự gửi vào V2. Nói tiếp hoặc mở hộp thoại kết thúc sẽ hủy lần tự gửi đang chờ. Trong **Tùy chỉnh cuộc trò chuyện**, có thể tăng khoảng nghỉ hoặc tắt **Tự gửi khi nói xong**, sau đó dùng **Tôi đã trả lời xong**. Câu hỏi lập trình bằng lời dùng cùng cơ chế chuyển lượt này.

Đây là phát hiện tiếng nói dựa trên năng lượng âm thanh và khoảng im lặng, chưa phải nhận biết kết thúc ý theo ngữ nghĩa. Chưa có bước AI hội thoại riêng để trả lời các câu hỏi ngoài luồng; câu nói được gom vào bản nháp trả lời V2. Dùng tai nghe để hạn chế tiếng vọng làm ngắt lời nhầm. Ngắt lời yêu cầu tiếng nói kéo dài khoảng 180 ms.

Khi nói liên tục, audio được chia khoảng 4 giây để cập nhật phụ đề trong lúc người dùng vẫn nói. Đây là STT theo đoạn, không phải phụ đề streaming từng từ: có thêm độ trễ mạng/model. Ranh giới đoạn không kết thúc lượt trả lời, không lặp/bỏ frame audio; đoạn đuôi chỉ có im lặng không gửi STT. Bản ghi nhận diện lỗi được giữ trong bộ nhớ, có nút thử lại hoặc bỏ đoạn lỗi; không lưu audio xuống DB. Sau lỗi đánh giá, câu trả lời/request ID vẫn được giữ như V2 để thử lại thủ công. Kết thúc phiên hoặc rời trang giải phóng micro, AudioContext và hủy yêu cầu đang chờ. Reload giữ chế độ phỏng vấn đã chọn nhưng không tự bật lại micro.

Simli nhận audio TTS đã chuyển sang PCM16 mono 16 kHz và trả video/âm thanh đồng bộ qua SDK; frontend không phát audio TTS lần thứ hai và không nối sang streaming-service cũ ở cổng 8001. API đọc tiếng chỉ nhận turn/version, backend tự lấy `introduction` (nhận xét ngắn về câu trả lời trước và lời chuyển tiếp) cùng câu hỏi đã lưu, rồi đọc trong một luồng TTS. Câu đầu chỉ đọc câu hỏi. Không nhận text tùy ý từ trình duyệt và không tạo một yêu cầu TTS riêng cho phần nhận xét.

## API

Public, yêu cầu JWT của chủ phiên:

- `GET /api/v2/sessions/{id}/interview/voice/config`
- `POST .../voice/transcribe`: `{turn_id, expected_state_version, audio, phase}`; `audio` là base64 WAV, `phase` là `preview` hoặc `final` (mặc định). Trả `{text, phase, verification: "not_requested", review_required: false}`; không trả `alternative_text`. Client không tự chọn model, vocabulary hay topic; backend lấy từ phiên đã xác thực. Mỗi request gọi đúng một model một lần. Timeout frontend 115 giây/backend 110 giây là trần bảo vệ cũ, không phải thời gian chờ cố định.
- `POST .../voice/speech`: `{turn_id, expected_state_version}`; trả raw audio stream với `X-Audio-Format` và `X-Audio-Sample-Rate`.

Internal, chỉ giữ trong mạng backend: `/api/v2/voice/config`, `/transcribe`, `/speech` trên AI service. Các endpoint voice không ghi trạng thái phỏng vấn. Bản nháp chỉ được đánh giá khi đi qua `/interview/respond` thông thường.

Java voice client phải dùng HTTP/1.1 với Uvicorn. Mặc định JDK thử nâng kết nối h2c; khi Uvicorn không hỗ trợ sẽ có `Unsupported upgrade request`, body POST bị đọc thiếu (`422` với `detail.loc=["body"]`), rồi `Invalid HTTP request received` do frame HTTP/2. `VoiceAiClient` đã khóa `HTTP_1_1` cho cả config, speech và transcribe. Đây là lỗi truyền tải nội bộ, không được chữa bằng cách đổi model hoặc cài thư viện WebSocket. Kiểm tra phân biệt với 422 do WAV hoặc nội dung đầu vào không hợp lệ.

Tắt proxy buffering cho đường `/voice/speech` nếu dùng Nginx/gateway. Upstream/server trả `Cache-Control: no-store`, `X-Accel-Buffering: no`. Khóa API không đi ra trình duyệt; lỗi upstream không trả lại body chứa audio hoặc thông tin bí mật.

## Kiểm tra

Từ `ai-service`:

```powershell
python -B -m pytest tests_voice -q
```

Từ `backend`, dùng JDK tương thích:

```powershell
.\mvnw.cmd -Dtest=EvidenceVoiceTest,EvidenceAiClientTest,EvidenceServiceTest test
```

Từ `web-app`:

```powershell
node scripts/voice-audio-test.mjs
npm run build
# Chạy frontend tại URL tương ứng trước:
node scripts/voice-smoke.mjs http://localhost:3000
node scripts/evidence-smoke.mjs http://localhost:3000
```

Live smoke từ gốc repo, có dùng số dư OpenRouter: `python -B scripts/verify-voice-openrouter.py`. Chỉ tổng hợp một câu thử tiếng Việt và nhận diện lại, không gửi CV/JD. Các kiểm thử tự động còn lại dùng HTTP/micro giả lập và không tiêu tốn API.

Chỉ kiểm tra model đọc tiếng free, không gọi STT: `python -B scripts/verify-voice-openrouter.py --tts-only`. Đảm bảo cấu hình đang trỏ đúng slug `:free` trước khi chạy. Script kiểm tra audio nhận về, không đánh giá chất lượng phát âm.

Không suy ra chất lượng tiếng Việt hoặc độ trễ thực tế từ mock tests. Cần chạy live smoke và thử micro thật trên đúng thiết bị/mạng trước khi đưa vào vận hành.

Kiểm thử nền trước đó: 40 ca Python (voice và hồi quy V2), 21 ca backend, TypeScript/ESLint, WAV/PCM/VAD và browser smoke cho hai giao diện riêng với micro/HTTP tổng hợp; build production thành công.

Đợt trả lời coding bằng lời và thêm phụ đề: 44 ca Python (voice, workflow, judge recovery), TypeScript/ESLint, audio unit tests và browser smoke cho hai chế độ đạt. Kiểm thử phụ đề xuất hiện trước khi người dùng ngừng nói, nối nhiều đoạn thành một câu trả lời, không tự gửi ở ranh giới đoạn, không mất/lặp frame và không gửi đuôi im lặng. Voice không có editor hay ô nhập; nội dung nhận diện được hiển thị chỉ đọc và giữ lại sau khi gửi.

Đợt thiết kế lại giao diện: TypeScript/ESLint và build production đạt; browser smoke chạy trên container web mới cho cả voice/text. Đã kiểm tra desktop 1440×900, màn hình thấp 800×600, mobile 320×740 và 390×844; nút bắt đầu vẫn trong màn hình, không tràn ngang, hộp cài đặt vừa viewport. Kiểm tra Escape/khôi phục focus, tạm dừng, thử lại nhận diện, trạng thái phụ đề và kết thúc phiên. Avatar có báo đang tải và nội dung thay thế khi WebGL không hỗ trợ; hiệu ứng trạng thái tôn trọng `prefers-reduced-motion`.

Đợt đổi HeyGen free: 14 ca Python voice và 5 ca backend voice đạt; kiểm tra cả việc không gửi header h2c trên ba endpoint và truyền nguyên vẹn JSON/PCM 44,1 kHz. Đã tái hiện trên Uvicorn thật: client JDK mặc định trả 422 thiếu body, HTTP/1.1 đọc đúng body. Đã rebuild/recreate hai container backend/AI. Live TTS từ container qua OpenRouter thành công với một câu tổng hợp tiếng Việt, nhận 286.460 byte PCM, mẫu đầu sau khoảng 2,78 giây, hoàn tất sau 3,27 giây. Đây là một lần đo, không phải SLA hay đánh giá chất lượng phát âm. Kết nối từ host vẫn không được OpenRouter; live STT và cuộc hội thoại đầy đủ với micro thật chưa được xác nhận trong đợt này.
