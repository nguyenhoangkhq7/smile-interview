const labels: Record<string, string> = {
  'html css': 'HTML / CSS', html: 'HTML', css: 'CSS', javascript: 'JavaScript', typescript: 'TypeScript',
  sql: 'SQL', postgresql: 'PostgreSQL', mysql: 'MySQL', java: 'Java', python: 'Python',
  react: 'React', reactjs: 'React', nodejs: 'Node.js', git: 'Git', docker: 'Docker',
  'spring boot': 'Spring Boot', 'rest api': 'REST API', mongodb: 'MongoDB', aws: 'AWS',
  'react native': 'React Native', 'machine learning': 'Machine Learning', 'ci cd': 'CI/CD',
};

// Reproduce the old ASCII-only slug strictly for looking up names in saved evidence.
function legacySlug(value: string) {
  return value.normalize('NFKC').toLowerCase().replace(/[^a-z0-9+#.\-]+/g, '-')
    .replace(/-{2,}/g, '-').replace(/^-+|-+$/g, '');
}

function nameFromEvidence(id: string, spans: readonly string[]) {
  if (!/^[a-z0-9+#._-]+$/i.test(id) || !/[-_]/.test(id)) return undefined;
  const target = id.toLowerCase().replace(/_/g, '-');
  const candidates = new Map<string, string>();
  for (const span of spans) {
    const tokens = [...span.matchAll(/[\p{L}\p{M}\p{N}+#.]+/gu)].filter(token => /[\p{L}\p{N}]/u.test(token[0]));
    for (let start = 0; start < tokens.length; start++) {
      for (let end = start; end < Math.min(tokens.length, start + 24); end++) {
        const lastWord = tokens[end][0].replace(/\.+$/, '');
        const phrase = span.slice(tokens[start].index!, tokens[end].index! + lastWord.length).trim();
        const prefix = legacySlug(phrase);
        if (!target.startsWith(prefix)) break;
        if (prefix !== target) continue;
        const key = phrase.normalize('NFKC').toLowerCase().replace(/\s+/g, ' ');
        if (!candidates.has(key)) candidates.set(key, phrase.replace(/\s+/g, ' '));
      }
    }
  }
  // Lossy IDs can collide. Only restore a name when the evidence is unambiguous.
  return candidates.size === 1 ? candidates.values().next().value : undefined;
}

export function skillLabel(value: string, displayName?: string | null, evidenceSpans: readonly string[] = []) {
  const name = displayName?.trim();
  if (name && name !== value) return name;
  const known = labels[value.toLowerCase().replace(/[-_]/g, ' ')];
  return known || nameFromEvidence(value, evidenceSpans) || value.replace(/[-_]+/g, ' ');
}
