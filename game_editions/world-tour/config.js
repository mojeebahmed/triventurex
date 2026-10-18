/**
 * game_editions/world-tour/config.js
 *
 * World Tour — a trip around the world, collecting passport stamps at famous
 * wonders. Questions, deeds and action cards are in the CSV files next to this
 * one (edit those, then run `npm run build:content world-tour`).
 *
 * Landmark photos: game_editions/world-tour/images/landmarks/ — credits in CREDITS.md.
 */

window.EDITION_CONFIG = {

  // ── Brand identity ──────────────────────────────────────────────────────────
  GAME: {
    engineName:   'Triventurex',
    editionName:  'World Tour',
    editionIcon:  '🌍',
    subtitle:     'Collect passport stamps on a trip around the world.',
    gameIdPrefix: 'WT',
    pointsName:   'Stamps',
    finishLabel:       'Home Again',
    finishCelebration: "Welcome home, world traveller! 🧳",
    finishButtonLabel: '🏠 Land back home',
    endScreenMessage:  'Every traveller is home again!',
  },

  // ── Landmarks ───────────────────────────────────────────────────────────────
  // `image` path is relative to index.html.
  // `description` is shown in the landing modal when a player arrives.
  LANDMARKS: [
    // ── Europe ───────────────────────────────────────────────────────────────
    {
      name:        'Eiffel Tower — Paris',
      image:       'game_editions/world-tour/images/landmarks/eiffel-tower.jpg',
      description: 'The Eiffel Tower was built for the 1889 World\'s Fair in Paris and is over 320 metres tall. It was the tallest structure in the world until 1930, and it gets a fresh coat of paint about every seven years.',
    },
    {
      name:        'Colosseum — Rome',
      image:       'game_editions/world-tour/images/landmarks/colosseum.jpg',
      description: 'This giant amphitheatre opened almost 2,000 years ago, in the year 80. Tens of thousands of people came to watch gladiator contests and shows here. It is still the largest amphitheatre ever built.',
    },
    {
      name:        'Big Ben — London',
      image:       'game_editions/world-tour/images/landmarks/big-ben.jpg',
      description: '"Big Ben" is really the name of the huge bell inside the clock tower. The tower itself was renamed the Elizabeth Tower in 2012. The clock has kept time over London since 1859.',
    },
    {
      name:        'Sagrada Família — Barcelona',
      image:       'game_editions/world-tour/images/landmarks/sagrada-familia.jpg',
      description: 'Architect Antoni Gaudí designed this church, and building began in 1882. More than 140 years later it is still not completely finished! Its tallest tower was planned to be completed in 2026, 100 years after Gaudí\'s death.',
    },
    {
      name:        'Acropolis — Athens',
      image:       'game_editions/world-tour/images/landmarks/acropolis.jpg',
      description: 'A rocky hill above Athens crowned by the Parthenon, a temple built about 2,500 years ago for the goddess Athena. It is a symbol of ancient Greece, where democracy was born.',
    },
    {
      name:        'Neuschwanstein Castle — Bavaria',
      image:       'game_editions/world-tour/images/landmarks/neuschwanstein-castle.jpg',
      description: 'King Ludwig II of Bavaria began building this fairy-tale castle in 1869. It helped inspire the castle in Disney\'s Sleeping Beauty. Ludwig died before it was finished, and today millions of people visit it every year.',
    },

    // ── Africa ───────────────────────────────────────────────────────────────
    {
      name:        'Pyramids of Giza — Egypt',
      image:       'game_editions/world-tour/images/landmarks/pyramids-of-giza.jpg',
      description: 'The Great Pyramid is about 4,500 years old and was the tallest building made by people for almost 4,000 years. It is the only one of the Seven Wonders of the Ancient World that is still standing.',
    },
    {
      name:        'Mount Kilimanjaro — Tanzania',
      image:       'game_editions/world-tour/images/landmarks/mount-kilimanjaro.jpg',
      description: 'Africa\'s highest mountain, 5,895 metres tall. It is a sleeping volcano, and even though it stands close to the equator, its top has snow and ice.',
    },
    {
      name:        'Victoria Falls — Zambia & Zimbabwe',
      image:       'game_editions/world-tour/images/landmarks/victoria-falls.jpg',
      description: 'One of the biggest waterfalls in the world, on the Zambezi River between Zambia and Zimbabwe. Its local name, Mosi-oa-Tunya, means "the smoke that thunders" — you can see its spray from far away.',
    },
    {
      name:        'Table Mountain — Cape Town',
      image:       'game_editions/world-tour/images/landmarks/table-mountain.jpg',
      description: 'A mountain with a flat top, about 3 km wide, looking over Cape Town in South Africa. When clouds spill over the edge, people say the "tablecloth" is on the table.',
    },

    // ── Asia & the Middle East ───────────────────────────────────────────────
    {
      name:        'Petra — Jordan',
      image:       'game_editions/world-tour/images/landmarks/petra.jpg',
      description: 'A city carved straight into rose-red cliffs by the Nabataean people more than 2,000 years ago. Its most famous building, the Treasury (Al-Khazneh), is cut out of a single rock face.',
    },
    {
      name:        'Taj Mahal — Agra',
      image:       'game_editions/world-tour/images/landmarks/taj-mahal.jpg',
      description: 'Mughal emperor Shah Jahan built this white marble tomb in the 1600s in memory of his wife, Mumtaz Mahal. The marble seems to change colour during the day, from pink in the morning to gold at sunset.',
    },
    {
      name:        'Great Wall of China',
      image:       'game_editions/world-tour/images/landmarks/great-wall-of-china.jpg',
      description: 'Built and rebuilt over more than 2,000 years, the wall and its branches stretch for thousands of kilometres. A popular myth says you can see it from the Moon — you can\'t!',
    },
    {
      name:        'Mount Fuji — Japan',
      image:       'game_editions/world-tour/images/landmarks/mount-fuji.jpg',
      description: 'Japan\'s highest mountain, 3,776 metres tall, with an almost perfect cone shape. It is a volcano, and its snowy top is one of the most famous sights in Japan.',
    },
    {
      name:        'Angkor Wat — Cambodia',
      image:       'game_editions/world-tour/images/landmarks/angkor-wat.jpg',
      description: 'Built in the 1100s, it is the largest religious monument in the world. It is so important to Cambodia that it appears on the country\'s flag.',
    },
    {
      name:        'Burj Khalifa — Dubai',
      image:       'game_editions/world-tour/images/landmarks/burj-khalifa.jpg',
      description: 'When it opened in 2010, this 828-metre skyscraper became the tallest building in the world. It has more than 150 floors, and its lifts are among the fastest anywhere.',
    },
    {
      name:        'Hagia Sophia — Istanbul',
      image:       'game_editions/world-tour/images/landmarks/hagia-sophia.jpg',
      description: 'Finished in the year 537, its giant dome amazed the world for centuries. It was first a church, then a mosque, then a museum — and it has been a mosque again since 2020.',
    },

    // ── Oceania ──────────────────────────────────────────────────────────────
    {
      name:        'Sydney Opera House — Sydney',
      image:       'game_editions/world-tour/images/landmarks/sydney-opera-house.jpg',
      description: 'Its roofs look like white sails on the harbour. Designed by the Danish architect Jørn Utzon, it opened in 1973 and is one of the most famous buildings of the 20th century.',
    },
    {
      name:        'Uluru — Australia',
      image:       'game_editions/world-tour/images/landmarks/uluru.jpg',
      description: 'A huge sandstone rock, 348 metres high, rising from the desert in the middle of Australia. It is sacred to the Anangu, its traditional owners, and glows red at sunset. Since 2019 climbing it is no longer allowed.',
    },
    {
      name:        'Moai — Easter Island',
      image:       'game_editions/world-tour/images/landmarks/moai-easter-island.jpg',
      description: 'Nearly 900 giant stone statues carved by the Rapa Nui people. Many have bodies buried under the ground! Easter Island is one of the most remote places on Earth where people live.',
    },

    // ── The Americas ─────────────────────────────────────────────────────────
    {
      name:        'Statue of Liberty — New York',
      image:       'game_editions/world-tour/images/landmarks/statue-of-liberty.jpg',
      description: 'A gift from France to the United States, opened in 1886. It is made of copper, which turned green over the years — just like an old penny.',
    },
    {
      name:        'Grand Canyon — Arizona',
      image:       'game_editions/world-tour/images/landmarks/grand-canyon.jpg',
      description: 'Carved by the Colorado River over millions of years, the canyon is up to 1.8 km deep. Its rock layers show almost two billion years of Earth\'s history.',
    },
    {
      name:        'Niagara Falls — USA & Canada',
      image:       'game_editions/world-tour/images/landmarks/niagara-falls.jpg',
      description: 'Three waterfalls on the border between the USA and Canada. Boats take visitors right up to the spray at the bottom of the Horseshoe Falls.',
    },
    {
      name:        'Chichén Itzá — Mexico',
      image:       'game_editions/world-tour/images/landmarks/chichen-itza.jpg',
      description: 'A great city of the Maya. Its main pyramid, El Castillo, has 365 steps in total — one for each day of the year.',
    },
    {
      name:        'Machu Picchu — Peru',
      image:       'game_editions/world-tour/images/landmarks/machu-picchu.jpg',
      description: 'An Inca city built in the 1400s high in the Andes mountains. It became famous around the world after the explorer Hiram Bingham visited it in 1911.',
    },
    {
      name:        'Christ the Redeemer — Rio de Janeiro',
      image:       'game_editions/world-tour/images/landmarks/christ-the-redeemer.jpg',
      description: 'This 30-metre statue has watched over Rio from the top of Corcovado mountain since 1931. Its arms stretch about 28 metres wide.',
    },
  ],

  // ── Board background image ──────────────────────────────────────────────────
  // A 1635 world map by Willem Blaeu (public domain) — see CREDITS.md.
  BOARD_BACKGROUND: {
    image:          'game_editions/world-tour/images/backgrounds/world-map-1635.jpg',
    overlayOpacity: 0.7,
    size:           'cover',
    position:       'center',
    blur:           0,
  },

  // ── Space distribution — the standard mix (same as Swab Quest) ──────────────
  SPACE_DISTRIBUTION: {
    short:  { action: 0.10, good_deed: 0.10, bad_deed: 0.10, landmark: 0.08, skip: 0.05 },
    medium: { action: 0.10, good_deed: 0.10, bad_deed: 0.10, landmark: 0.08, skip: 0.05 },
    long:   { action: 0.12, good_deed: 0.10, bad_deed: 0.10, landmark: 0.08, skip: 0.05 },
  },

  // ── Icons ──────────────────────────────────────────────────────────────────
  // Only the icons this edition changes; every other icon is the engine's
  // (names: js/shared/icon-registry.js). A value is an emoji, '<set>:<icon>'
  // (e.g. 'lucide:trophy') or 'file:icons/<picture>.svg' in this folder.
  ICONS: {
    tileFinish:     '🏠',
    tileGoodDeed:   '✈️',
    tileBadDeed:    '🧳',
    tileLandmark:   '📍',
    awardGoodDeeds: '🤝',
    awardBadDeeds:  '🧳',
    awardExplorer:  '🗺️',
  },

  // ── Space type overrides ────────────────────────────────────────────────────
  SPACE_INFO: {
    finish:    { label: 'Home Again' },
    good_deed: { label: 'Smooth Travels', color: '#00897B' },
    bad_deed:  { label: 'Travel Trouble', color: '#C62828' },
    landmark:  { label: 'Wonder',         color: '#FFB300' },
  },

  // ── Colour scheme ───────────────────────────────────────────────────────────
  COLORS: {
    // Primary brand colour (ocean teal)
    '--green':          '#00695C',
    '--green-dark':     '#004D40',
    '--green-light':    '#B2DFDB',

    // Secondary / accent (passport navy & sunset amber)
    '--blue':           '#1A237E',
    '--gold':           '#FFB300',
    '--danger':         '#C62828',

    // UI surfaces
    '--bg':             '#F1F7F6',
    '--card':           '#FFFFFF',
    '--text':           '#1A1A1A',
    '--text-muted':     '#555555',
    '--border':         '#CFE3E0',

    // Fixed space colours
    '--c-start':        '#00695C',
    '--c-finish':       '#FFB300',

    // Setup & End screen gradient (sea → teal → passport navy)
    '--gradient-a':     '#0097A7',
    '--gradient-b':     '#00695C',
    '--gradient-c':     '#1A237E',

    // Board viewport fallback gradient
    '--vp-a':           '#B2DFDB',
    '--vp-b':           '#E0F2F1',
    '--vp-c':           '#C5CAE9',

    // Deed card result colours
    '--deed-good-bg':   '#E0F2F1',
    '--deed-good-text': '#004D40',
    '--deed-bad-bg':    '#FFEBEE',
    '--deed-bad-text':  '#B71C1C',
  },

  // ── End-screen awards (G13) — rename any engine award (js/shared/config.js AWARDS)
  AWARDS: {
    quizMaster:    { title: 'Know-it-all Navigator' },
    performer:     { title: 'Street Performer' },
    goodDeeds:     { title: 'Friendly Traveller' },
    badDeeds:      { title: 'Lost Luggage' },
    explorer:      { title: 'Globetrotter' },
    patience:      { title: 'Delayed Flight' },
  },

};
