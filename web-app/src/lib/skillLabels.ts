import type { SkillGapResult } from '@/services/cvJdMatching';

const labels: Record<string, string> = {
  'html css': 'HTML / CSS', html: 'HTML', css: 'CSS', javascript: 'JavaScript', typescript: 'TypeScript',
  sql: 'SQL', postgresql: 'PostgreSQL', 'postgresql jd': 'PostgreSQL', mysql: 'MySQL', java: 'Java', python: 'Python',
  react: 'React', reactjs: 'React', nodejs: 'Node.js', git: 'Git', docker: 'Docker', 'docker jd': 'Docker',
  'spring boot': 'Spring Boot', 'rest api': 'REST API', 'restful microservices': 'RESTful Microservices',
  'query performance': 'Query Performance', 'integration tests': 'Integration Tests', indexing: 'Indexing',
  mongodb: 'MongoDB', aws: 'AWS', api: 'API', http: 'HTTP', https: 'HTTPS', ai: 'AI',
  cv: 'CV', jd: 'JD', sdk: 'SDK', ui: 'UI', ux: 'UX',
  rest: 'REST', restful: 'RESTful', 'node.js': 'Node.js', 'next.js': 'Next.js', nosql: 'NoSQL',
  ios: 'iOS', github: 'GitHub', graphql: 'GraphQL', grpc: 'gRPC', 'c++': 'C++', 'c#': 'C#', '.net': '.NET',
  'react native': 'React Native', 'machine learning': 'Machine Learning', 'ci cd': 'CI/CD',
  golang: 'Golang', go: 'Go', redis: 'Redis', oop: 'OOP',
  'ai tools usage': 'Sử dụng công cụ AI',
  'ai coding agent expertise': 'Sử dụng AI Coding Agent',
  'english reading': 'Đọc hiểu tiếng Anh',
  'crypto trading': 'Chứng khoán & Crypto',
  'financial investment': 'Đầu tư tài chính',
  'web development basics': 'Phát triển web cơ bản',
  'behavioral competency': 'Kinh nghiệm & Ứng xử (STAR)',
};

function canonicalLabel(value: string) {
  const key = value.toLowerCase().replace(/[-_/\s]+/g, ' ');
  return Object.hasOwn(labels, key) ? labels[key] : undefined;
}

function formatSkillName(name: string) {
  const known = canonicalLabel(name);
  if (known) return known;
  if (/[^\x00-\x7f]/.test(name.replace(/[^\p{L}\p{M}]/gu, ''))) {
    return name.replace(/^\p{Ll}/u, initial => initial.toUpperCase());
  }
  return name.replace(/\.?[a-z0-9]+(?:\.[a-z0-9]+)*[+#]*/gi, word => {
    const knownWord = canonicalLabel(word);
    if (knownWord) return knownWord;
    return word === word.toLowerCase() ? word[0].toUpperCase() + word.slice(1) : word;
  });
}

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
  if (name && name !== value) return formatSkillName(name);
  const known = canonicalLabel(value);
  if (known) return known;
  const restoredName = nameFromEvidence(value, evidenceSpans);
  if (restoredName) return formatSkillName(restoredName);
  if (name && !/[-_]/.test(name)) return formatSkillName(name);
  return value.replace(/[-_]+/g, ' ');
}

export function jdSkillLabel(skill: Pick<SkillGapResult,
  'jd_skill_id' | 'jd_skill_name' | 'jd_evidence_spans' | 'job_tasks'>) {
  const taskSpans = skill.job_tasks?.flatMap(task => task.evidence_spans ?? []) ?? [];
  return skillLabel(skill.jd_skill_id, skill.jd_skill_name, [...new Set([...(skill.jd_evidence_spans ?? []), ...taskSpans])]);
}
