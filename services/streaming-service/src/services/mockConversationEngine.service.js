/**
 * Mock Dynamic Conversation Engine
 * Simulates the RAG and LLM reasoning pipeline to determine the next interview action.
 */

export const determineNextAction = async (candidateText, currentSessionState) => {
  // In a real implementation, this would:
  // 1. Embed the candidateText.
  // 2. Query the vector database for context.
  // 3. Prompt an LLM to evaluate the answer and decide:
  //    - Does it need a follow-up?
  //    - Should we transition to the next topic/question?
  
  // For the mock, we use simple logic based on the session state.
  
  const questionState = currentSessionState.questionState;
  
  let actionType = 'FOLLOW_UP';
  let responseText = '';
  
  // Simple heuristic: If candidate talks a lot, assume they answered well and transition.
  // Otherwise, follow up (until max depth).
  const isDetailedAnswer = candidateText.length > 50;

  if (isDetailedAnswer || questionState.currentFollowUpDepth >= questionState.maxFollowUpDepth) {
    actionType = 'TRANSITION';
    responseText = "That's a very clear explanation. Let's move on to the next topic. Can you tell me about a time you had to optimize a slow database query?";
  } else {
    actionType = 'FOLLOW_UP';
    responseText = "That's an interesting point. Could you dive a bit deeper into the specific technologies you used for that?";
  }

  return {
    actionId: `mock-action-${Date.now()}`,
    actionType,
    text: responseText,
    metadata: {
      inferredQuality: isDetailedAnswer ? 'GOOD' : 'NEEDS_DETAIL',
      suggestedNextState: {
        ...questionState,
        currentFollowUpDepth: actionType === 'FOLLOW_UP' ? questionState.currentFollowUpDepth + 1 : 0,
        baseQuestionIndex: actionType === 'TRANSITION' ? questionState.baseQuestionIndex + 1 : questionState.baseQuestionIndex
      }
    }
  };
};
