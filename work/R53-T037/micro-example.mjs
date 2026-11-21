import assert from 'node:assert/strict';

const text = 'e\u0301bcdef';
const graphemes = Array.from(new Intl.Segmenter().segment(text), (part) => part.segment);
const byGrapheme = graphemes.slice(0, 5).join('');
const byCodePoint = Array.from(text).slice(0, 5).join('');

assert.equal(byGrapheme, 'e\u0301bcde');
assert.equal(byCodePoint, 'e\u0301bcd');
process.stdout.write(JSON.stringify({ input: text, byGrapheme, byCodePoint }) + '\n');
