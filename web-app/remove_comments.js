const fs = require('fs');
const strip = require('strip-comments');

const files = [
  'src/hooks/useNewInterview.ts',
  'src/hooks/useInterviewSession.ts',
  'src/app/(main)/interview/new/page.tsx',
  'src/app/interview/session/[id]/page.tsx',
  'src/components/features/interview/NewInterview/UploadStep.tsx',
  'src/components/features/interview/NewInterview/MatchingResultPanel.tsx',
  'src/components/features/interview/NewInterview/ActiveSessionsPanel.tsx',
  'src/components/features/interview/SessionPlayer/ChatPanel.tsx',
  'src/components/features/interview/SessionPlayer/ControlsBar.tsx',
  'src/components/features/interview/SessionPlayer/ResultPanel.tsx',
  'src/app/layout.tsx'
];

for (const file of files) {
    if (fs.existsSync(file)) {
        let content = fs.readFileSync(file, 'utf8');
        content = strip(content);
        fs.writeFileSync(file, content, 'utf8');
        console.log('Stripped', file);
    } else {
        console.log('Not found', file);
    }
}
