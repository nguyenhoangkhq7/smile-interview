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
const aiInference = protoDescriptor.ai.inference;

const GRPC_SERVER = process.env.INFERENCE_GRPC_SERVER || 'localhost:9091';

// Create a gRPC client
const client = new aiInference.InferenceService(
  GRPC_SERVER,
  grpc.credentials.createInsecure()
);

/**
 * Calls the EvaluateResponse gRPC method on the AI Inference Service.
 * @param {Object} request
 * @param {string} request.sessionId
 * @param {string} request.targetJobTitle
 * @param {string} request.interviewDomain        - e.g. "IT", "Marketing", "Finance"
 * @param {string} request.currentQuestion
 * @param {string} request.candidateAnswer
 * @param {number} request.currentFollowUpCount
 * @param {number} request.maxFollowUpCount
 * @param {Array<{question: string, answer: string, was_follow_up: boolean}>} request.conversationThread
 * @returns {Promise<Object>} Evaluation response from the AI engine
 */
export const evaluateCandidateResponse = (request) => {
  return new Promise((resolve, reject) => {
    const grpcRequest = {
      session_id: request.sessionId,
      target_job_title: request.targetJobTitle || 'IT Engineer',
      interview_domain: request.interviewDomain || 'IT',
      current_question: request.currentQuestion || '',
      candidate_answer: request.candidateAnswer,
      current_follow_up_count: request.currentFollowUpCount || 0,
      max_follow_up_count: request.maxFollowUpCount || 3,
      conversation_thread: (request.conversationThread || []).map(ctx => ({
        question: ctx.question || '',
        answer: ctx.answer || '',
        was_follow_up: ctx.wasFollowUp || false
      })),
      fast_mode: request.fastMode || false,
      cv_text: request.cvText || '',
      good_answer_signals: request.goodAnswerSignals || []
    };

    client.EvaluateResponse(grpcRequest, (error, response) => {
      if (error) {
        console.error('[engine.client] gRPC Error calling EvaluateResponse:', error);
        return reject(error);
      }
      resolve({
        decision: response.decision,
        followUpQuestion: response.follow_up_question,
        reasoning: response.reasoning,
        score: response.score,
        evaluation: response.evaluation,
        isFallback: response.is_fallback,
        excludedFromScoring: response.excluded_from_scoring
      });
    });
  });
};

/**
 * Calls the GenerateFinalReport gRPC method on the AI Inference Service.
 * Should be triggered after the interview ends (INTERVIEW_END event).
 * Not bound by real-time latency — uses a longer timeout model.
 *
 * @param {Object} request
 * @param {string} request.sessionId
 * @param {string} request.targetJobTitle
 * @param {Array<{question, answer, score, evaluation, wasFollowUp}>} request.turns
 * @param {string} [request.resumeText]  - Full resume markdown text (optional)
 * @param {string} [request.jdText]      - Full JD markdown text (optional)
 * @returns {Promise<Object>} Final report response
 */
export const generateFinalReport = (request) => {
  return new Promise((resolve, reject) => {
    const grpcRequest = {
      session_id: request.sessionId,
      target_job_title: request.targetJobTitle || 'IT Engineer',
      turns: (request.turns || []).map(t => ({
        question: t.question || '',
        answer: t.answer || '',
        score: t.score || 0,
        evaluation: t.evaluation || '',
        was_follow_up: t.wasFollowUp || false
      })),
      resume_text: request.resumeText || '',
      jd_text: request.jdText || ''
    };

    client.GenerateFinalReport(grpcRequest, (error, response) => {
      if (error) {
        console.error('[engine.client] gRPC Error calling GenerateFinalReport:', error);
        return reject(error);
      }
      resolve({
        overallScore: response.overall_score,
        overallSummary: response.overall_summary,
        strengths: response.strengths || [],
        weaknesses: response.weaknesses || [],
        recommendations: response.recommendations || [],
        hiringRecommendation: response.hiring_recommendation
      });
    });
  });
};
