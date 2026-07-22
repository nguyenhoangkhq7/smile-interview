package fit.iuh.modules.evaluation.service;

import fit.iuh.grpc.inference.FinalReportRequest;
import fit.iuh.grpc.inference.InferenceRequest;
import fit.iuh.modules.evaluation.model.EvaluationResult;
import fit.iuh.modules.evaluation.model.FinalReportResult;

/**
 * Business interface for AI-powered interview evaluation.
 * <p>
 * Decoupling the interface from its implementation allows the gRPC handler to depend on an
 * abstraction, making it straightforward to swap implementations or mock in unit tests.
 */
public interface EvaluationService {

    /**
     * Evaluates a single candidate answer and returns a decision on whether to ask
     * a follow-up question or move to the next topic, optionally with a score.
     *
     * @param request the per-turn gRPC request containing Q&amp;A context, domain, and CV
     * @return evaluation result with decision, score, and optional follow-up question
     */
    EvaluationResult evaluate(InferenceRequest request);

    /**
     * Synthesises the full interview transcript into a holistic hiring recommendation.
     *
     * @param request the final-report gRPC request with all scored turns + resume/JD
     * @return final report with overall score, summary, strengths, weaknesses, and recommendation
     */
    FinalReportResult generateFinalReport(FinalReportRequest request);
}
