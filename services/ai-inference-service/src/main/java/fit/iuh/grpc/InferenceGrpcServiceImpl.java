package fit.iuh.grpc;

import fit.iuh.dto.EvaluationResult;
import fit.iuh.grpc.inference.InferenceRequest;
import fit.iuh.grpc.inference.InferenceResponse;
import fit.iuh.grpc.inference.InferenceServiceGrpc;
import fit.iuh.service.InterviewEvaluationService;
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

    @Override
    public void evaluateResponse(InferenceRequest request, StreamObserver<InferenceResponse> responseObserver) {
        EvaluationResult result = evalService.evaluate(request);
        
        InferenceResponse response = InferenceResponse.newBuilder()
                .setDecision(result.decision() != null ? result.decision() : "NEXT_TOPIC")
                .setReasoning(result.reasoning() != null ? result.reasoning() : "")
                .setGeneratedFollowUpQuestion(result.followUpQuestion() != null ? result.followUpQuestion() : "")
                .setScore(result.score())
                .build();
                
        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }
}
