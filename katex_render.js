#!/usr/bin/env node
/**
 * katex_render.js
 * Reads newline-separated JSON records from stdin, each:
 *   {"math": "<latex>", "display": true|false}
 * Writes one SVG string per line to stdout.
 * Errors produce a fallback <code> element on that line.
 *
 * Usage:
 *   echo '{"math":"x^2","display":false}' | node katex_render.js
 */

// Locate KaTeX — prefer local node_modules, fall back to mermaid-cli's bundled copy
let katex;
try {
  katex = require('./node_modules/katex');
} catch (_) {
  // mermaid-cli bundles katex — find it
  const path = require('path');
  const katexPaths = [
    './node_modules/@mermaid-js/mermaid-cli/node_modules/katex',
    './node_modules/mermaid/node_modules/katex',
  ];
  for (const p of katexPaths) {
    try { katex = require(p); break; } catch (_) {}
  }
}

if (!katex) {
  process.stderr.write('katex not found\n');
  process.exit(1);
}

const readline = require('readline');
const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });

rl.on('line', (line) => {
  line = line.trim();
  if (!line) return;
  let record;
  try {
    record = JSON.parse(line);
  } catch (e) {
    process.stdout.write('<code>JSON parse error</code>\n');
    return;
  }
  try {
    // 'html' for PDF (WeasyPrint handles complex CSS); 'mathml' for EPUB (native reader support)
    const output = (record.mode === 'mathml') ? 'mathml' : 'html';
    const svg = katex.renderToString(record.math, {
      displayMode: !!record.display,
      output: output,
      throwOnError: false,
      strict: 'ignore',
      trust: false,
    });
    // Single line — replace actual newlines inside output
    process.stdout.write(svg.replace(/\n/g, ' ') + '\n');
  } catch (e) {
    // Fallback: emit the raw LaTeX in a styled <code>
    const escaped = record.math.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    process.stdout.write(`<code class="math-fallback">${escaped}</code>\n`);
  }
});
