import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { rehypeMathSubscripts } from '@/lib/rehypeMathSubscripts';
import { cn } from '@/lib/utils';
import styles from './markdown-content.module.css';

export function MarkdownContent({ content, className }: { content: string; className?: string }) {
  return <div className={cn(styles.markdown, className)}>
    <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeMathSubscripts, [rehypeKatex, { trust: false }]]} components={{
      table: ({ children }) => <div className={styles.tableScroll}><table>{children}</table></div>,
      a: ({ children, href }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
    }}>{content}</ReactMarkdown>
  </div>;
}
