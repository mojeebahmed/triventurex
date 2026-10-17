/**
 * game_editions/editions.js
 * Registry of all available Triventurex game editions.
 *
 * TO ADD A NEW EDITION:
 *   1. Create a folder: game_editions/<your-id>/
 *   2. Copy game_editions/template/ into it and edit the files.
 *   3. Add an entry to TRIVENTUREX_EDITIONS below.
 *   That's it — the edition will appear on the setup screen automatically.
 *
 * Each entry:
 *   id          – folder name under game_editions/ (must match exactly)
 *   name        – display name shown on setup screen
 *   icon        – single emoji representing the edition
 *   description – one-line description shown on the edition card
 *   accentColor – card border/highlight colour when selected
 */

window.TRIVENTUREX_EDITIONS = [

  {
    id:          'swab-quest',
    name:        'Swab Quest',
    icon:        '🕌',
    description: 'Islamic & Ahmadiyya family game. Journey to collecting Sawab.',
    accentColor: '#3d9e41',
  },

  {
    id:          'football-quest',
    name:        'Football Quest',
    icon:        '⚽',
    description: 'Score Goals and reach the Final. The beautiful game on a board.',
    accentColor: '#3485bf',
  },

  {
    id:          'world-tour',
    name:        'World Tour',
    icon:        '🌍',
    description: 'Collect Stamps on a trip around the world, from the Eiffel Tower to Machu Picchu.',
    accentColor: '#00897B',
  },

  {
    id:          'animal-safari',
    name:        'Animal Safari',
    icon:        '🦁',
    description: 'Collect Paw Prints on an expedition through the world\'s wild places, from the Serengeti to Antarctica.',
    accentColor: '#558B2F',
  },

  {
    id:          'prophets-stories',
    name:        "Prophets' Stories",
    icon:        '📖',
    description: 'Travel through the stories of the prophets, from Hadhrat Adam (as) to the Promised Messiah (as), and collect Noor.',
    accentColor: '#283593',
  },

];
