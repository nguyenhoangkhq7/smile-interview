/**
 * Technical Interview Question Service
 * 
 * Manages the question database and state machine for selecting the next question.
 * Heuristic rules:
 * - Evaluating user answers based on character length (< 45 chars is "shallow") and keyword inclusion.
 * - If shallow or missing keywords, trigger a deep-dive question (max 2 per topic).
 * - Otherwise, transition to a new primary technical topic.
 * - Concludes after 5 questions or when all topics are exhausted.
 */

export interface MockQuestion {
  id: string;
  topic: string;
  questionText: string;
  keyKeywords: string[];
  suggestedAnswer: string;
  followUps: Omit<MockQuestion, 'followUps'>[];
}

const QUESTION_BANK: MockQuestion[] = [
  {
    id: 'q-react-perf',
    topic: 'React Performance',
    questionText: 'Bạn hãy giải thích cơ chế hoạt động của useMemo và useCallback trong React. Khi nào chúng ta thực sự cần sử dụng chúng?',
    keyKeywords: ['cache', 'render', 're-render', 'tính toán', 'dependency', 'tham chiếu', 'reference', 'memo'],
    suggestedAnswer: 'useMemo giúp lưu giữ giá trị của phép tính phức tạp giữa các lần render. useCallback lưu giữ tham chiếu của function. Chỉ sử dụng khi: 1) Có tính toán đắt đỏ. 2) Truyền prop xuống component con tối ưu bằng React.memo. 3) Function là dependency của hook khác.',
    followUps: [
      {
        id: 'q-react-perf-deep1',
        topic: 'React Performance',
        questionText: 'Nếu lạm dụng useMemo hoặc useCallback vô điều kiện thì sẽ gây ra những vấn đề hay tác hại gì cho ứng dụng?',
        keyKeywords: ['overhead', 'bộ nhớ', 'memory', 'so sánh', 'đọc', 'phức tạp', 'chậm', 'dependencies'],
        suggestedAnswer: 'Lạm dụng gây ra 2 vấn đề lớn: 1) Overhead về hiệu năng: React phải phân bổ bộ nhớ cho hàm so sánh và mảng dependencies. 2) Độ phức tạp của mã nguồn tăng lên không cần thiết. Hầu hết các component nhỏ không cần tối ưu hóa bằng hook này.'
      },
      {
        id: 'q-react-perf-deep2',
        topic: 'React Performance',
        questionText: 'Làm thế nào để đo lường hiệu năng render của một component React trong thực tế để biết nó có thực sự bị chậm hay không?',
        keyKeywords: ['profiler', 'chrome devtools', 'lighthouse', 'render time', 'performance tab', 'console.time', 'react developer tools'],
        suggestedAnswer: 'Chúng ta sử dụng công cụ React DevTools Profiler để ghi lại thời gian render của các component, hoặc sử dụng Component <Profiler> API trong code để đo lường chính xác các chỉ số mount và update.'
      }
    ]
  },
  {
    id: 'q-js-loop',
    topic: 'JS Event Loop',
    questionText: 'Cơ chế Event Loop trong Javascript hoạt động như thế nào? Sự khác nhau giữa Microtask queue và Macrotask queue là gì?',
    keyKeywords: ['event loop', 'callback', 'call stack', 'microtask', 'macrotask', 'queue', 'bất đồng bộ', 'promise', 'settimeout', 'async'],
    suggestedAnswer: 'Event Loop giám sát Call Stack và Callback Queue. Khi Call Stack trống, nó đẩy các task từ Queue vào. Microtask (Promise, process.nextTick) có độ ưu tiên cao hơn và được chạy hết trước khi Event Loop chuyển sang Macrotask tiếp theo (setTimeout, setInterval).',
    followUps: [
      {
        id: 'q-js-loop-deep1',
        topic: 'JS Event Loop',
        questionText: 'Bạn đoán xem đoạn code sử dụng Promise.resolve().then() và setTimeout(() => {}, 0) thì cái nào sẽ chạy trước và tại sao?',
        keyKeywords: ['promise', 'then', 'microtask', 'trước', 'nhanh hơn', 'ưu tiên', 'settimeout', 'macrotask'],
        suggestedAnswer: 'Promise.resolve().then() chạy trước vì callback của nó được xếp vào Microtask queue, vốn có độ ưu tiên cao hơn và được giải phóng toàn bộ trước khi Macrotask queue (chứa setTimeout) được xử lý.'
      }
    ]
  },
  {
    id: 'q-db-design',
    topic: 'Database Design',
    questionText: 'Làm thế nào để tối ưu hóa hiệu năng truy vấn cho một bảng cơ sở dữ liệu có hàng triệu bản ghi? Khi nào bạn nên tạo index?',
    keyKeywords: ['index', 'truy vấn', 'query', 'tối ưu', 'optimize', 'bản ghi', 'chỉ mục', 'explain', 'where', 'join'],
    suggestedAnswer: 'Ta tối ưu bằng cách tạo Index (chỉ mục) trên các cột hay tìm kiếm ở điều kiện WHERE, JOIN. Sử dụng lệnh EXPLAIN để phân tích execution plan. Tránh SELECT * và tối ưu hóa các câu lệnh subquery thành JOIN.',
    followUps: [
      {
        id: 'q-db-design-deep1',
        topic: 'Database Design',
        questionText: 'Việc tạo quá nhiều Index trên một bảng có thể gây ra những bất lợi gì?',
        keyKeywords: ['insert', 'update', 'delete', 'ghi', 'write', 'dung lượng', 'bộ nhớ', 'chậm', 'storage'],
        suggestedAnswer: 'Tạo quá nhiều index làm chậm các thao tác ghi (INSERT, UPDATE, DELETE) vì hệ quản trị CSDL phải cập nhật lại cây chỉ mục tương ứng, đồng thời tốn thêm dung lượng lưu trữ đĩa cứng.'
      }
    ]
  }
];

