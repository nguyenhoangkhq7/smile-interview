const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const path = require('path');

const PROTO_PATH = path.join(__dirname, 'src', 'modules', 'interview', 'proto', 'inference.proto');

const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true
});
const inferenceProto = grpc.loadPackageDefinition(packageDefinition).ai.inference;

// Create insecure (cleartext) client
const client = new inferenceProto.InferenceService('localhost:9091', grpc.credentials.createInsecure());

console.log("Đang gửi request EvaluateResponse tới ai-inference-service (gRPC port 9091)...");

client.EvaluateResponse({
    session_id: "test-session",
    target_job_title: "Java Developer",
    interview_domain: "IT",
    current_question: "What is OOP?",
    candidate_answer: "OOP is Object Oriented Programming.",
    current_follow_up_count: 0,
    max_follow_up_count: 2,
    conversation_thread: []
}, (error, response) => {
    if (error) {
        console.error("❌ Lỗi gRPC:", error);
    } else {
        console.log("✅ KẾT QUẢ TỪ AI:");
        console.log(JSON.stringify(response, null, 2));
    }
});
