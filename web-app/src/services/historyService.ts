/**
 * Interview Session History Service
 * 
 * Exposes an asynchronous interface to persist and retrieve interview session records.
 * In a production environment, this service will be replaced by a REST API client.
 * 
 * TODO: Replace localStorage implementation with real REST API calls.
 * Expected REST Endpoints:
 * - GET /api/v1/interviews - Get all interview sessions
 * - GET /api/v1/interviews/{id} - Get detailed session by ID
 * - POST /api/v1/interviews - Create a new interview session
 * - PUT /api/v1/interviews/{id} - Update session details (answers, scores, feedback)
 */

export interface QuestionFeedback {
  question: string;
  answer: string;
  score: number;
  strengths: string;
  improvements: string;
  suggestedAnswer: string;
  topicTag: string;
  isDeepDive: boolean;
}

export interface SessionHistoryItem {
  id: string;
  date: string;
  interviewType: 'Technical' | 'Behavioural' | 'Live Coding' | 'Case Study' | 'System Design';
  roleTitle: string;
  cvFilename: string;
  jdFilename: string;
  overallScore?: number;
  status: 'Completed' | 'In progress' | 'Not started';
  questions: QuestionFeedback[];
  overallFeedback?: string;
  competencyFitScore?: number;
  skillsAnalysis?: {
    analysis: string;
    criticalMissingSkills: string[];
  };
  experienceEvaluation?: string;
  projectEvaluation?: string;
  actionableSuggestions?: string[];
}

const STORAGE_KEY = 'interviewer_interview_history';

