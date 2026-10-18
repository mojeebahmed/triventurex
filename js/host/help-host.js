/**
 * help-host.js — which help topic the host page's ? button opens: the setup
 * tab on screen, the lobby, or the game (the open card, GM controls, game log).
 * The help text itself is in js/shared/help.js.
 */

/** The HELP topic for what is on the host's screen now. */
function hostHelpTopic() {
  const screen = document.querySelector('.screen.active')?.id;
  if (screen === 'setup-screen') {
    const tab = document.querySelector('.setup-tab.active')?.dataset.tab || 'new';
    return HELP[`setup-${tab}`] ? `setup-${tab}` : 'setup-new';
  }
  if (screen === 'lobby-screen') return 'lobby';
  if (screen === 'game-screen') {
    if (!document.getElementById('modal-overlay')?.classList.contains('hidden')) return 'game-cards';
    if (!document.getElementById('gm-controls')?.classList.contains('hidden')) return 'game-gm';
    if (!document.getElementById('history-content')?.classList.contains('hidden')) return 'game-log';
    return 'game';
  }
  return 'how-to-play';
}

function openHostHelp() { openHelp(hostHelpTopic()); }

/**
 * Print a short rules card for this edition with the Rules tab's settings —
 * two copies on an A4 page, to cut out and keep with the game.
 */
function printRulesCard() {
  const R = rulesForNewGame();
  const g = CONFIG.GAME || {};
  const card = rulesCardHtml({
    rules: R, bonus: finishBonusList(R, CONFIG), words: helpWords(CONFIG), iconFn: icon,
    edition: { name: g.editionName, iconHtml: icon(g.editionIcon) },
  });
  const base = location.href.replace(/[^/]*([?#].*)?$/, '');   // images are relative to the game folder
  const win = window.open('', '_blank');
  if (!win) { showToast('Allow pop-ups to print the rules card', 3500); return; }
  win.document.write(`<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><base href="${esc(base)}">
    <title>${esc(g.editionName || 'Triventurex')} — rules card</title>
    <style>
      @page { size: A4; margin: 10mm; }
      * { box-sizing: border-box; }
      body { margin: 0; font: 11pt/1.4 system-ui, -apple-system, 'Segoe UI', sans-serif; color: #222; }
      .rc { height: 136mm; padding: 6mm 8mm; border: 1px dashed #999; border-radius: 4mm; margin-bottom: 4mm; overflow: hidden; }
      .rc-head { display: flex; align-items: center; gap: 4mm; border-bottom: 2px solid ${esc(CONFIG.COLORS?.['--green'] || '#2E7D32')}; padding-bottom: 2mm; }
      .rc-logo img { width: 13mm; height: 13mm; }
      .rc-app { font-size: 8pt; font-weight: 800; letter-spacing: .5px; text-transform: uppercase; color: #777; }
      .rc-title { font-size: 17pt; font-weight: 900; line-height: 1.1; }
      .rc-sub { margin-left: auto; font-weight: 700; color: #777; }
      .rc-goal { margin: 3mm 0; }
      .rc-spaces { border-collapse: collapse; width: 100%; }
      .rc-spaces td { padding: 1.1mm 0; vertical-align: top; }
      .rc-ic { width: 8mm; } .rc-ic img { width: 5.5mm; height: 5.5mm; }
      .rc-extras { margin: 2mm 0; padding-left: 5mm; } .rc-extras li { margin: .5mm 0; }
      .rc-foot { margin: 2mm 0 0; font-size: 9pt; color: #666; }
      .tx-icon svg { width: 5mm; height: 5mm; }
      .hint { font: 10pt system-ui; color: #666; margin: 0 0 4mm; } @media print { .hint { display: none; } }
    </style></head><body>
    <p class="hint">Two copies of the rules card — cut along the dashed lines. (Close this tab when you are done.)</p>
    <div class="rc">${card}</div><div class="rc">${card}</div>
    </body></html>`);
  win.document.close();
  // print once the pictures are in
  const go = () => { win.focus(); win.print(); };
  const imgs = [...win.document.images];
  Promise.all(imgs.map(i => i.complete ? null : new Promise(r => { i.onload = i.onerror = r; }))).then(() => setTimeout(go, 100));
}
