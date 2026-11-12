import { useRef, useState } from 'react';
import { toast } from 'sonner';
import { interviewError } from '@/services/evidenceInterview';
import { studyPlans, type StudyPlanView } from '@/services/studyPlans';

export function useStudyPlan(profileId: string, initialPlan: StudyPlanView) {
  const [data, setData] = useState(initialPlan);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string>();
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const locked = useRef(false);

  async function run<T>(action: () => Promise<T>) {
    if (locked.current) return null;
    locked.current = true;
    setPending(true);
    setError(undefined);
    try {
      return { value: await action() };
    } catch (error) {
      const message = interviewError(error);
      setError(message);
      toast.error(message);
      return null;
    } finally {
      locked.current = false;
      setPending(false);
    }
  }

  async function refresh() {
    setData(await studyPlans.get(profileId));
    setNeedsRefresh(false);
  }

  async function save<T>(action: () => Promise<T>) {
    if (needsRefresh) return null;
    return run(async () => {
      const result = await action();
      try {
        await refresh();
      } catch {
        setNeedsRefresh(true);
        setError('Đã lưu thay đổi. Hãy tải lại dữ liệu kế hoạch để tiếp tục.');
      }
      return result;
    });
  }

  return { data, pending, error, needsRefresh, save, reload: () => run(refresh) };
}