// In-memory state tracking per session
interface ActiveSessionState {
  currentTopicIndex: number;
  currentDeepDiveIndex: number;
  totalQuestionsAsked: number;
  askedQuestionIds: string[];
}

const sessionStates: Record<string, ActiveSessionState> = {};

const getOrInitState = (sessionId: string): ActiveSessionState => {
  if (!sessionStates[sessionId]) {
    sessionStates[sessionId] = {
      currentTopicIndex: 0,
      currentDeepDiveIndex: 0,
      totalQuestionsAsked: 0,
      askedQuestionIds: []
    };
  }
  return sessionStates[sessionId];
};

export const questionService = {
  /**
   * Evaluates the candidate's answer and returns the next question details.
   * If currentAnswerText is empty, returns the first question.
   */
  async getNextQuestion(
    sessionId: string,
    currentAnswerText?: string
  ): Promise<{
    questionText: string;
    isFinished: boolean;
    isDeepDive: boolean;
    topicTag: string;
    suggestedAnswer: string;
    score: number;
    strengths: string;
    improvements: string;
  }> {
    const state = getOrInitState(sessionId);
    const maxTotalQuestions = 5;

    // Check if we already reached the max limit
    if (state.totalQuestionsAsked >= maxTotalQuestions) {
      return {
        questionText: '',
        isFinished: true,
        isDeepDive: false,
        topicTag: '',
        suggestedAnswer: '',
        score: 0,
        strengths: '',
        improvements: ''
      };
    }

    // First question initialization
    if (!currentAnswerText || state.totalQuestionsAsked === 0) {
      const topic = QUESTION_BANK[0];
      state.totalQuestionsAsked = 1;
      state.askedQuestionIds.push(topic.id);
      
      return {
        questionText: topic.questionText,
        isFinished: false,
        isDeepDive: false,
        topicTag: topic.topic,
        suggestedAnswer: topic.suggestedAnswer,
        score: 0,
        strengths: '',
        improvements: ''
      };
    }

    // Evaluate current answer
    const currentTopic = QUESTION_BANK[state.currentTopicIndex];
    let currentQuestion: Omit<MockQuestion, 'followUps'> = currentTopic;
    
    // Determine which question the candidate just answered
    const isDeepDiveNow = state.currentDeepDiveIndex > 0;
    if (isDeepDiveNow) {
      currentQuestion = currentTopic.followUps[state.currentDeepDiveIndex - 1];
    }

    // Evaluation logic (Heuristic: length and keyword check)
    const cleanedAnswer = currentAnswerText.toLowerCase();
    const matchedKeywords = currentQuestion.keyKeywords.filter(k => cleanedAnswer.includes(k));
    const isShallow = currentAnswerText.length < 45;
    const missingKeywords = matchedKeywords.length < 2;

    // Generate score based on match rate
    let score = 85;
    let strengths = 'Trình bày đúng trọng tâm vấn đề, trả lời mạch lạc.';
    let improvements = 'Có thể mở rộng thêm về các case thực tế hoặc ví dụ cụ thể.';

    if (isShallow) {
      score = 55;
      strengths = 'Nhận diện được chủ đề câu hỏi.';
      improvements = 'Câu trả lời quá ngắn, cần giải thích sâu hơn và đưa ra lập luận thuyết phục.';
    } else if (missingKeywords) {
      score = 70;
      strengths = 'Câu trả lời có độ dài tốt.';
      improvements = `Thiếu một số từ khóa chuyên môn cốt lõi như: ${currentQuestion.keyKeywords.slice(0, 3).join(', ')}.`;
    } else {
      score = Math.floor(85 + Math.random() * 11); // Random 85-95
    }

    // Decide what is next
    let nextQuestionText = '';
    let nextTopicTag = '';
    let nextSuggested = '';
    let isNextDeepDive = false;
    let shouldAdvanceTopic = false;

    // Deep dive heuristic decision
    if ((isShallow || missingKeywords) && state.currentDeepDiveIndex < currentTopic.followUps.length) {
      // Trigger deep dive
      state.currentDeepDiveIndex += 1;
      const nextDeepDiveQ = currentTopic.followUps[state.currentDeepDiveIndex - 1];
      nextQuestionText = nextDeepDiveQ.questionText;
      nextTopicTag = nextDeepDiveQ.topic;
      nextSuggested = nextDeepDiveQ.suggestedAnswer;
      isNextDeepDive = true;
    } else {
      // Advance to next primary topic
      shouldAdvanceTopic = true;
    }

    if (shouldAdvanceTopic) {
      state.currentTopicIndex += 1;
      state.currentDeepDiveIndex = 0;

      if (state.currentTopicIndex < QUESTION_BANK.length) {
        const nextTopicQ = QUESTION_BANK[state.currentTopicIndex];
        nextQuestionText = nextTopicQ.questionText;
        nextTopicTag = nextTopicQ.topic;
        nextSuggested = nextTopicQ.suggestedAnswer;
        isNextDeepDive = false;
      } else {
        // Exited question bank topics
        return {
          questionText: '',
          isFinished: true,
          isDeepDive: false,
          topicTag: '',
          suggestedAnswer: '',
          score,
          strengths,
          improvements
        };
      }
    }

    // Increment count
    state.totalQuestionsAsked += 1;
    
    // If it exceeds the interview limit, mark as finished
    if (state.totalQuestionsAsked > maxTotalQuestions) {
      return {
        questionText: '',
        isFinished: true,
        isDeepDive: false,
        topicTag: '',
        suggestedAnswer: '',
        score,
        strengths,
        improvements
      };
    }

    return {
      questionText: nextQuestionText,
      isFinished: false,
      isDeepDive: isNextDeepDive,
      topicTag: nextTopicTag,
      suggestedAnswer: nextSuggested,
      score,
      strengths,
      improvements
    };
  },

  /**
   * Resets session state tracking (useful when restarting a mock session)
   */
  async resetSession(sessionId: string): Promise<void> {
    delete sessionStates[sessionId];
  }
};
