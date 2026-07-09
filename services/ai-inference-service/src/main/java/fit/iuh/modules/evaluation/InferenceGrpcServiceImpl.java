package fit.iuh.modules.evaluation;

import fit.iuh.grpc.inference.FinalReportRequest;
import fit.iuh.grpc.inference.FinalReportResponse;
import fit.iuh.grpc.inference.InferenceRequest;
import fit.iuh.grpc.inference.InferenceResponse;
import fit.iuh.grpc.inference.InferenceServiceGrpc;
import io.grpc.stub.StreamObserver;
import net.devh.boot.grpc.server.service.GrpcService;
import org.springframework.beans.factory.annotation.Autowired;

@GrpcService
public class InferenceGrpcServiceImpl extends InferenceServiceGrpc.InferenceServiceImplBase {

    private final InterviewEvaluationService evalService;

    @Autowired
    public InferenceGrpcServiceImpl(InterviewEvaluationService evalService) {
        this.evalService = evalService;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Per-turn evaluation
    // ─────────────────────────────────────────────────────────────────────────

    @Override
    public void evaluateResponse(InferenceRequest request,
                                 StreamObserver<InferenceResponse> responseObserver) {
        EvaluationResult result = evalService.evaluate(request);

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
        FinalReportResult result = evalService.generateFinalReport(request);

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