// Helper to simulate network latency
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// Pre-populate with realistic mock history if empty
const initializeMockData = () => {
  if (typeof window === 'undefined') return [];
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored) return JSON.parse(stored);

  const defaultHistory: SessionHistoryItem[] = [
    {
      id: 'session-react-1',
      date: '2026-06-28T14:30:00Z',
      interviewType: 'Technical',
      roleTitle: 'React Frontend Engineer',
      cvFilename: 'Nguyen_Van_A_CV.pdf',
      jdFilename: 'JD_Frontend_React.pdf',
      overallScore: 82,
      status: 'Completed',
      overallFeedback: 'Ứng viên có kiến thức tốt về React Lifecycle, hooks và các kỹ thuật tối ưu hóa performance (useMemo, useCallback). Kỹ năng giao tiếp và truyền đạt mạch lạc. Điểm cần cải thiện là giải thích sâu hơn về cơ chế reconciliation của Virtual DOM và cách tối ưu hóa SSR với Next.js.',
      competencyFitScore: 85,
      skillsAnalysis: {
        analysis: 'Ứng viên đáp ứng 80% các yêu cầu kỹ thuật cốt lõi trong JD.',
        criticalMissingSkills: ['Webpack custom config', 'Next.js App Router optimization']
      },
      experienceEvaluation: '3 năm kinh nghiệm làm việc với React. Đã trực tiếp tham gia xây dựng và triển khai các dự án quy mô vừa.',
      projectEvaluation: 'Các dự án cá nhân và doanh nghiệp thể hiện kỹ năng áp dụng thực tiễn tốt, cấu trúc code gọn gàng.',
      actionableSuggestions: [
        'Tìm hiểu sâu hơn về cơ chế Reconciliation và Fiber Architecture của React.',
        'Thực hành cấu hình Webpack từ đầu để hiểu rõ cách optimize bundle size.',
        'Nghiên cứu Next.js App Router (Server Components vs Client Components).'
      ],
      questions: [
        {
          question: 'Bạn hãy giải thích cơ chế hoạt động của useMemo và useCallback trong React. Khi nào chúng ta nên sử dụng chúng?',
          answer: 'useMemo dùng để cache lại kết quả tính toán của một hàm để tránh tính lại ở các lần render sau. useCallback dùng để cache lại chính định nghĩa của một callback function. Chúng ta nên dùng khi xử lý tính toán nặng hoặc truyền callback xuống component con đã được wrap trong React.memo để tránh re-render không cần thiết.',
          score: 90,
          strengths: 'Hiểu rõ sự khác biệt giữa cache giá trị và cache function định nghĩa. Đưa ra được trường hợp sử dụng chính xác liên quan đến React.memo.',
          improvements: 'Có thể đề cập thêm về chi phí (overhead) của việc sử dụng các hook này (so sánh địa chỉ, lưu trữ dependency array), không nên lạm dụng vô điều kiện.',
          suggestedAnswer: 'useMemo giúp lưu giữ giá trị của phép tính phức tạp giữa các lần render. useCallback lưu giữ tham chiếu của function. Chỉ sử dụng khi: 1) Có tính toán đắt đỏ. 2) Truyền prop xuống component con tối ưu bằng React.memo. 3) Function là dependency của hook khác.',
          topicTag: 'React Performance',
          isDeepDive: false
        },
        {
          question: 'Vậy việc lạm dụng useMemo hoặc useCallback có thể dẫn đến những vấn đề gì?',
          answer: 'Nếu lạm dụng quá nhiều thì code sẽ trở nên phức tạp, khó đọc hơn. Đồng thời cũng gây tốn bộ nhớ vì React phải lưu trữ mảng dependency và thực hiện so sánh nông (shallow comparison) ở mỗi lần render, điều này có khi còn làm chậm app hơn.',
          score: 85,
          strengths: 'Đưa ra luận điểm đúng về việc so sánh mảng dependency và overhead bộ nhớ.',
          improvements: 'Nên nhấn mạnh rằng trong hầu hết các trường hợp cơ bản, việc khởi tạo lại function cực kỳ nhanh, việc so sánh dependency đôi khi đắt hơn việc tạo mới.',
          suggestedAnswer: 'Lạm dụng gây ra 2 vấn đề lớn: 1) Overhead về hiệu năng: React phải phân bổ bộ nhớ cho hàm so sánh và mảng dependencies. 2) Độ phức tạp của mã nguồn tăng lên không cần thiết. Hầu hết các component nhỏ không cần tối ưu hóa bằng hook này.',
          topicTag: 'React Performance',
          isDeepDive: true
        },
        {
          question: 'Bạn hiểu thế nào là Virtual DOM trong React và nó giúp cải thiện hiệu năng như thế nào?',
          answer: 'Virtual DOM là một bản sao gọn nhẹ của Real DOM bằng Javascript. Khi state thay đổi, React sẽ tạo ra một Virtual DOM mới, so sánh nó với Virtual DOM cũ thông qua cơ chế diffing, tìm ra những chỗ thay đổi và chỉ update đúng những phần đó lên Real DOM.',
          score: 78,
          strengths: 'Trình bày rõ ràng khái niệm Virtual DOM và quy trình diffing cơ bản.',
          improvements: 'Cần giải thích sâu hơn về giải thuật Diffing (độ phức tạp O(n) nhờ các giả định của React) và cơ chế Reconciliation.',
          suggestedAnswer: 'Virtual DOM là mô hình biểu diễn giao diện dưới dạng object trong bộ nhớ. React cải thiện hiệu năng bằng cách gom nhóm các thay đổi (batching) và tính toán giải thuật so sánh (diffing) để cập nhật Real DOM một cách tối thiểu, tránh thao tác trực tiếp đắt đỏ lên trình duyệt.',
          topicTag: 'React Core',
          isDeepDive: false
        }
      ]
    },
    {
      id: 'session-js-2',
      date: '2026-06-29T09:15:00Z',
      interviewType: 'Technical',
      roleTitle: 'Node.js Backend Developer',
      cvFilename: 'Resume_Backend_NguyenA.pdf',
      jdFilename: 'JD_Backend_Node.pdf',
      overallScore: 65,
      status: 'Completed',
      overallFeedback: 'Ứng viên nắm được các khái niệm cơ bản về Event Loop và Asynchronous trong Node.js. Tuy nhiên kỹ năng thiết kế cơ sở dữ liệu và tối ưu hóa truy vấn SQL còn yếu. Cần luyện tập thêm về các bài toán xử lý đồng thời (concurrency).',
      competencyFitScore: 60,
      skillsAnalysis: {
        analysis: 'Ứng viên có kiến thức nền tảng tốt nhưng thiếu hụt kinh nghiệm thực chiến nâng cao.',
        criticalMissingSkills: ['SQL Query Optimization', 'Redis caching strategies']
      },
      experienceEvaluation: 'Có 1.5 năm kinh nghiệm làm việc thực tế với Express và Node.js.',
      projectEvaluation: 'Dự án ở mức đơn giản (CRUD APIs), chưa đối mặt với các bài toán lượng truy cập lớn hoặc phân tán.',
      actionableSuggestions: [
        'Học kỹ về cách hoạt động của Indexing trong MySQL/PostgreSQL.',
        'Tìm hiểu sâu về các phases trong Event Loop của Node.js (Timers, Poll, Check...).',
        'Thực hành tích hợp Redis cache để giảm tải cho Database.'
      ],
      questions: [
        {
          question: 'Hãy mô tả cơ chế hoạt động của Event Loop trong Node.js.',
          answer: 'Event loop giúp Node.js chạy single-thread nhưng vẫn xử lý được bất đồng bộ. Nó có các hàng đợi chứa các callback. Khi call stack trống, event loop sẽ lấy callback từ hàng đợi ra để thực thi.',
          score: 75,
          strengths: 'Hiểu được bản chất single-thread và vai trò của call stack cũng như callback queue.',
          improvements: 'Nên liệt kê chi tiết các phase (Timers, Pending Callbacks, Idle/Prepare, Poll, Check, Close Callbacks) và microtask queue (process.nextTick, Promise).',
          suggestedAnswer: 'Event Loop gồm nhiều pha chạy tuần tự: 1) Timers: xử lý setTimeout/setInterval. 2) Pending Callbacks: I/O callbacks. 3) Poll: nhận I/O event mới. 4) Check: xử lý setImmediate. 5) Close: đóng socket/handlers. Các microtask queue luôn được ưu tiên thực thi xen kẽ giữa các pha.',
          topicTag: 'Node.js Event Loop',
          isDeepDive: false
        }
      ]
    }
  ];

  localStorage.setItem(STORAGE_KEY, JSON.stringify(defaultHistory));
  return defaultHistory;
};

