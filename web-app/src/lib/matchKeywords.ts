/**
 * matchKeywords.ts
 *
 * Fast, Zero-Token Local Keyword Matcher.
 *
 * Scans raw CV and JD text using a rich technical lexicon and regex word-boundary matching.
 * Replaces external LLM calls to save ~3,000-5,000 tokens per upload and execute in < 5ms.
 */

export interface SkillEntry {
  /** Unique visual tag ID (e.g. "ms1", "msk2") */
  id: string;
  /** The canonical keyword as detected in the JD */
  keyword: string;
  /** "hard" for technical skills, "soft" for interpersonal/process skills */
  category: 'hard' | 'soft';
  /** Optional variants detected in the text */
  variants?: string[];
}

export interface KeywordMatchResult {
  matching_skills: SkillEntry[];
  missing_skills: SkillEntry[];
}

/** Pre-defined Comprehensive Technical & Soft Skill Taxonomy */
const TECH_LEXICON: Array<{ keyword: string; category: 'hard' | 'soft'; synonyms: string[] }> = [
  // Languages
  { keyword: 'Java', category: 'hard', synonyms: ['java 8', 'java 11', 'java 17', 'java 21'] },
  { keyword: 'JavaScript', category: 'hard', synonyms: ['js', 'es6', 'ecmascript'] },
  { keyword: 'TypeScript', category: 'hard', synonyms: ['ts'] },
  { keyword: 'Python', category: 'hard', synonyms: ['python3', 'py'] },
  { keyword: 'C++', category: 'hard', synonyms: ['cpp', 'c/c++'] },
  { keyword: 'C#', category: 'hard', synonyms: ['csharp', '.net'] },
  { keyword: 'Go', category: 'hard', synonyms: ['golang'] },
  { keyword: 'PHP', category: 'hard', synonyms: [] },
  { keyword: 'Rust', category: 'hard', synonyms: [] },
  { keyword: 'SQL', category: 'hard', synonyms: ['pl/sql', 't-sql'] },
  { keyword: 'HTML/CSS', category: 'hard', synonyms: ['html5', 'css3', 'scss', 'sass', 'tailwind'] },

  // Frameworks & Libraries
  { keyword: 'Spring Boot', category: 'hard', synonyms: ['spring', 'spring boot 3', 'spring mvc', 'spring data', 'spring security'] },
  { keyword: 'React', category: 'hard', synonyms: ['reactjs', 'react.js', 'react native'] },
  { keyword: 'Next.js', category: 'hard', synonyms: ['nextjs', 'next'] },
  { keyword: 'Node.js', category: 'hard', synonyms: ['nodejs', 'express', 'express.js', 'nest.js', 'nestjs'] },
  { keyword: 'Angular', category: 'hard', synonyms: ['angularjs', 'angular 2+'] },
  { keyword: 'Vue.js', category: 'hard', synonyms: ['vue', 'vuejs', 'nuxt'] },
  { keyword: 'Django', category: 'hard', synonyms: ['fastapi', 'flask'] },
  { keyword: 'Hibernate', category: 'hard', synonyms: ['jpa', 'mybatis', 'prisma', 'typeorm'] },

  // Databases & Storage
  { keyword: 'PostgreSQL', category: 'hard', synonyms: ['postgres', 'pg'] },
  { keyword: 'MySQL', category: 'hard', synonyms: ['mariadb'] },
  { keyword: 'MongoDB', category: 'hard', synonyms: ['mongo', 'nosql'] },
  { keyword: 'Redis', category: 'hard', synonyms: ['memcached'] },
  { keyword: 'Oracle DB', category: 'hard', synonyms: ['oracle'] },
  { keyword: 'Elasticsearch', category: 'hard', synonyms: ['elastic search', 'elk'] },

  // Cloud, DevOps & Tools
  { keyword: 'Docker', category: 'hard', synonyms: ['containerization', 'containers'] },
  { keyword: 'Kubernetes', category: 'hard', synonyms: ['k8s'] },
  { keyword: 'AWS', category: 'hard', synonyms: ['amazon web services', 's3', 'ec2', 'eks', 'lambda'] },
  { keyword: 'Azure', category: 'hard', synonyms: ['microsoft azure'] },
  { keyword: 'GCP', category: 'hard', synonyms: ['google cloud platform', 'google cloud'] },
  { keyword: 'CI/CD', category: 'hard', synonyms: ['jenkins', 'github actions', 'gitlab ci', 'bitbucket pipelines'] },
  { keyword: 'Git', category: 'hard', synonyms: ['github', 'gitlab', 'version control'] },
  { keyword: 'Kafka', category: 'hard', synonyms: ['rabbitmq', 'event streaming', 'message broker'] },
  { keyword: 'Microservices', category: 'hard', synonyms: ['distributed systems', 'microservice architecture'] },
  { keyword: 'RESTful API', category: 'hard', synonyms: ['rest api', 'restful', 'graphql', 'grpc'] },

  // Testing & Quality
  { keyword: 'Unit Testing', category: 'hard', synonyms: ['junit', 'mockito', 'jest', 'vitest', 'cypress'] },

  // Soft & Process Skills
  { keyword: 'Agile / Scrum', category: 'soft', synonyms: ['agile', 'scrum', 'kanban', 'jira'] },
  { keyword: 'Problem Solving', category: 'soft', synonyms: ['analytical skills', 'critical thinking'] },
  { keyword: 'Communication', category: 'soft', synonyms: ['teamwork', 'collaboration', 'presentation'] },
  { keyword: 'English', category: 'soft', synonyms: ['english communication', 'toeic', 'ielts'] },
  { keyword: 'Leadership', category: 'soft', synonyms: ['mentoring', 'team lead', 'project management'] },
];

function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function containsTerm(text: string, term: string): boolean {
  if (!text || !term) return false;
  const escaped = escapeRegex(term);
  const regex = new RegExp(`(?:^|\\b|_|\\s)${escaped}(?:$|\\b|_|\\s|\\.|,)`, 'i');
  return regex.test(text);
}

/**
 * Extract and match skill keywords locally using Lexicon & Regex (0 LLM Tokens).
 */
export async function matchKeywords(
  rawResumeText: string,
  rawJdText: string
): Promise<KeywordMatchResult> {
  const start = Date.now();
  const cvText = rawResumeText || '';
  const jdText = rawJdText || '';

  const matching_skills: SkillEntry[] = [];
  const missing_skills: SkillEntry[] = [];

  let matchIdx = 1;
  let missIdx = 1;

  for (const entry of TECH_LEXICON) {
    const allTerms = [entry.keyword, ...entry.synonyms];
    const presentInJd = allTerms.some((t) => containsTerm(jdText, t));

    if (presentInJd) {
      const matchedVariant = allTerms.find((t) => containsTerm(cvText, t));

      if (matchedVariant) {
        matching_skills.push({
          id: `ms${matchIdx++}`,
          keyword: entry.keyword,
          category: entry.category,
          variants: matchedVariant.toLowerCase() !== entry.keyword.toLowerCase() ? [matchedVariant] : undefined,
        });
      } else {
        missing_skills.push({
          id: `msk${missIdx++}`,
          keyword: entry.keyword,
          category: entry.category,
        });
      }
    }
  }

  console.log(
    `[matchKeywords Local Lexicon] Done in ${Date.now() - start}ms (0 Tokens). Matching: ${matching_skills.length}, Missing: ${missing_skills.length}`
  );

  return { matching_skills, missing_skills };
}
