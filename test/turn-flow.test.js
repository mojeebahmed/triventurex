/**
 * test/turn-flow.test.js
 * Drives the REAL host turn pipeline (game.js and friends) with the page,
 * board and network replaced by stubs that record what happened.
 *
 * Scripts are loaded in the order index.html lists them, so this keeps working
 * when game.js is split into more files. UI/board/dice/socket scripts are
 * replaced by the stubs below instead of loaded.
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ROOT = path.join(__dirname, '..');
const STUBBED = new Set(['js/host/ui.js', 'js/host/board.js', 'js/shared/dice.js', 'js/shared/socket-client.js']);

/** Local js/ scripts in index.html order, minus the ones replaced by stubs. */
function hostScripts() {
  const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
  return [...html.matchAll(/<script src="(js\/[^"]+)"/g)].map(m => m[1]).filter(f => !STUBBED.has(f));
}

/** A fresh sandboxed host page: 2 players, board 0=start, 1–8 question, 9=finish. */
function makeWorld() {
  const els = {};
  const el = id => (els[id] ??= {
    id, style: {}, textContent: '', innerHTML: '', disabled: false, value: '',
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    addEventListener() {}, querySelector: () => el('_q'), querySelectorAll: () => [],
  });
  const store = {};
  const log = { modals: [], spaces: [], toasts: [], emits: [], ended: 0 };
  const handlers = {};
  const noop = () => {};

  const ctx = {
    console: { log: noop, warn: noop, error: noop },
    setTimeout, clearTimeout,
    document: {
      getElementById: el, querySelector: () => el('_q'), querySelectorAll: () => [],
      addEventListener: noop, createElement: () => el('_new'), head: { appendChild: noop },
      documentElement: { style: { setProperty: noop, removeProperty: noop } },
    },
    localStorage: {
      getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = String(v); },
      removeItem: k => { delete store[k]; },
    },
    alert: noop, confirm: () => true,
  };
  ctx.window = ctx;
  vm.createContext(ctx);

  // Stubs for ui.js / board.js / dice.js / socket-client.js
  Object.assign(ctx, {
    showModal: m => log.modals.push(m), hideModal: noop, showToast: t => log.toasts.push(t),
    showSpaceModal: (space, player, onDone) => log.spaces.push({ space, player, onDone }),
    showGuesserModal: (players, performer, done) => done(),
    showEndScreen: () => { log.ended++; },
    showScreen: noop, renderBoard: noop, renderLegend: noop, updateScoreboard: noop,
    updateGMPlayerSelect: noop, updateBoardTokens: noop, updateCurrentPlayerDisplay: noop,
    highlightSpace: noop, renderHistoryPanel: noop, showScoreFlyout: noop, timerStop: noop,
    renderDie: () => '', populatePathSelector: noop,
    generateBoard: () => Array.from({ length: 10 }, (_, i) =>
      ({ id: i, type: i === 0 ? 'start' : i === 9 ? 'finish' : 'question' })),
    animateDice: async () => {},
    animatePlayerMovement: async (player, spaces, steps) => {
      const max = spaces.length - 1;
      const exact = vm.runInContext('CONFIG', ctx).RULES.exactFinish;
      if (steps > 0 && exact && !player.finished && steps > max - player.position) return true;
      ctx.movePlayer(player, spaces, steps);
      return false;
    },
    TX_NET: new Proxy({ on: (e, f) => { handlers[e] = f; }, isConnected: () => true },
      { get: (t, k) => t[k] ?? ((...a) => log.emits.push([k, ...a])) }),
  });

  for (const f of hostScripts()) {
    vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), ctx, { filename: f });
  }
  ctx._showDiceOverlay = async () => {}; // skip the overlay's real-time fade

  const run = code => vm.runInContext(code, ctx);
  run(`state.players = [createPlayer(0,'Ali','#111','a'), createPlayer(1,'Sara','#222','b')];
       state.board = Array.from({ length: 10 }, (_, i) =>
         ({ id: i, type: i === 0 ? 'start' : i === 9 ? 'finish' : 'question' }));
       state.phase = 'playing'; state.currentPlayerIndex = 0; state.turnPhase = 'roll';
       state.history = []; state.turn = null;`);
  const rollWith = n => { ctx.rollDice = () => n; };
  const network = () => run('_isNetworkGame = true; _networkGameId = "1234"; _initSocketHandlers()');
  return { ctx, run, log, handlers, store, rollWith, network };
}

/** Let fire-and-forget async work (e.g. the roll_result handler) finish. */
const flush = () => new Promise(r => setTimeout(r, 0));

