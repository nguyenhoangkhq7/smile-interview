/**
 * Mock Avatar Service
 * Simulates the integration with the visual synthesis / talking head module.
 */

export const generateAvatarAction = async (text, emotionHint = 'NEUTRAL') => {
  // In a real implementation, this might contact a Python service 
  // to pre-generate video chunks or return precise lip-sync blendshapes.
  
  // For the mock, we just return a simplified JSON payload that the frontend
  // can use to trigger basic animations or expressions on a 3D model.

  let emotion = emotionHint;
  let gesture = 'NONE';

  // Simple heuristic for mock
  if (text.toLowerCase().includes('great') || text.toLowerCase().includes('excellent')) {
    emotion = 'HAPPY';
    gesture = 'NOD';
  } else if (text.toLowerCase().includes('interesting') || text.toLowerCase().includes('how')) {
    emotion = 'CURIOUS';
    gesture = 'THINKING_NOD';
  }

  return {
    emotion,
    gesture,
    blendshapeDataUrl: null, // Placeholder for real blendshapes
    timestamp: Date.now()
  };
};
