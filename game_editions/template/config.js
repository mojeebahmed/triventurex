/**
 * game_editions/template/config.js
 *
 * Blank edition template for Triventurex.
 * Copy this folder to game_editions/<your-edition-id>/ and fill in the values below.
 * Then add an entry to game_editions/editions.js to make it appear on the setup screen.
 *
 * REQUIRED: Fill in GAME, LANDMARKS (even if empty), and SPACE_INFO.finish.
 * OPTIONAL: BOARD_BACKGROUND, COLORS, SPACE_DISTRIBUTION. Omit any block to use engine defaults.
 */

window.EDITION_CONFIG = {

  // ── Brand identity ──────────────────────────────────────────────────────────
  GAME: {
    engineName:   'Triventurex',      // do not change
    editionName:  'My Edition',       // shown on setup screen and title
    editionIcon:  '🎯',               // emoji shown next to edition name
    subtitle:     'One-line description of your edition',
    gameIdPrefix: 'TX',               // prefix for generated game IDs
    pointsName:   'Points',           // name for score currency (e.g. 'Goals', 'Stars')
  },

  // ── Landmarks ───────────────────────────────────────────────────────────────
  // Named locations players can be sent to by deed cards.
  // `image` path is relative to index.html. Set to null for no image.
  LANDMARKS: [
    // {
    //   name:        'My Place',
    //   image:       'game_editions/<your-edition>/images/landmarks/my-place.jpg',
    //   description: 'A short description shown in the landing modal and the info popup.',
    // },
  ],

  // ── Board background image ──────────────────────────────────────────────────
  // Set image to null to use the CSS gradient fallback.
  BOARD_BACKGROUND: {
    image:          null,   // e.g. 'game_editions/<your-edition>/images/backgrounds/bg.jpg'
    overlayOpacity: 0.65,  // 0 = full image, 1 = fully hidden by gradient
    size:           'cover',
    position:       'center',
    blur:           0,
  },

  // ── Space distribution (optional) ───────────────────────────────────────────
  // Ratios for each non-question type. Questions fill whatever space remains.
  // Can be flat (same for all lengths) or keyed by 'short'/'medium'/'long'.
  // Omit to use the engine defaults from js/shared/config.js.
  // SPACE_DISTRIBUTION: {
  //   short:  { action: 0.10, good_deed: 0.12, bad_deed: 0.12, landmark: 0.06, skip: 0.04 },
  //   medium: { action: 0.10, good_deed: 0.12, bad_deed: 0.12, landmark: 0.06, skip: 0.04 },
  //   long:   { action: 0.10, good_deed: 0.12, bad_deed: 0.12, landmark: 0.06, skip: 0.04 },
  // },

  // ── Space type overrides ────────────────────────────────────────────────────
  // Only specify what differs from the engine defaults in js/shared/config.js SPACE_INFO.
  // Must include `finish` to set the destination name for your edition.
  SPACE_INFO: {
    finish: { icon: '🏁', label: 'Finish' },   // change label to your destination
  },

  // ── Colour scheme ───────────────────────────────────────────────────────────
  // Override any CSS custom property. Omit this block to use engine defaults.
  // See css/styles.css :root for the full list of variables.
  COLORS: {
    '--green':       '#2E7D32',   // primary brand colour (buttons, headings)
    '--green-dark':  '#1B5E20',
    '--green-light': '#E8F5E9',
    '--gold':        '#F9A825',   // accent / active-space glow
    '--gradient-a':  '#1B5E20',   // setup/end screen background gradient
    '--gradient-b':  '#2E7D32',
    '--gradient-c':  '#1565C0',
  },

};