export const historyService = {
  /**
   * Fetch all past practice sessions
   */
  async getHistory(): Promise<SessionHistoryItem[]> {
    await delay(600); // Simulate network latency
    return initializeMockData();
  },

  /**
   * Fetch details of a specific session by ID
   */
  async getSessionById(id: string): Promise<SessionHistoryItem | null> {
    await delay(400); // Simulate network latency
    const list = initializeMockData();
    const item = list.find((s: SessionHistoryItem) => s.id === id);
    return item || null;
  },

  /**
   * Save or update an interview session in history
   */
  async saveSession(session: SessionHistoryItem): Promise<SessionHistoryItem> {
    await delay(800); // Simulate network latency
    const list = initializeMockData();
    const index = list.findIndex((s: SessionHistoryItem) => s.id === session.id);

    if (index >= 0) {
      list[index] = session;
    } else {
      list.unshift(session); // Add new sessions to the top
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
    return session;
  },

  /**
   * Create an initial blank session
   */
  async createSession(id: string, roleTitle: string, cvFilename: string, jdFilename: string): Promise<SessionHistoryItem> {
    await delay(300);
    const newSession: SessionHistoryItem = {
      id,
      date: new Date().toISOString(),
      interviewType: 'Technical',
      roleTitle,
      cvFilename,
      jdFilename,
      status: 'Not started',
      questions: []
    };

    return this.saveSession(newSession);
  }
};
