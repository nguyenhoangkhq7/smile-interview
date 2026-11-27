import { autocompletion, type Completion, type CompletionContext, type CompletionResult } from '@codemirror/autocomplete';
import type { Extension } from '@codemirror/state';
import type { CodingLanguage } from '@/services/evidenceInterview';

const PYTHON_MODULES: Completion[] = [
  { label: 'redis', type: 'namespace', detail: 'Redis in-memory (fakeredis)' },
  { label: 'pymongo', type: 'namespace', detail: 'MongoDB in-memory (mongomock)' },
  { label: 'fastapi', type: 'namespace', detail: 'FastAPI + TestClient' },
  { label: 'pydantic', type: 'namespace', detail: 'BaseModel, Field' },
  { label: 'httpx', type: 'namespace', detail: 'HTTP client / ASGI test' },
  { label: 'sortedcontainers', type: 'namespace', detail: 'SortedList, SortedDict' },
  { label: 'collections', type: 'namespace', detail: 'defaultdict, Counter, deque' },
  { label: 'heapq', type: 'namespace', detail: 'heappush, heappop, nlargest' },
  { label: 'itertools', type: 'namespace', detail: 'groupby, combinations, chain' },
  { label: 'functools', type: 'namespace', detail: 'lru_cache, reduce' },
  { label: 'json', type: 'namespace', detail: 'loads, dumps' },
  { label: 're', type: 'namespace', detail: 'Biểu thức chính quy' },
  { label: 'datetime', type: 'namespace', detail: 'datetime, timedelta, timezone' },
  { label: 'math', type: 'namespace', detail: 'ceil, floor, gcd, inf' },
  { label: 'typing', type: 'namespace', detail: 'Optional, Iterable, Any' },
  { label: 'dataclasses', type: 'namespace', detail: '@dataclass' },
  { label: 'sqlite3', type: 'namespace', detail: 'SQLite trong bộ nhớ' },
  { label: 'asyncio', type: 'namespace', detail: 'Lập trình bất đồng bộ' },
  { label: 'time', type: 'namespace', detail: 'time, monotonic' },
  { label: 'uuid', type: 'namespace', detail: 'uuid4' },
];

const PYTHON_MEMBERS: Completion[] = [
  { label: 'Redis', type: 'class', detail: 'Redis(host="localhost", port=6379, db=0, decode_responses=True)' },
  { label: 'from_url', type: 'method', detail: 'redis.from_url(url, decode_responses=True)' },
  { label: 'set', type: 'method', detail: 'set(key, value, ex=3600)' },
  { label: 'get', type: 'method', detail: 'get(key)' },
  { label: 'delete', type: 'method', detail: 'delete(*keys)' },
  { label: 'exists', type: 'method', detail: 'exists(key)' },
  { label: 'expire', type: 'method', detail: 'expire(key, seconds)' },
  { label: 'ttl', type: 'method', detail: 'ttl(key)' },
  { label: 'incr', type: 'method', detail: 'incr(key, amount=1)' },
  { label: 'hset', type: 'method', detail: 'hset(name, key, value)' },
  { label: 'hget', type: 'method', detail: 'hget(name, key)' },
  { label: 'hgetall', type: 'method', detail: 'hgetall(name)' },
  { label: 'lpush', type: 'method', detail: 'lpush(name, *values)' },
  { label: 'rpush', type: 'method', detail: 'rpush(name, *values)' },
  { label: 'lrange', type: 'method', detail: 'lrange(name, start, end)' },
  { label: 'sadd', type: 'method', detail: 'sadd(name, *values)' },
  { label: 'zadd', type: 'method', detail: 'zadd(name, mapping)' },
  { label: 'pipeline', type: 'method', detail: 'pipeline(transaction=True)' },
  { label: 'MongoClient', type: 'class', detail: 'MongoClient("mongodb://localhost:27017")' },
  { label: 'insert_one', type: 'method', detail: 'insert_one(document)' },
  { label: 'insert_many', type: 'method', detail: 'insert_many(documents)' },
  { label: 'find_one', type: 'method', detail: 'find_one(filter)' },
  { label: 'find', type: 'method', detail: 'find(filter)' },
  { label: 'update_one', type: 'method', detail: 'update_one(filter, update)' },
  { label: 'delete_one', type: 'method', detail: 'delete_one(filter)' },
  { label: 'count_documents', type: 'method', detail: 'count_documents(filter)' },
  { label: 'aggregate', type: 'method', detail: 'aggregate(pipeline)' },
  { label: 'append', type: 'method', detail: 'list.append(item)' },
  { label: 'extend', type: 'method', detail: 'list.extend(iterable)' },
  { label: 'items', type: 'method', detail: 'dict.items()' },
  { label: 'values', type: 'method', detail: 'dict.values()' },
  { label: 'keys', type: 'method', detail: 'dict.keys()' },
  { label: 'setdefault', type: 'method', detail: 'dict.setdefault(key, default)' },
  { label: 'dumps', type: 'function', detail: 'json.dumps(obj, ensure_ascii=False)' },
  { label: 'loads', type: 'function', detail: 'json.loads(text)' },
];

