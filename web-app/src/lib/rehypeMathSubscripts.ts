import type { Root, RootContent } from 'hast';

/** Repair Markdown-escaped subscript operators in older reports, only inside math. */
export function rehypeMathSubscripts() {
  return (tree: Root) => {
    function walk(node: Root | RootContent) {
      if (node.type === 'element' && node.tagName === 'code') {
        const classes = node.properties.className;
        if (Array.isArray(classes) && classes.some(name => ['math-inline', 'math-display', 'language-math'].includes(String(name)))) {
          for (const child of node.children) {
            if (child.type === 'text') child.value = child.value.replace(/\\_(?=\{)/g, '_');
          }
        }
      }
      if ('children' in node) node.children.forEach(walk);
    }
    walk(tree);
  };
}
