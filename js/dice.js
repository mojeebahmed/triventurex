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
 * Animate the dice element using CSS dot faces, then settle on the result.
 */
function animateDice(result) {
  return new Promise(resolve => {
    const diceEl  = document.getElementById('dice-display');
    const resultEl = document.getElementById('dice-result');

    diceEl.classList.add('rolling');
    resultEl.textContent = '';

    let flashes = 0;
    const interval = setInterval(() => {
      diceEl.innerHTML = renderDie(Math.floor(Math.random() * 6) + 1);
      flashes++;
      if (flashes >= 10) {
        clearInterval(interval);
        diceEl.innerHTML = renderDie(result);
        diceEl.classList.remove('rolling');
        resultEl.textContent = result;
        resolve();
      }
    }, 60);
  });
}
