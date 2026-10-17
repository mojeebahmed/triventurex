/**
 * edition.js
 * An edition's config.js on top of the engine CONFIG, and its colours as CSS
 * variables. Shared by the host page (edition-loader.js) and the TV display.
 */

/** Merge an edition's config (window.EDITION_CONFIG) into the engine `config`. */
function mergeEditionConfig(config, T) {
  if (!T) return;
  if (T.GAME)                Object.assign(config.GAME,             T.GAME);
  if (T.COLORS)              Object.assign(config.COLORS,           T.COLORS);
  if (T.LANDMARKS)           config.LANDMARKS = T.LANDMARKS;
  if (T.BOARD_BACKGROUND)    Object.assign(config.BOARD_BACKGROUND, T.BOARD_BACKGROUND);
  if (T.SPACE_DISTRIBUTION)  config.EDITION_SPACE_DISTRIBUTION = T.SPACE_DISTRIBUTION;
  if (T.SCORE_VALUES)        Object.assign(config.SCORE_VALUES,     T.SCORE_VALUES);
  if (T.FINISH_BONUS)        config.FINISH_BONUS = [...T.FINISH_BONUS];
  if (T.AWARDS) {
    for (const [id, overrides] of Object.entries(T.AWARDS)) {
      config.AWARDS[id] = { ...config.AWARDS[id], ...overrides };
    }
  }
  if (T.SPACE_INFO) {
    for (const [type, overrides] of Object.entries(T.SPACE_INFO)) {
      if (config.SPACE_INFO[type]) Object.assign(config.SPACE_INFO[type], overrides);
      else config.SPACE_INFO[type] = overrides;
    }
  }
}

/**
 * Edition colours → CSS variables on the page: COLORS entries as they are,
 * and each space type's colour as --c-<type> (board spaces + legend use them).
 */
function applyEditionColors(config) {
  const root = document.documentElement;
  for (const [prop, value] of Object.entries(config.COLORS || {})) {
    root.style.setProperty(prop, value);
  }
  for (const [type, info] of Object.entries(config.SPACE_INFO || {})) {
    if (info.color) root.style.setProperty(`--c-${type.replace(/_/g, '-')}`, info.color);
  }
}
