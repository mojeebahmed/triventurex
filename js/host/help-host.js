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
