import type { JobTask } from '@/services/cvJdMatching';
import { searchText } from './applicationUi';

type PreparationTemplate = {
  signals: readonly RegExp[];
  title: string;
  exercise: string;
};

const templates: readonly PreparationTemplate[] = [
  {
    signals: [
      /\b(?:giai thich|phan tich|explain|analy[sz]e|interpret)(?: [a-z0-9]+){0,4} (?:bien dong (?:cua )?(?:thi truong|gia)|(?:market|price) (?:movements?|fluctuations?|volatility)|changes in (?:market )?prices?)\b/,
    ],
    title: 'Tập giải thích một biến động bằng dữ liệu',
    exercise: 'chọn một biến động bạn đã phân tích. Tập trình bày trong khoảng một phút về số liệu quan sát được, căn cứ cho nhận định và cách bạn kiểm tra lại.',
  },
  {
    signals: [/\b(?:kiem thu|test cases?|(?:unit|integration|e2e) tests?|(?:write|design|create|run) tests?|test(?:ing)? (?:apis?|features?|endpoints?))\b/],
    title: 'Chuẩn bị hai ca kiểm thử',
    exercise: 'chọn một hành vi bạn từng kiểm thử. Viết một ca thông thường và một ca lỗi, mỗi ca có đầu vào và kết quả mong đợi.',
  },
  {
    signals: [
      /\b(?:debug(?:ging)?|troubleshoot(?:ing)?|root cause analysis|chan doan (?:loi|su co)|khac phuc (?:loi|su co)|xu ly su co|phan tich nguyen nhan (?:loi|su co)|diagnos(?:e|ing) (?:[a-z0-9]+ ){0,3}(?:incidents?|issues?|failures?|errors?))\b/,
    ],
    title: 'Tập giải thích cách khoanh vùng sự cố',
    exercise: 'chọn một sự cố bạn đã xử lý. Nêu dấu hiệu đầu tiên, cách khoanh vùng nguyên nhân và cách bạn xác nhận sự cố đã được xử lý.',
  },
  {
    signals: [
      /\b(?:toi uu|optimi[sz](?:e|ing|ation)|tun(?:e|ing))\b/,
      /\b(?:hieu nang|truy van|thoi gian phan hoi|toc do|performance|quer(?:y|ies)|latency|throughput)\b/,
    ],
    title: 'Chuẩn bị số đo trước và sau khi tối ưu',
    exercise: 'chọn một lần tối ưu bạn từng thực hiện. Chuẩn bị số đo trước và sau thay đổi, rồi giải thích điều kiện đo để hai kết quả có thể so sánh.',
  },
  {
    signals: [
      /\b(?:thiet ke|design(?:ing)?|architect(?:ing)?)\b/,
      /\b(?:he thong|kien truc|co che|giao dien|chi muc|co so du lieu|api|luong|schema|interfaces?|indexes?|indices|architecture|systems?|workflows?|databases?|solutions?|services?)\b/,
    ],
    title: 'Tập giải thích một quyết định thiết kế',
    exercise: 'chọn một quyết định thiết kế bạn từng đưa ra. Phác hai phương án đã cân nhắc và nêu ràng buộc nào dẫn tới lựa chọn cuối cùng.',
  },
  {
    signals: [/\b(?:(?:lap|viet|soan|trinh bay) (?:cac )?bao cao|(?:prepare|write|draft|produce|present) (?:[a-z0-9]+ ){0,3}reports?)\b/],
    title: 'Chuẩn bị phần tóm tắt một báo cáo',
    exercise: 'chọn một báo cáo bạn từng làm. Tóm tắt câu hỏi báo cáo cần trả lời, kết luận chính và số liệu hỗ trợ kết luận đó.',
  },
  {
    signals: [/\b(?:phan tich (?:[a-z0-9]+ ){0,2}(?:du lieu|so lieu)|(?:data|statistical) analysis|(?:analy[sz]e|explore|interpret) (?:[a-z0-9]+ ){0,3}(?:data|metrics)|interpret (?:the )?results)\b/],
    title: 'Tập trình bày một lần phân tích dữ liệu',
    exercise: 'chọn một lần phân tích bạn từng làm. Chuẩn bị câu hỏi bạn cần trả lời, dữ liệu đã dùng và một cách bạn kiểm tra kết luận.',
  },
  {
    signals: [
      /\b(?:xay dung|phat trien|trien khai|tich hop|implement|build|develop|deploy|integrate)\b/,
      /\b(?:dich vu|tinh nang|luong xu ly|ung dung|giao dien|apis?|endpoints?|features?|services?|workflows?|applications?|interfaces?)\b/,
    ],
    title: 'Chuẩn bị một luồng xử lý và cách kiểm tra',
    exercise: 'chọn một phần triển khai bạn phụ trách. Phác luồng xử lý chính, một tình huống cần xử lý riêng và cách bạn kiểm tra kết quả.',
  },
];

function normalizeTaskText(text: string) {
  return searchText(text).replace(/[^a-z0-9]+/g, ' ').trim();
}

export function getTaskPreparation(tasks: readonly JobTask[]) {
  const orderedTasks = [...tasks].sort((a, b) =>
    Number(b.requirement_kind === 'REQUIRED') - Number(a.requirement_kind === 'REQUIRED'));

  for (const task of orderedTasks) {
    const description = task.description?.trim();
    if (!description) continue;

    const taskText = normalizeTaskText(description);
    const excerpts = (task.evidence_spans ?? []).map(quote => ({ quote: quote.trim(), text: normalizeTaskText(quote) }));

    for (const template of templates) {
      if (!template.signals.every(signal => signal.test(taskText))) continue;
      // The original JD excerpt must support the same action as the extracted task.
      const source = excerpts.find(excerpt => template.signals.every(signal => signal.test(excerpt.text)));
      if (source) {
        return { title: template.title, exercise: template.exercise, taskDescription: description, jdQuote: source.quote };
      }
    }
  }

  return undefined;
}
