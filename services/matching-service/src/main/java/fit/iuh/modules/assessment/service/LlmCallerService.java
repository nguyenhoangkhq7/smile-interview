package fit.iuh.modules.assessment.service;

public interface LlmCallerService {
    String callLlmBlocking(String systemPrompt, String userPrompt);
    String callLlmBlockingWithSemaphore(String systemPrompt, String userPrompt);
}
