// Initialize persistent VAPID credentials for the backend Docker Compose env file.
import { createECDH } from 'node:crypto';
import { appendFileSync, existsSync, readFileSync } from 'node:fs';

const envFile = new URL('../backend/.env', import.meta.url);
const previous = existsSync(envFile) ? readFileSync(envFile, 'utf8') : '';
const present = ['PUBLIC', 'PRIVATE'].map(side => new RegExp('^WEB_PUSH_' + side + '_KEY=.+$', 'm').test(previous));
if (present.every(Boolean)) {
  console.log('Web Push keys are already configured.');
} else if (present.some(Boolean) || /^WEB_PUSH_(PUBLIC|PRIVATE)_KEY=/m.test(previous)) {
  throw new Error('Incomplete Web Push configuration. Restore the matching key pair in backend/.env.');
} else {
  const pair = createECDH('prime256v1');
  pair.generateKeys();
  appendFileSync(envFile, '\nWEB_PUSH_PUBLIC_KEY=' + pair.getPublicKey().toString('base64url')
    + '\nWEB_PUSH_PRIVATE_KEY=' + pair.getPrivateKey().toString('base64url') + '\n', { mode: 0o600 });
  console.log('Configured Web Push keys in backend/.env.');
}
