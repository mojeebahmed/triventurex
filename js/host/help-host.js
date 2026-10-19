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
 * one A4 page (print 2 pages per sheet for a smaller card).
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
      body { font-size: 15pt; }
      .rc { width: 186mm; margin: 0 auto; padding: 10mm 11mm; border: 1.5px solid #bbb; border-radius: 5mm; }   /* A4 190 mm inside the margins */
      .rc-head { display: flex; align-items: center; gap: 4mm; border-bottom: 2px solid ${esc(CONFIG.COLORS?.['--green'] || '#2E7D32')}; padding-bottom: 2mm; }
      .rc-logo img { width: 18mm; height: 18mm; }
      .rc-app { font-size: 8pt; font-weight: 800; letter-spacing: .5px; text-transform: uppercase; color: #777; }
      .rc-title { font-size: 28pt; font-weight: 900; line-height: 1.1; }
      .rc-sub { margin-left: auto; font-weight: 700; color: #777; }
      .rc-goal { margin: 5mm 0; }
      .rc-spaces { border-collapse: collapse; width: 100%; }
      .rc-spaces td { padding: 3mm 0; vertical-align: top; }
      .rc-ic { width: 11mm; } .rc-ic img { width: 7.5mm; height: 7.5mm; }
      .rc-extras { margin: 4mm 0; padding-left: 6mm; } .rc-extras li { margin: 1.5mm 0; }
      .rc-foot { margin: 6mm 0 0; font-size: 11pt; color: #666; }
      .tx-icon svg { width: 5mm; height: 5mm; }
      .hint { font: 10pt system-ui; color: #666; margin: 0 0 4mm; } @media print { .hint { display: none; } }
    </style></head><body>
    <p class="hint">The rules card fills one A4 page — for a smaller card, print 2 pages per sheet. (Close this tab when you are done.)</p>
    <div class="rc">${card}</div>
    </body></html>`);
  win.document.close();
  // print once the pictures are in
  const go = () => { win.focus(); win.print(); };
  const imgs = [...win.document.images];
  Promise.all(imgs.map(i => i.complete ? null : new Promise(r => { i.onload = i.onerror = r; }))).then(() => setTimeout(go, 100));
}
