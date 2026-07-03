import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PROTO_PATH = path.resolve(__dirname, './proto/inference.proto');

const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true
});

const protoDescriptor = grpc.loadPackageDefinition(packageDefinition);
// The package name in the proto file is ai.inference
const aiInference = protoDescriptor.ai.inference;

const GRPC_SERVER = process.env.INFERENCE_GRPC_SERVER || 'localhost:9090';

// Create a gRPC client
const client = new aiInference.InferenceService(
  GRPC_SERVER,
  grpc.credentials.createInsecure()
);

/**
 * Calls the EvaluateResponse gRPC method on the AI Inference Service.
 * @param {Object} request - The inference request parameters.
 * @param {string} request.sessionId
 * @param {string} request.currentQuestion
 * @param {string} request.candidateAnswer
 * @param {number} request.currentFollowUpCount
 * @param {string} request.targetJobTitle
 * @param {string[]} request.previousQaContext
 * @returns {Promise<Object>} The evaluation response from the AI engine.
 */
export const evaluateCandidateResponse = (request) => {
  return new Promise((resolve, reject) => {
    const grpcRequest = {
      session_id: request.sessionId,
      current_question: request.currentQuestion || "",
      candidate_answer: request.candidateAnswer,
      current_follow_up_count: request.currentFollowUpCount,
      target_job_title: request.targetJobTitle || "IT Engineer",
      previous_qa_context: request.previousQaContext || []
    };

    client.EvaluateResponse(grpcRequest, (error, response) => {
      if (error) {
        console.error('gRPC Error calling EvaluateResponse:', error);
        return reject(error);
      }
      resolve({
        decision: response.decision,
        reasoning: response.reasoning,
        generatedFollowUpQuestion: response.generated_follow_up_question,
        score: response.score,
        evaluation: response.evaluation
      });
    });
  });
};