describe('turn pipeline', () => {
  it('offline turn: land, resolve, record history, next player', async () => {
    const w = makeWorld();
    w.rollWith(3); await w.run('handleRoll()');
    assert.equal(w.run('state.turnPhase'), 'resolving');
    assert.equal(w.log.spaces.length, 1);
    w.log.spaces[0].onDone();
    assert.equal(w.run('state.history.length'), 1);
    assert.equal(w.run('state.history[0].roll'), 3);
    assert.equal(w.run('state.players[0].position'), 3);
    assert.equal(w.run('state.currentPlayerIndex'), 1);
    assert.equal(w.run('state.turn'), null);
    assert.equal(w.run('state.turnPhase'), 'roll');
  });

  it('ignores a second roll while a turn is in progress', async () => {
    const w = makeWorld();
    w.rollWith(3); await w.run('handleRoll()'); await w.run('handleRoll()'); await w.run('handleManualRoll(2)');
    assert.equal(w.log.spaces.length, 1);
  });

  it('extra turn: same player rolls again and state is synced', async () => {
    const w = makeWorld(); w.network();
    await w.run('handleManualRoll(2)');
    w.run('state.players[0].hasExtraTurn = true'); w.log.spaces[0].onDone();
    assert.equal(w.run('state.currentPlayerIndex'), 0);
    assert.equal(w.run('state.turnPhase'), 'roll');
    assert.equal(w.run('state.players[0].hasExtraTurn'), false);
    assert.ok(w.log.emits.some(e => e[0] === 'syncState'));
  });

  it('exact-finish overshoot: blocked, recorded, next player, synced', async () => {
    const w = makeWorld(); w.network();
    w.run('state.players[0].position = 8');
    await w.run('handleRoll()'); w.handlers.roll_result({ roll: 5 }); await flush();
    assert.equal(w.run('state.players[0].position'), 8);
    assert.equal(w.run('state.history.length'), 1);
    assert.equal(w.run('state.currentPlayerIndex'), 1);
    assert.equal(w.log.emits.find(e => e[0] === 'emitTurnResult')[2].spaceType, 'blocked');
    assert.ok(w.log.emits.some(e => e[0] === 'syncState'));
  });
});

describe('undo', () => {
  it('during a turn cancels ONLY that turn', async () => {
    const w = makeWorld();
    w.rollWith(2); await w.run('handleRoll()'); w.log.spaces[0].onDone(); // Ali done
    w.rollWith(4); await w.run('handleRoll()');                            // Sara mid-turn
    w.run('undoLastMove()');
    assert.equal(w.run('state.players[1].position'), 0, 'Sara back to start');
    assert.equal(w.run('state.players[0].position'), 2, "Ali's turn not undone");
    assert.equal(w.run('state.history.length'), 1);
    assert.equal(w.run('state.currentPlayerIndex'), 1);
    w.log.spaces[1].onDone(); // stale modal button
    assert.equal(w.run('state.history.length'), 1, 'stale callback ignored');
  });

  it('between turns pops the last turn', async () => {
    const w = makeWorld();
    w.rollWith(2); await w.run('handleRoll()'); w.log.spaces[0].onDone();
    w.run('undoLastMove()');
    assert.equal(w.run('state.history.length'), 0);
    assert.equal(w.run('state.players[0].position'), 0);
    assert.equal(w.run('state.currentPlayerIndex'), 0);
  });
});

describe('skipped turns', () => {
  it('is consumed, recorded and advances; undo re-arms the skip', async () => {
    const w = makeWorld();
    w.run('state.players[0].skipNextTurn = true');
    await w.run('handleRoll()');
    w.log.modals.at(-1).actions[0].callback();
    assert.equal(w.run('state.history[0].spaceType'), 'skip');
    assert.equal(w.run('state.currentPlayerIndex'), 1);
    w.run('undoLastMove()');
    assert.equal(w.run('state.players[0].skipNextTurn'), true);
    assert.equal(w.run('state.currentPlayerIndex'), 0);
  });

  it('a phone roll with skipNextTurn skips instead of moving', async () => {
    const w = makeWorld(); w.network();
    w.run('state.players[0].skipNextTurn = true');
    w.handlers.roll_result({ roll: 4 }); await flush();
    assert.equal(w.run('state.players[0].position'), 0);
    w.log.modals.at(-1).actions[0].callback();
    assert.equal(w.run('state.history[0].spaceType'), 'skip');
  });
});

describe('phone rolls', () => {
  it('start a turn that is undoable; a duplicate is ignored', async () => {
    const w = makeWorld(); w.network();
    w.handlers.roll_result({ roll: 2 }); await flush();
    w.handlers.roll_result({ roll: 6 }); await flush();
    assert.equal(w.log.spaces.length, 1);
    assert.equal(w.run('state.players[0].position'), 2);
    assert.ok(w.run('state.turn.snapshot'));
  });
});

