/**
 * game_editions/animal-safari/config.js
 *
 * Animal Safari — an expedition through the world's wild places, collecting
 * paw prints of the animals you meet. Questions, deeds and action cards are in
 * the CSV files next to this one (edit those, then run
 * `npm run build:content animal-safari`).
 *
 * Reserve photos: game_editions/animal-safari/images/landmarks/ — credits in CREDITS.md.
 */

window.EDITION_CONFIG = {

  // ── Brand identity ──────────────────────────────────────────────────────────
  GAME: {
    engineName:   'Triventurex',
    editionName:  'Animal Safari',
    editionIcon:  '🦁',
    subtitle:     'Collect paw prints on an expedition through the world\'s wild places.',
    gameIdPrefix: 'AS',
    pointsName:   'Paw Prints',
    finishLabel:       'Safari Lodge',
    finishCelebration: 'Back at the lodge with amazing photos! 📸',
    finishButtonLabel: '🛖 Arrive at the lodge',
    endScreenMessage:  'Every explorer is back at the lodge!',
  },

  // ── Landmarks (reserves) ────────────────────────────────────────────────────
  // `image` path is relative to index.html.
  // `description` is shown in the landing modal when a player arrives.
  LANDMARKS: [
    // ── Africa ───────────────────────────────────────────────────────────────
    {
      name:        'Serengeti — Tanzania',
      image:       'game_editions/animal-safari/images/landmarks/serengeti.jpg',
      description: 'Endless grassy plains where more than a million wildebeest, with zebras and gazelles, travel in a giant circle every year: the Great Migration. Lions, cheetahs and hyenas follow the herds.',
    },
    {
      name:        'Masai Mara — Kenya',
      image:       'game_editions/animal-safari/images/landmarks/masai-mara.jpg',
      description: 'The northern end of the Great Migration. Every summer the herds have to cross the Mara River, where crocodiles are waiting for them.',
    },
    {
      name:        'Ngorongoro Crater — Tanzania',
      image:       'game_editions/animal-safari/images/landmarks/ngorongoro-crater.jpg',
      description: 'The bowl of a collapsed volcano, almost 20 km across, with a whole world of animals living inside: lions, elephants, hippos and rare black rhinos.',
    },
    {
      name:        'Okavango Delta — Botswana',
      image:       'game_editions/animal-safari/images/landmarks/okavango-delta.jpg',
      description: 'A river that never reaches the sea. It spreads out into the Kalahari Desert and makes a huge green maze of channels, full of elephants, hippos and crocodiles.',
    },
    {
      name:        'Kruger National Park — South Africa',
      image:       'game_editions/animal-safari/images/landmarks/kruger-national-park.jpg',
      description: 'One of Africa\'s biggest wildlife parks and home to the "Big Five": lion, leopard, elephant, rhino and buffalo.',
    },
    {
      name:        'Bwindi Forest — Uganda',
      image:       'game_editions/animal-safari/images/landmarks/bwindi-forest.jpg',
      description: 'The Bwindi Impenetrable Forest is a misty mountain rainforest where about half of all the world\'s mountain gorillas live. Chimpanzees live here too.',
    },
    {
      name:        'Avenue of the Baobabs — Madagascar',
      image:       'game_editions/animal-safari/images/landmarks/madagascar.jpg',
      description: 'Giant baobab trees line this famous road on Madagascar, an island where most of the animals live nowhere else on Earth, such as lemurs, chameleons and the fossa.',
    },

    // ── Asia ─────────────────────────────────────────────────────────────────
    {
      name:        'Sundarbans — India & Bangladesh',
      image:       'game_editions/animal-safari/images/landmarks/sundarbans.jpg',
      description: 'The world\'s largest mangrove forest, where the land floods with every tide. Bengal tigers live here and swim between the islands.',
    },
    {
      name:        'Borneo Rainforest — Malaysia & Indonesia',
      image:       'game_editions/animal-safari/images/landmarks/borneo-rainforest.jpg',
      description: 'One of the oldest rainforests on Earth and home of the orangutan, whose name means "person of the forest" in Malay.',
    },
    {
      name:        'Wolong Panda Reserve — China',
      image:       'game_editions/animal-safari/images/landmarks/wolong-panda-reserve.jpg',
      description: 'Bamboo-covered mountains in Sichuan where giant pandas live and are protected. A panda spends most of its day eating bamboo.',
    },
    {
      name:        'Komodo National Park — Indonesia',
      image:       'game_editions/animal-safari/images/landmarks/komodo-national-park.jpg',
      description: 'Rugged islands that are the home of the Komodo dragon, the biggest lizard in the world. They can grow up to 3 metres long.',
    },
    {
      name:        'Gobi Desert — Mongolia & China',
      image:       'game_editions/animal-safari/images/landmarks/gobi-desert.jpg',
      description: 'A cold, rocky desert with freezing winters and hot summers, where two-humped Bactrian camels roam.',
    },
    {
      name:        'Hemis National Park — India',
      image:       'game_editions/animal-safari/images/landmarks/hemis-national-park.jpg',
      description: 'High, snowy mountains in Ladakh, in the Himalayas. It is one of the best places in the world to spot the shy snow leopard, the "ghost of the mountains".',
    },

    // ── The Americas ─────────────────────────────────────────────────────────
    {
      name:        'Amazon Rainforest — South America',
      image:       'game_editions/animal-safari/images/landmarks/amazon-rainforest.jpg',
      description: 'The largest rainforest on Earth, home to jaguars, sloths, toucans, pink river dolphins and millions of kinds of insects.',
    },
    {
      name:        'Galápagos Islands — Ecuador',
      image:       'game_editions/animal-safari/images/landmarks/galapagos-islands.jpg',
      description: 'Volcanic islands where giant tortoises, marine iguanas and blue-footed boobies live. Charles Darwin\'s visit in 1835 helped him think about how animals change over time.',
    },
    {
      name:        'Pantanal — Brazil',
      image:       'game_editions/animal-safari/images/landmarks/pantanal.jpg',
      description: 'The world\'s largest tropical wetland and one of the best places to see jaguars, capybaras and caimans.',
    },
    {
      name:        'Monteverde Cloud Forest — Costa Rica',
      image:       'game_editions/animal-safari/images/landmarks/monteverde-cloud-forest.jpg',
      description: 'A forest high in the mountains, wrapped in clouds, full of sloths, hummingbirds and the bright green quetzal bird.',
    },
    {
      name:        'Yellowstone — USA',
      image:       'game_editions/animal-safari/images/landmarks/yellowstone.jpg',
      description: 'The world\'s first national park (1872), with bison, grizzly bears and wolves — and hot springs and geysers like Old Faithful.',
    },
    {
      name:        'Everglades — USA',
      image:       'game_editions/animal-safari/images/landmarks/everglades.jpg',
      description: 'A slow "river of grass" in Florida. It is the only place in the world where alligators and crocodiles live side by side in the wild.',
    },
    {
      name:        'Monarch Butterfly Reserve — Mexico',
      image:       'game_editions/animal-safari/images/landmarks/monarch-butterfly-reserve.jpg',
      description: 'Every winter millions of orange monarch butterflies fly thousands of kilometres from the USA and Canada to these mountain forests and cover the trees.',
    },

    // ── Oceania ──────────────────────────────────────────────────────────────
    {
      name:        'Kangaroo Island — Australia',
      image:       'game_editions/animal-safari/images/landmarks/kangaroo-island.jpg',
      description: 'An island where kangaroos, koalas, echidnas and sea lions can all be seen in a single day.',
    },
    {
      name:        'Daintree Rainforest — Australia',
      image:       'game_editions/animal-safari/images/landmarks/daintree-rainforest.jpg',
      description: 'One of the oldest rainforests in the world, home of the cassowary, a tall, colourful bird that cannot fly.',
    },
    {
      name:        'Great Barrier Reef — Australia',
      image:       'game_editions/animal-safari/images/landmarks/great-barrier-reef.jpg',
      description: 'The largest coral reef system in the world, full of turtles, clownfish, sharks and colourful corals.',
    },

    // ── Europe & the poles ───────────────────────────────────────────────────
    {
      name:        'Białowieża Forest — Poland & Belarus',
      image:       'game_editions/animal-safari/images/landmarks/bialowieza-forest.jpg',
      description: 'One of the last ancient forests in Europe. European bison had died out in the wild, and this is where they were brought back to roam free again.',
    },
    {
      name:        'Svalbard — Norway',
      image:       'game_editions/animal-safari/images/landmarks/svalbard.jpg',
      description: 'Arctic islands where polar bears, walruses and Arctic foxes live. In summer the sun never sets — that is the midnight sun.',
    },
    {
      name:        'Antarctica',
      image:       'game_editions/animal-safari/images/landmarks/antarctica.jpg',
      description: 'The coldest place on Earth. Emperor penguin fathers huddle together through the dark winter, keeping the eggs warm on their feet.',
    },
  ],

  // ── Board background image ──────────────────────────────────────────────────
  BOARD_BACKGROUND: {
    image:          'game_editions/animal-safari/images/backgrounds/savannah.jpg',
    overlayOpacity: 0.6,
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

  // ── Space type overrides ────────────────────────────────────────────────────
  SPACE_INFO: {
    finish:    { icon: '🛖', label: 'Safari Lodge' },
    good_deed: { icon: '🌿', label: 'Wildlife Hero', color: '#43A047' },
    bad_deed:  { icon: '🐊', label: 'Safari Mishap', color: '#C62828' },
    landmark:  { icon: '🏞️', label: 'Reserve',       color: '#F9A825' },
  },

  // ── Colour scheme ───────────────────────────────────────────────────────────
  COLORS: {
    // Primary brand colour (acacia green)
    '--green':          '#558B2F',
    '--green-dark':     '#33691E',
    '--green-light':    '#DCEDC8',

    // Secondary / accent (earth brown & savannah gold)
    '--blue':           '#5D4037',
    '--gold':           '#F9A825',
    '--danger':         '#C62828',

    // UI surfaces (sand)
    '--bg':             '#F6F3E7',
    '--card':           '#FFFFFF',
    '--text':           '#1A1A1A',
    '--text-muted':     '#5A5A5A',
    '--border':         '#E3DCC5',

    // Fixed space colours
    '--c-start':        '#558B2F',
    '--c-finish':       '#F9A825',

    // Setup & End screen gradient (jungle green → acacia → sunset orange)
    '--gradient-a':     '#33691E',
    '--gradient-b':     '#689F38',
    '--gradient-c':     '#E65100',

    // Board viewport fallback gradient
    '--vp-a':           '#DCEDC8',
    '--vp-b':           '#F1E9D2',
    '--vp-c':           '#FFE0B2',

    // Deed card result colours
    '--deed-good-bg':   '#F1F8E9',
    '--deed-good-text': '#33691E',
    '--deed-bad-bg':    '#FFEBEE',
    '--deed-bad-text':  '#B71C1C',
  },

  // ── End-screen awards (G13) — rename any engine award (js/shared/config.js AWARDS)
  AWARDS: {
    quizMaster:    { icon: '🦉', title: 'Wise Owl' },
    performer:     { icon: '🐒', title: 'Cheeky Monkey' },
    goodDeeds:     { icon: '🌿', title: 'Wildlife Hero' },
    badDeeds:      { icon: '🐊', title: 'Croc Magnet' },
    explorer:      { icon: '🔭', title: 'Safari Guide' },
    bigTurn:       { icon: '🦘', title: 'Big Leap' },
    luckyRoller:   { icon: '🐆', title: 'Cheetah Speed' },
    unluckyRoller: { icon: '🐌', title: 'Snail Pace' },
    patience:      { icon: '🦥', title: 'Slow as a Sloth' },
  },

};
