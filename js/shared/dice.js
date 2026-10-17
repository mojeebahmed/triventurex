/**
 * dice.js
 * Dice rolling and animation.
 */

/**
 * Render a CSS die face (dots on white square). Returns an HTML string.
 * sizeClass: '' | 'die-lg' | 'die-xl'
 */
function renderDie(n, sizeClass = '') {
  const layouts = {
    1: [[50,50]],
    2: [[30,30],[70,70]],
    3: [[30,30],[50,50],[70,70]],
    4: [[30,30],[70,30],[30,70],[70,70]],
    5: [[30,30],[70,30],[50,50],[30,70],[70,70]],
    6: [[30,30],[70,30],[30,50],[70,50],[30,70],[70,70]],
  };
  const dots = layouts[n] || layouts[1];
  const cls  = sizeClass ? `die-face ${sizeClass}` : 'die-face';
  return `<div class="${cls}">${dots.map(([x,y]) =>
    `<span class="die-dot" style="left:${x}%;top:${y}%"></span>`
  ).join('')}</div>`;
}

/**
 * Return a random integer between 1 and 6 inclusive.
 */
function rollDice() {
  return Math.floor(Math.random() * 6) + 1;
}

/**
 * Rolling animation: flash random faces in `el`, then settle on `result`.
 * Resolves when the final face is shown (~600ms by default). Shared by the
 * host's dice display and the phone screens so a roll looks the same everywhere.
 */
function animateDieInto(el, result, { sizeClass = '', flashes = 10, intervalMs = 60 } = {}) {
  return new Promise(resolve => {
    if (!el) { resolve(); return; }
    let shown = 0;
    const interval = setInterval(() => {
      el.innerHTML = renderDie(Math.floor(Math.random() * 6) + 1, sizeClass);
      if (++shown >= flashes) {
        clearInterval(interval);
        el.innerHTML = renderDie(result, sizeClass);
        resolve();
      }
    }, intervalMs);
  });
}

/** Host: animate the sidebar dice display, then show the result number. */
async function animateDice(result) {
  const diceEl   = document.getElementById('dice-display');
  const resultEl = document.getElementById('dice-result');
  diceEl.classList.add('rolling');
  resultEl.textContent = '';
  await animateDieInto(diceEl, result);
  diceEl.classList.remove('rolling');
  resultEl.textContent = result;
}

if (typeof module !== 'undefined') module.exports = { renderDie, rollDice, animateDieInto };