const PYTHON_SYMBOLS: Completion[] = [
  { label: 'def', type: 'keyword', detail: 'Định nghĩa hàm' },
  { label: 'return', type: 'keyword' },
  { label: 'import', type: 'keyword', detail: 'Nhập thư viện' },
  { label: 'from', type: 'keyword', detail: 'from <module> import ...' },
  { label: 'defaultdict', type: 'class', detail: 'collections.defaultdict' },
  { label: 'Counter', type: 'class', detail: 'collections.Counter' },
  { label: 'deque', type: 'class', detail: 'collections.deque' },
  { label: 'BaseModel', type: 'class', detail: 'pydantic.BaseModel' },
  { label: 'FastAPI', type: 'class', detail: 'fastapi.FastAPI' },
  { label: 'TestClient', type: 'class', detail: 'fastapi.testclient.TestClient' },
  { label: 'SortedList', type: 'class', detail: 'sortedcontainers.SortedList' },
  { label: 'enumerate', type: 'function', detail: 'enumerate(iterable, start=0)' },
  { label: 'sorted', type: 'function', detail: 'sorted(iterable, key=...)' },
  { label: 'isinstance', type: 'function', detail: 'isinstance(obj, cls)' },
  { label: 'print', type: 'function', detail: 'In ra stdout khi chạy thử' },
];

const JS_COMPLETIONS: Completion[] = [
  { label: 'function', type: 'keyword' },
  { label: 'async function', type: 'keyword' },
  { label: 'const', type: 'keyword' },
  { label: 'return', type: 'keyword' },
  { label: 'new Map()', type: 'class', detail: 'Bảng băm O(1)' },
  { label: 'new Set()', type: 'class', detail: 'Tập hợp duy nhất' },
  { label: 'Array.from', type: 'method', detail: 'Array.from(iterable)' },
  { label: 'Object.entries', type: 'method', detail: 'Object.entries(obj)' },
  { label: 'JSON.stringify', type: 'method', detail: 'Chuyển sang JSON' },
  { label: 'JSON.parse', type: 'method', detail: 'Đọc chuỗi JSON' },
  { label: 'Promise.all', type: 'method', detail: 'Chạy song song Promises' },
  { label: 'console.log', type: 'method', detail: 'In ra stdout khi chạy thử' },
  { label: 'filter', type: 'method', detail: 'arr.filter(fn)' },
  { label: 'map', type: 'method', detail: 'arr.map(fn)' },
  { label: 'reduce', type: 'method', detail: 'arr.reduce(fn, init)' },
  { label: 'sort', type: 'method', detail: 'arr.sort((a, b) => a - b)' },
];

const SQL_COMPLETIONS: Completion[] = [
  { label: 'SELECT', type: 'keyword' },
  { label: 'DISTINCT', type: 'keyword' },
  { label: 'FROM', type: 'keyword' },
  { label: 'WHERE', type: 'keyword' },
  { label: 'INNER JOIN', type: 'keyword' },
  { label: 'LEFT JOIN', type: 'keyword' },
  { label: 'GROUP BY', type: 'keyword' },
  { label: 'HAVING', type: 'keyword' },
  { label: 'ORDER BY', type: 'keyword' },
  { label: 'LIMIT', type: 'keyword' },
  { label: 'WITH', type: 'keyword', detail: 'CTE (Common Table Expression)' },
  { label: 'COUNT(*)', type: 'function' },
  { label: 'SUM()', type: 'function' },
  { label: 'AVG()', type: 'function' },
  { label: 'COALESCE()', type: 'function', detail: 'Giá trị thay thế khi NULL' },
  { label: 'ROW_NUMBER() OVER ()', type: 'function', detail: 'Window function' },
  { label: 'RANK() OVER ()', type: 'function', detail: 'Window function' },
  { label: 'CASE WHEN', type: 'keyword' },
];

function localIdentifiers(context: CompletionContext): Completion[] {
  const text = context.state.doc.toString();
  const matches = text.match(/\b[A-Za-z_][A-Za-z0-9_]{2,}\b/g) ?? [];
  const unique = new Set(matches);
  return [...unique].slice(0, 60).map(label => ({ label, type: 'variable' }));
}

function pythonSource(context: CompletionContext): CompletionResult | null {
  const line = context.state.doc.lineAt(context.pos);
  const beforeCursor = line.text.slice(0, context.pos - line.from);

  const importMatch = beforeCursor.match(/(?:^|\s)(?:import|from)\s+([A-Za-z_0-9]*)$/);
  if (importMatch) {
    return {
      from: context.pos - importMatch[1].length,
      options: PYTHON_MODULES,
      validFor: /^[A-Za-z_0-9]*$/,
    };
  }

  const memberMatch = beforeCursor.match(/\.([A-Za-z_0-9]*)$/);
  if (memberMatch) {
    return {
      from: context.pos - memberMatch[1].length,
      options: PYTHON_MEMBERS,
      validFor: /^[A-Za-z_0-9]*$/,
    };
  }

  const word = context.matchBefore(/[A-Za-z_][A-Za-z0-9_]*/);
  if (!word || (word.from === word.to && !context.explicit)) return null;
  const seen = new Set<string>();
  const options = [...PYTHON_SYMBOLS, ...PYTHON_MODULES, ...localIdentifiers(context)].filter(item => {
    if (seen.has(item.label)) return false;
    seen.add(item.label);
    return true;
  });
  return { from: word.from, options, validFor: /^[A-Za-z_0-9]*$/ };
}

function genericSource(base: Completion[]) {
  return (context: CompletionContext): CompletionResult | null => {
    const word = context.matchBefore(/[A-Za-z_][A-Za-z0-9_.]*/);
    if (!word || (word.from === word.to && !context.explicit)) return null;
    const seen = new Set<string>();
    const options = [...base, ...localIdentifiers(context)].filter(item => {
      if (seen.has(item.label)) return false;
      seen.add(item.label);
      return true;
    });
    return { from: word.from, options, validFor: /^[A-Za-z_0-9.]*$/ };
  };
}

export function createSandboxAutocomplete(language: CodingLanguage): Extension {
  const source = language === 'python'
    ? pythonSource
    : language === 'javascript'
      ? genericSource(JS_COMPLETIONS)
      : genericSource(SQL_COMPLETIONS);
  return autocompletion({
    override: [source],
    activateOnTyping: true,
    maxRenderedOptions: 10,
  });
}
