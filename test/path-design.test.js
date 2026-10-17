/**
 * test/path-design.test.js
 * js/shared/path-design.js — drawing board paths in the ✏️ Boards tab (G20).
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const D = require('../js/shared/path-design.js');

const design = (over = {}) => ({ name: 'Test', start: [5, 1], segments: [['right', 4], ['up', 3]], gridRows: 12, gridCols: 12, ...over });

describe('drawing', () => {
  it('walks the segments from the start', () => {
    const cells = D.designCells([5, 1], [['right', 2], ['up', 1]]);
    assert.deepEqual(cells.map(p => [p.r, p.c]), [[5, 1], [5, 2], [5, 3], [4, 3]]);
    assert.equal(cells[0].dir, null);
    assert.equal(cells[3].dir, 'up');
  });

  it('a click goes in a straight line from the end (the longer axis wins)', () => {
    assert.deepEqual(D.segmentTowards([5, 5], [5, 9]), { dir: 'right', steps: 4 });
    assert.deepEqual(D.segmentTowards([5, 5], [1, 6]), { dir: 'up', steps: 4 });
    assert.equal(D.segmentTowards([5, 5], [5, 5]), null);
  });

  it('a run may not leave the grid or cross the path', () => {
    const d = design();                                   // ends at [2,5]
    assert.equal(D.segmentCells(d, { dir: 'up', steps: 3 }), null, 'row -1');
    assert.equal(D.segmentCells(d, { dir: 'down', steps: 3 }), null, 'back over [5,5]');
    assert.equal(D.segmentCells(d, { dir: 'left', steps: 2 }).length, 2);
  });

  it('a run in the same direction merges into the last segment', () => {
    assert.deepEqual(D.addSegment([['right', 2]], { dir: 'right', steps: 3 }), [['right', 5]]);
    assert.deepEqual(D.addSegment([['right', 2]], { dir: 'up', steps: 1 }), [['right', 2], ['up', 1]]);
  });
});

describe('checks', () => {
  it('parallel runs side by side are crowded; corners are not', () => {
    const zig = D.designCells([5, 0], [['right', 3], ['up', 1], ['left', 3]]);   // two rows touching
    assert.ok(D.designCrowded(zig).size > 0);
    const spaced = D.designCells([5, 0], [['right', 3], ['up', 2], ['left', 3]]);
    assert.equal(D.designCrowded(spaced).size, 0);
  });

  it('errors: no start, too short, no name; warnings: far from the usual size', () => {
    assert.match(D.designCheck(design({ start: null }), 'short').errors.join(), /start/);
    assert.match(D.designCheck(design({ segments: [['right', 2]] }), 'short').errors.join(), /At least 10/);
    assert.match(D.designCheck(design({ name: '  ' }), 'short').errors.join(), /name/);
    const ok = D.designCheck(design({ start: [11, 0], segments: [['right', 10], ['up', 4], ['left', 7]] }), 'short');
    assert.deepEqual(ok.errors, []);
    assert.equal(ok.spaces, 22);
    assert.deepEqual(ok.warnings, []);
    assert.match(D.designCheck(design({ start: [11, 0], segments: [['right', 10], ['up', 4], ['left', 7]] }), 'long').warnings.join(), /about 62/);
  });
});

describe('export', () => {
  it('template keeps only non-default grid sizes', () => {
    assert.deepEqual(D.designTemplate(design()), { name: 'Test', start: [5, 1], segments: [['right', 4], ['up', 3]] });
    assert.equal(D.designTemplate(design({ gridRows: 9 })).gridRows, 9);
  });

  it('the config.js line parses back to the same path', () => {
    const t = D.designTemplate(design({ name: "Ali's board", gridCols: 14 }));
    const text = D.templateText(t);
    assert.match(text, /^\{ name: 'Ali\\'s board', start: \[5,1\], gridCols: 14, segments: \[\['right',4\],\['up',3\]\] \},$/);
    const back = Function(`return ${text.replace(/,$/, '')}`)();
    assert.deepEqual(back, t);
  });
});
