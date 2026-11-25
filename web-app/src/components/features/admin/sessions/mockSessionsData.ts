import { InspectedSessionData, SessionFilterTabKey } from './types';

export const SESSION_FILTER_TABS: {
  key: SessionFilterTabKey;
  label: string;
  count: number;
  isAnomaly?: boolean;
}[] = [
  { key: 'all', label: 'Tất cả phiên', count: 8750 },
  { key: 'completed', label: 'Đã hoàn thành', count: 7438 },
  { key: 'in_progress', label: 'Đang diễn ra', count: 124 },
  { key: 'anomaly', label: 'Phiên bất thường ⚠️', count: 32, isAnomaly: true },
];

export const DEFAULT_INSPECTED_SESSION: InspectedSessionData = {
  sessionId: '#SESS-2025-0891',
  traceToken: 'tk_891e4a_v2',
  candidateName: 'Nguyễn Hoàng Nam',
  candidateId: 'CAN-90182',
  candidateEmail: 'nam.nguyen@gmail.com',
  candidateAvatarUrl:
    'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=240&q=80',
  workspaceImageUrl:
    'https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=600&q=80',
  roleTitle: 'Senior Backend Engineer (Go/Distributed Systems) - VNG',
  shortRoleBadge: 'Senior Go Backend',
  matchingScorePct: 78.4,
  statusLabel: 'Hoàn thành (Completed)',
  durationLabel: '28m 15s',
  fullDurationText: '28 phút 15 giây',
  modeLabel: 'Mode: VOICE (Simli Avatar 3D)',
  overallRatingLabel: 'Đánh giá chung: 5/5',
  endingReasonLabel: 'Hoàn thành kế hoạch (Blueprint Goals)',
  fallbackUsedLabel: '0 / 2 allowed',
  pipelineStages: [
    {
      id: 1,
      stepCode: '01. CV & JD Đầu vào',
      title: '01. CV & JD Đầu vào',
      description: 'PDF CV 2 trang + JD 18 tiêu chí kỹ thuật.',
      leftMeta: '24 entities trích xuất',
      rightMeta: '100% OK',
    },
    {
      id: 2,
      stepCode: '02. Matching & Gap',
      title: '02. Matching & Gap',
      description: 'SBERT + GNN Similarity đạt 78.4%.',
      leftMeta: '4 Skill gaps phát hiện',
      rightMeta: 'SBERT',
      isErrorMeta: true,
    },
    {
      id: 3,
      stepCode: '03. Blueprint Snapshot',
      title: '03. Blueprint Snapshot',
      description: 'Policy v2.4, Max 8 câu hỏi, fallback_depth=2.',
      leftMeta: 'Rubric 6 levels',
      rightMeta: 'Locked',
      isLockedMeta: true,
    },
    {
      id: 4,
      stepCode: '04. Transcript & Evidence',
      title: '04. Transcript & Evidence',
      description: '8 lượt tương tác đối thoại thích ứng sâu.',
      leftMeta: '8/8 turns annotated',
      rightMeta: 'Active',
    },
    {
      id: 5,
      stepCode: '05. Final Evaluation',
      title: '05. Final Evaluation',
      description: 'Nghiệm thu hoàn tất. 4/5 năng lực đạt & vượt chuẩn.',
      leftMeta: 'Đã nghiệm thu',
      rightMeta: 'PDF Ready',
      isVerifiedStep: true,
    },
  ],
  turns: [
    {
      id: 'T1',
      pillLabel: 'T1: Chào hỏi & Warming',
      dotVariant: 'emerald',
      turnBadge: 'TURN 01',
      topicTitle: 'Giới thiệu kinh nghiệm hệ thống phân tán & kiến trúc ví điện tử',
      timeRange: '00:15 - 03:40',
      depthLabel: 'Depth: Level 1 (Warm-up)',
      aiStrategyTag: 'Context Grounding & Rapport',
      aiStrategyDescription:
        'Xác nhận bối cảnh dự án Payment Gateway tại công ty cũ của ứng viên để làm cơ sở dẫn dắt vào các tiêu chí kỹ thuật chuyên sâu.',
      aiTimestamp: '00:15',
      aiTtsQuality: 'TTS Synthesis 99%',
      aiPromptText:
        '"Chào Nam, rất vui được trao đổi cùng anh hôm nay. Trước khi đi sâu vào kiến trúc kỹ thuật, anh có thể chia sẻ ngắn gọn về vai trò của mình trong dự án nâng cấp Core Wallet lên 100k TPS gần đây nhất không?"',
      candidateInitials: 'HN',
      candidateName: 'Nguyễn Hoàng Nam',
      candidateTimestamp: '00:38',
      candidateConfidencePct: 96.0,
      audioDuration: '01:22',
      transcriptBeforeMark:
        '"Chào anh, trong dự án Core Wallet mình phụ trách chính mảng thiết kế luồng xử lý giao dịch thời gian thực bằng Golang. ',
      transcriptHighlightedMark:
        'Trọng tâm của mình là tách cụm Monolith cũ sang kiến trúc Event-driven Microservices sử dụng Kafka và gRPC kết nối nội bộ',
      transcriptAfterMark: ', giúp giảm độ trễ xử lý trung bình từ 120ms xuống dưới 15ms."',
      transcriptSecondParagraph:
        '"Ngoài ra mình cũng trực tiếp thiết kế cơ chế đối soát bất đồng bộ cuối ngày cho hơn 12 triệu ví hoạt động."',
      pitchLabel: 'Pitch: Confident',
      evidenceCode: '#EV-891-1',
      rubricLevel: 'DEMONSTRATED_AT_TARGET',
      linkedSkill: 'Event-Driven Microservices & gRPC',
      taxonomyCode: 'ARCH_MICROSERVICES_GOLANG_L2',
      confidenceScoreLabel: 'Confidence Score: 0.91 / 1.0',
      sourceTag: 'CV Claim Verified',
      sourceNote: 'Khớp hoàn toàn với mô tả dự án trang 1 trong CV ứng viên.',
      exactQuote:
        '"Tách cụm Monolith cũ sang kiến trúc Event-driven Microservices sử dụng Kafka và gRPC kết nối nội bộ... giảm độ trễ từ 120ms xuống dưới 15ms."',
    },
    {
      id: 'T2',
      pillLabel: 'T2: Microservices & Go',
      dotVariant: 'emerald',
      turnBadge: 'TURN 02',
      topicTitle: 'Quản lý Goroutine Leak & Backpressure trong tải cao',
      timeRange: '03:45 - 09:30',
      depthLabel: 'Depth: Level 2 (Technical Probe)',
      aiStrategyTag: 'Skill Depth Verification',
      aiStrategyDescription:
        'Kiểm tra năng lực xử lý đồng thời trong Golang khi downstream service bị nghẽn để đánh giá khả năng vận hành thực tế.',
      aiTimestamp: '03:45',
      aiTtsQuality: 'TTS Synthesis 98%',
      aiPromptText:
        '"Khi một dịch vụ bên thứ ba (như cổng ngân hàng) phản hồi chậm bất thường, anh kiểm soát vòng đời Goroutines và kênh truyền (Channels) như thế nào để tránh cạn kiệt bộ nhớ (OOM)?"',
      candidateInitials: 'HN',
      candidateName: 'Nguyễn Hoàng Nam',
      candidateTimestamp: '04:10',
      candidateConfidencePct: 95.4,
      audioDuration: '02:05',
      transcriptBeforeMark:
        '"Chúng tôi tuyệt đối không spawn Goroutine vô tội vạ cho mỗi request. ',
      transcriptHighlightedMark:
        'Hệ thống áp dụng Worker Pool cố định kết hợp với context.WithTimeout và Circuit Breaker (Gobreaker) để ngắt sớm khi tỷ lệ timeout vượt ngưỡng 5%',
      transcriptAfterMark:
        '. Mọi channel đều là buffered channel có giới hạn rõ ràng kèm select-case lắng nghe ctx.Done()."',
      transcriptSecondParagraph:
        '"Nhờ cơ chế shedding load này mà khi đối tác ngân hàng bảo trì đột xuất, lượng RAM của pod vẫn giữ ổn định ở mức 450MB không bị spike."',
      pitchLabel: 'Pitch: Steady',
      evidenceCode: '#EV-891-2',
      rubricLevel: 'DEMONSTRATED_ABOVE_TARGET',
      linkedSkill: 'Go Concurrency & Channels',
      taxonomyCode: 'LANG_GOLANG_CONCURRENCY_L3',
      confidenceScoreLabel: 'Confidence Score: 0.97 / 1.0',
      sourceTag: 'Production Pattern',
      sourceNote: 'Trình bày xuất sắc cả Worker Pool, Context cancellation và Circuit Breaker.',
      exactQuote:
        '"Áp dụng Worker Pool cố định kết hợp với context.WithTimeout và Circuit Breaker (Gobreaker) để ngắt sớm... lắng nghe ctx.Done()."',
    },
    {
      id: 'T3',
      pillLabel: 'T3: Distributed Locking (Deep Probe)',
      dotVariant: 'amber',
      isDeepProbe: true,
      turnBadge: 'TURN 03',
      topicTitle: 'Khảo sát xử lý tranh chấp dữ liệu (Concurrency & Distributed Locking)',
      timeRange: '09:42 - 13:10',
      depthLabel: 'Depth: Level 3 (Deep Probe)',
      aiStrategyTag: 'Diagnosis & Contradiction Verification',
      aiStrategyDescription:
        'Ứng viên khai báo kinh nghiệm xử lý 100k TPS tại ví điện tử trong CV. AI chủ động thiết lập kịch bản tranh chấp ghi đồng thời (race condition) trên distributed state để xác định ứng viên thực sự làm hay chỉ nắm lý thuyết.',
      aiTimestamp: '09:42',
      aiTtsQuality: 'TTS Synthesis 98%',
      aiPromptText:
        '"Trong CV anh có đề cập đến việc tối ưu hoá luồng nạp rút tiền ví điện tử với hàng ngàn giao dịch đồng thời mỗi giây. Khi hai tiến trình cùng cố gắng ghi nợ trên số dư tài khoản của một người dùng tại cùng một mili-giây trên cụm cluster phân tán, anh dùng cơ chế nào để ngăn chặn double-spending mà vẫn giữ latency p99 dưới 15ms?"',
      candidateInitials: 'HN',
      candidateName: 'Nguyễn Hoàng Nam',
      candidateTimestamp: '10:05',
      candidateConfidencePct: 94.2,
      audioDuration: '01:48',
      transcriptBeforeMark:
        '"Đối với bài toán double-spending trên hệ thống thanh toán, chúng tôi không dùng pessimistic locking thuần túy ở DB vì nó dễ gây bottleneck và connection exhaustion. ',
      transcriptHighlightedMark:
        'Trong hệ thống thanh toán trước đây tại công ty cũ, chúng tôi sử dụng Redis Redlock kết hợp với optimistic locking ở database level bằng version column',
      transcriptAfterMark:
        '. Cụ thể, mỗi user wallet sẽ có một key định danh trên cụm Redis Sentinel với TTL cực ngắn khoảng 200ms để giữ lock phân tán..."',
      transcriptSecondParagraph:
        '"...Nếu acquire lock thành công trong vòng 5ms, transaction ghi DB sẽ thực thi câu lệnh SQL với điều kiện WHERE version = current_version. Nếu version bị trôi do conflict ngầm, hệ thống sẽ retry theo exponential backoff tối đa 3 lần. Cách làm này giảm tải cho PostgreSQL tới 85% và giữ p99 luôn ở mức 11ms."',
      pitchLabel: 'Pitch: Steady',
      evidenceCode: '#EV-891-3',
      rubricLevel: 'DEMONSTRATED_AT_TARGET',
      linkedSkill: 'Redis Distributed Lock & DB Concurrency',
      taxonomyCode: 'ARCH_DISTRIBUTED_CONCURRENCY_L3',
      confidenceScoreLabel: 'Confidence Score: 0.94 / 1.0',
      sourceTag: 'Direct Speech + Metrics',
      sourceNote: 'Nêu rõ cả Redis Redlock, version column, latency p99 & backoff.',
      exactQuote:
        '"Sử dụng Redis Redlock kết hợp với optimistic locking ở database level bằng version column... transaction ghi DB với điều kiện WHERE version = current_version... giảm tải PostgreSQL 85%."',
    },
    {
      id: 'T4',
      pillLabel: 'T4: SQL Index Optimization',
      dotVariant: 'emerald',
      turnBadge: 'TURN 04',
      topicTitle: 'Tối ưu truy vấn sao kê lịch sử giao dịch trên bảng 500 triệu dòng',
      timeRange: '13:15 - 18:20',
      depthLabel: 'Depth: Level 2 (Technical Probe)',
      aiStrategyTag: 'Bottleneck Resolution Probe',
      aiStrategyDescription:
        'Đánh giá khả năng thiết kế Composite Index và Partitioning trên PostgreSQL đối với dữ liệu tài chính quy mô lớn.',
      aiTimestamp: '13:15',
      aiTtsQuality: 'TTS Synthesis 99%',
      aiPromptText:
        '"Với bảng ledger_entries tăng trưởng hơn 10 triệu bản ghi mỗi ngày, làm thế nào anh tối ưu truy vấn lấy lịch sử giao dịch phân trang theo user_id và khoảng thời gian created_at mà không bị chậm khi offset lớn?"',
      candidateInitials: 'HN',
      candidateName: 'Nguyễn Hoàng Nam',
      candidateTimestamp: '13:40',
      candidateConfidencePct: 92.8,
      audioDuration: '01:55',
      transcriptBeforeMark:
        '"Thứ nhất chúng tôi bỏ hoàn toàn OFFSET/LIMIT truyền thống và chuyển sang Keyset Pagination (Cursor-based) dựa trên cặp (created_at, id). ',
      transcriptHighlightedMark:
        'Thứ hai, bảng ledger được Range Partition theo từng tháng kết hợp Covering B-Tree Index trên (user_id, created_at DESC) INCLUDE (amount, status)',
      transcriptAfterMark:
        ' để PostgreSQL thực hiện Index-Only Scan mà không cần đọc ngược vào Heap table."',
      transcriptSecondParagraph:
        '"Nhờ Partition Pruning và Index-Only Scan, thời gian truy vấn trang bất kỳ của khách hàng luôn dưới 8ms."',
      pitchLabel: 'Pitch: Steady',
      evidenceCode: '#EV-891-4',
      rubricLevel: 'DEMONSTRATED_AT_TARGET',
      linkedSkill: 'SQL Query Optimization',
      taxonomyCode: 'DB_POSTGRES_INDEXING_L3',
      confidenceScoreLabel: 'Confidence Score: 0.93 / 1.0',
      sourceTag: 'Direct Speech + Metrics',
      sourceNote: 'Giải quyết triệt để bài toán deep pagination bằng Keyset + Covering Index.',
      exactQuote:
        '"Chuyển sang Keyset Pagination... Range Partition theo từng tháng kết hợp Covering B-Tree Index trên (user_id, created_at DESC) INCLUDE (amount, status)."',
    },
    {
      id: 'T5',
      pillLabel: 'T5: Raft Consensus Failure',
      dotVariant: 'rose',
      turnBadge: 'TURN 05',
      topicTitle: 'Xử lý Split-Brain và Quorum Loss trong thuật toán đồng thuận Raft',
      timeRange: '18:25 - 23:10',
      depthLabel: 'Depth: Level 3 (Edge-case Probe)',
      aiStrategyTag: 'Boundary & Gap Detection',
      aiStrategyDescription:
        'Kiểm tra kiến thức nền tảng về lý thuyết đồng thuận phân tán (Raft/Paxos) khi xảy ra phân mảnh mạng (Network Partition).',
      aiTimestamp: '18:25',
      aiTtsQuality: 'TTS Synthesis 97%',
      aiPromptText:
        '"Giả sử cụm etcd/Consul chạy Raft 5 node bị đứt cáp mạng chia thành 2 phân vùng (2 node và 3 node), trong đó Leader cũ nằm ở nhánh 2 node. Chuyện gì xảy ra khi client vẫn gửi yêu cầu đọc/ghi vào Leader cũ?"',
      candidateInitials: 'HN',
      candidateName: 'Nguyễn Hoàng Nam',
      candidateTimestamp: '18:55',
      candidateConfidencePct: 78.5,
      audioDuration: '01:30',
      transcriptBeforeMark:
        '"Khi bị chia tách như vậy thì nhánh 3 node đủ quorum nên sẽ bầu ra Leader mới. ',
      transcriptHighlightedMark:
        'Ở nhánh 2 node, Leader cũ không nhận được đa số ACK nên các lệnh ghi mới sẽ không thể commit, tuy nhiên mình chưa nắm thật sâu cơ chế ReadIndex hay LeaseRead để chặn hoàn toàn stale read',
      transcriptAfterMark: ' từ Leader cũ trong khoảng thời gian heartbeat chưa hết hạn."',
      transcriptSecondParagraph:
        '"Trong thực tế dự án mình thường ủy thác cấu hình sẵn của thư viện etcd client chứ ít khi tự tinh chỉnh tầng Raft internals."',
      pitchLabel: 'Pitch: Hesitant',
      evidenceCode: '#EV-891-5',
      rubricLevel: 'DEMONSTRATED_BELOW_TARGET',
      linkedSkill: 'Raft Consensus Algorithm',
      taxonomyCode: 'DIST_RAFT_CONSENSUS_L3',
      confidenceScoreLabel: 'Confidence Score: 0.89 / 1.0',
      sourceTag: 'Gap Identified',
      sourceNote: 'Hiểu nguyên lý Quorum cơ bản nhưng thiếu chiều sâu về Linearizable Read / ReadIndex.',
      exactQuote:
        '"Leader cũ không nhận được đa số ACK nên lệnh ghi không thể commit, tuy nhiên chưa nắm thật sâu cơ chế ReadIndex hay LeaseRead để chặn hoàn toàn stale read."',
    },
    {
      id: 'T6',
      pillLabel: 'T6-T8...',
      dotVariant: 'emerald',
      turnBadge: 'TURN 06 - 08',
      topicTitle: 'Vận hành Docker Container Lifecycle & Tổng kết tình huống hệ thống',
      timeRange: '23:15 - 28:15',
      depthLabel: 'Depth: Level 2 (Wrap-up & Verification)',
      aiStrategyTag: 'Consolidation & Graceful Shutdown',
      aiStrategyDescription:
        'Tổng hợp bằng chứng về kỹ năng vận hành Container, xử lý tín hiệu SIGTERM khi rolling update trên Kubernetes.',
      aiTimestamp: '23:15',
      aiTtsQuality: 'TTS Synthesis 99%',
      aiPromptText:
        '"Câu hỏi cuối: Khi thực hiện Rolling Update trên Kubernetes cho dịch vụ thanh toán, anh xử lý tín hiệu SIGTERM trong container Go như thế nào để không làm đứt gãy các giao dịch đang xử lý dở?"',
      candidateInitials: 'HN',
      candidateName: 'Nguyễn Hoàng Nam',
      candidateTimestamp: '23:35',
      candidateConfidencePct: 95.1,
      audioDuration: '01:40',
      transcriptBeforeMark:
        '"Trong hàm main của Go, chúng tôi đăng ký signal.Notify lắng nghe SIGTERM và SIGINT. ',
      transcriptHighlightedMark:
        'Khi nhận SIGTERM, ứng dụng lập tức đánh dấu readiness probe thành false để ngừng nhận tải mới, đồng thời gọi srv.Shutdown(ctx) và WaitGroup.Wait() đợi các worker hoàn tất giao dịch đang chạy',
      transcriptAfterMark:
        ' trong khoảng terminationGracePeriodSeconds là 30 giây trước khi đóng kết nối DB."',
      transcriptSecondParagraph:
        '"Quy trình này đảm bảo Zero-downtime deployment trong mọi đợt release hàng tuần."',
      pitchLabel: 'Pitch: Steady',
      evidenceCode: '#EV-891-6',
      rubricLevel: 'DEMONSTRATED_AT_TARGET',
      linkedSkill: 'Docker Container Lifecycle',
      taxonomyCode: 'DEVOPS_CONTAINER_LIFECYCLE_L2',
      confidenceScoreLabel: 'Confidence Score: 0.95 / 1.0',
      sourceTag: 'Direct Speech',
      sourceNote: 'Nắm vững cơ chế Graceful Shutdown, Readiness Probe và WaitGroup.',
      exactQuote:
        '"Đánh dấu readiness probe thành false để ngừng nhận tải mới, đồng thời gọi srv.Shutdown(ctx) và WaitGroup.Wait() đợi các worker hoàn tất giao dịch đang chạy."',
    },
  ],
  metadata: {
    engineCore: 'Smile-Adaptive-LLM-V2',
    audioPipeline: 'Whisper-Large-v3 + Simli',
    evidenceHash: 'sha256:88a7c29e1fa04',
    evaluationSeed: '#90182471',
  },
};
