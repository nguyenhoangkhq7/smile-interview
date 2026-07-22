package fit.iuh.modules.evaluation.grpc;

import fit.iuh.grpc.inference.FinalReportRequest;
import fit.iuh.grpc.inference.FinalReportResponse;
import fit.iuh.grpc.inference.InferenceRequest;
import fit.iuh.grpc.inference.InferenceResponse;
import fit.iuh.grpc.inference.InferenceServiceGrpc;
import fit.iuh.modules.evaluation.model.EvaluationResult;
import fit.iuh.modules.evaluation.model.FinalReportResult;
import fit.iuh.modules.evaluation.service.EvaluationService;
import io.grpc.stub.StreamObserver;
import lombok.RequiredArgsConstructor;
import net.devh.boot.grpc.server.service.GrpcService;

/**
 * Thin gRPC request handler — the entry point of the ai-inference-service.
 * <p>
 * Responsibilities (and only these):
 * <ul>
 *   <li>Receive inbound gRPC requests.</li>
 *   <li>Delegate all business logic to {@link EvaluationService}.</li>
 *   <li>Map internal domain models to Protobuf response messages.</li>
 *   <li>Complete or error the {@link StreamObserver}.</li>
 * </ul>
 */
@GrpcService
@RequiredArgsConstructor
public class InferenceGrpcServiceImpl extends InferenceServiceGrpc.InferenceServiceImplBase {

    private final EvaluationService evaluationService;

    // ─────────────────────────────────────────────────────────────────────────
    // Per-turn evaluation
    // ─────────────────────────────────────────────────────────────────────────

    @Override
    public void evaluateResponse(InferenceRequest request,
                                 StreamObserver<InferenceResponse> responseObserver) {
        EvaluationResult result = evaluationService.evaluate(request);

        InferenceResponse response = InferenceResponse.newBuilder()
                .setDecision(result.getDecision() != null ? result.getDecision() : "NEXT_TOPIC")
                .setFollowUpQuestion(result.getFollowUpQuestion() != null ? result.getFollowUpQuestion() : "")
                .setReasoning(result.getReasoning() != null ? result.getReasoning() : "")
                .setScore(result.getScore() != null ? result.getScore() : 0)
                .setEvaluation(result.getEvaluation() != null ? result.getEvaluation() : "")
                .setIsFallback(result.isFallback())
                .setExcludedFromScoring(result.isExcludedFromScoring())
                .build();

        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Final synthesis
    // ─────────────────────────────────────────────────────────────────────────

    @Override
    public void generateFinalReport(FinalReportRequest request,
                                    StreamObserver<FinalReportResponse> responseObserver) {
        FinalReportResult result = evaluationService.generateFinalReport(request);

        FinalReportResponse.Builder builder = FinalReportResponse.newBuilder()
                .setOverallScore(result.getOverallScore())
                .setOverallSummary(result.getOverallSummary() != null ? result.getOverallSummary() : "")
                .setHiringRecommendation(
                        result.getHiringRecommendation() != null ? result.getHiringRecommendation() : "No Hire");

        if (result.getStrengths() != null) {
            builder.addAllStrengths(result.getStrengths());
        }
        if (result.getWeaknesses() != null) {
            builder.addAllWeaknesses(result.getWeaknesses());
        }
        if (result.getRecommendations() != null) {
            builder.addAllRecommendations(result.getRecommendations());
        }

        responseObserver.onNext(builder.build());
        responseObserver.onCompleted();
    }
}