describe('finishing', () => {
  it('by roll records place + bonus; the last finisher ends the game', async () => {
    const w = makeWorld();
    w.run('state.players[1].finished = true; state.players[1].finishOrder = 1; state.finishCount = 1; state.players[0].position = 7');
    w.rollWith(2); await w.run('handleRoll()');
    assert.equal(w.run('state.players[0].finishOrder'), 2);
    assert.equal(w.run('state.players[0].score'), 7, '2nd place bonus');
    w.log.spaces[0].onDone();
    assert.equal(w.run('state.phase'), 'ended');
    await new Promise(r => setTimeout(r, 700)); // end screen is shown after 600ms
    assert.equal(w.log.ended, 1);
  });

  it('via a deed effect during the turn also gets the bonus', async () => {
    const w = makeWorld();
    w.rollWith(2); await w.run('handleRoll()');
    w.run('movePlayer(state.players[0], state.board, 20)'); // deed carries to finish
    w.log.spaces[0].onDone();
    assert.equal(w.run('state.players[0].finishOrder'), 1);
    assert.ok(w.log.toasts.some(t => t.includes('finished 1st')));
  });
});

describe('save / resume', () => {
  it('refresh mid-turn: modal re-opens, turn completes, still undoable', async () => {
    const w = makeWorld();
    w.rollWith(3); await w.run('handleRoll()');
    const save = JSON.parse(w.store.triventurex_save);
    assert.ok(save.turn, 'mid-turn save has state.turn');
    w.run('state.turn = null; state.players = []'); // "page reload"
    w.ctx.__save = save; w.run('_restoreGame(__save)');
    assert.equal(w.log.spaces.length, 2, 'space modal re-opened');
    assert.equal(w.run('state.turnPhase'), 'resolving');
    w.log.spaces[1].onDone();
    assert.equal(w.run('state.history.length'), 1);
    assert.equal(w.run('state.currentPlayerIndex'), 1);
    w.run('undoLastMove()');
    assert.equal(w.run('state.players[0].position'), 0);
  });

  it('an old-format save (pendingTurn) still resumes', async () => {
    const w = makeWorld();
    w.rollWith(3); await w.run('handleRoll()');
    const save = JSON.parse(w.store.triventurex_save);
    save.pendingTurn = { roll: save.turn.roll, posBefore: 0, scoreBefore: 0, snapshot: save.turn.snapshot };
    delete save.turn;
    w.ctx.__save = save; w.run('state.turn = null; _restoreGame(__save)');
    w.log.spaces.at(-1).onDone();
    assert.equal(w.run('state.history.length'), 1);
  });
});

describe('players and GM', () => {
  it('removing the current player mid-turn cancels their turn', async () => {
    const w = makeWorld(); w.network();
    w.run("state.players.push(createPlayer(2,'Omar','#333','c')); state.currentPlayerIndex = 1");
    await w.run('handleRoll()'); w.handlers.roll_result({ roll: 2 }); await flush();
    w.handlers.player_removed({ playerId: 1 });
    assert.equal(w.run('state.turn'), null);
    assert.equal(w.run('state.players[state.currentPlayerIndex].name'), 'Omar');
    w.log.spaces[0].onDone(); // stale
    assert.equal(w.run('state.history.length'), 0);
  });

  it('GM action between turns has its own undoable entry; during a turn it folds in', async () => {
    const w = makeWorld();
    w.run("document.getElementById('gm-player-select').value = '1'; gmAdjustScore(2)");
    assert.equal(w.run('state.history.at(-1).spaceType'), 'gm');
    w.run('undoLastMove()');
    assert.equal(w.run('state.players[1].score'), 0);
    w.rollWith(2); await w.run('handleRoll()');
    w.run('gmAdjustScore(2)');
    w.log.spaces[0].onDone();
    assert.equal(w.run('state.history.length'), 1, 'no separate GM entry mid-turn');
    w.run('undoLastMove()');
    assert.equal(w.run('state.players[1].score'), 0, 'undoing the turn reverts the GM change');
  });

  it('a mid-game joiner is added and synced', async () => {
    const w = makeWorld(); w.network();
    w.handlers.player_joined({ player: { id: 7, name: 'Late', color: '#444', token: 'L' }, players: [] });
    assert.ok(w.run('state.players.some(p => p.id === 7)'));
    assert.ok(w.log.emits.some(e => e[0] === 'syncState'));
  });

  it('network game_started starts a fresh game and syncs it', async () => {
    const w = makeWorld(); w.network();
    w.run("_pendingNetworkSetup = { gameLength: 'short', pathIndex: 'random' }; state.phase = 'setup'");
    w.handlers.game_started({ players: [{ id: 0, name: 'A', color: '#111', token: 'a' },
                                        { id: 3, name: 'B', color: '#222', token: 'b' }] });
    assert.equal(w.run('state.phase'), 'playing');
    assert.equal(w.run('state.board.length'), 10);
    assert.deepEqual(w.run('state.players.map(p => p.id)'), [0, 3]);
    assert.equal(w.run('state.history.length'), 0);
    assert.ok(w.store.triventurex_save, 'saved');
    assert.ok(w.log.emits.some(e => e[0] === 'syncState'));
  });

  it('player_reconnected clears the disconnected marker', async () => {
    const w = makeWorld(); w.network();
    w.handlers.player_disconnected({ playerId: 1 });
    assert.equal(w.run('state.players[1].disconnected'), true);
    w.handlers.player_reconnected({ playerId: 1 });
    assert.equal(w.run('state.players[1].disconnected'), false);
  });
});
