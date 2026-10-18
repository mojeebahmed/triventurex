/**
 * game_editions/football-quest/config.js
 *
 * Edition configuration for "Football Quest" — Triventurex edition 2.
 *
 * TO CREATE A NEW EDITION:
 *   1. Copy this folder (game_editions/football-quest/) to game_editions/<your-edition>/
 *   2. Edit config.js, questions.js, deeds.js and replace images.
 *   3. Add an entry to game_editions/editions.js.
 */

window.EDITION_CONFIG = {

  // ── Brand identity ──────────────────────────────────────────────────────────
  GAME: {
    engineName:   'Triventurex',
    editionName:  'Football Quest',
    editionIcon:  '⚽',
    subtitle:     'Score Goals and reach the Final — the beautiful game on a board.',
    gameIdPrefix: 'FQ',
    pointsName:   'Goals',
    finishLabel:       'The Final',
    finishCelebration: "Full time! You've reached the Final! 🏆",
    finishButtonLabel: '🏆 Lift the Trophy!',
    endScreenMessage:  'All players have reached the Final!',
  },

  // ── Landmarks ───────────────────────────────────────────────────────────────
  // `image` path is relative to index.html.
  // `description` is shown in the landing modal when a player arrives.
  LANDMARKS: [
    // ── Iconic Stadiums ──────────────────────────────────────────────────────
    {
      name:        'Wembley Stadium',
      image:       'game_editions/football-quest/images/landmarks/wembley-stadium.jpg',
      description: 'Wembley Stadium in London is the home of English football and one of the most iconic venues in the world. With a capacity of 90,000, it has hosted FA Cup finals, European Championships, and World Cup matches. Its famous arch, rising 133 metres above the pitch, is visible across London.',
    },
    {
      name:        'Camp Nou',
      image:       'game_editions/football-quest/images/landmarks/camp-nou.jpg',
      description: "Camp Nou in Barcelona is Europe's largest football stadium, with a capacity of over 99,000. Home to FC Barcelona since 1957, it has witnessed some of the greatest moments in football history — from European Cup triumphs to El Clásico classics. Its name simply means 'New Ground' in Catalan.",
    },
    {
      name:        'Santiago Bernabéu',
      image:       'game_editions/football-quest/images/landmarks/santiago-bernabeu.jpg',
      description: 'The Santiago Bernabéu in Madrid is the home of Real Madrid, the most decorated club in UEFA Champions League history. Named after the club president who oversaw its construction in 1947, the stadium has hosted World Cup finals, European Cup finals, and Champions League showpieces. Its recent renovation has made it one of the most modern stadiums on earth.',
    },
    {
      name:        'Anfield',
      image:       'game_editions/football-quest/images/landmarks/anfield.jpg',
      description: "Anfield is the legendary home of Liverpool FC, famous for its electric atmosphere and the iconic Kop stand. When 54,000 fans sing 'You'll Never Walk Alone' before kickoff, it is regarded as one of the most spine-tingling experiences in football. Anfield has hosted European Cup semi-finals and some of the greatest comebacks in football history.",
    },
    {
      name:        'Old Trafford',
      image:       'game_editions/football-quest/images/landmarks/old-trafford.jpg',
      description: "Old Trafford, known as the 'Theatre of Dreams', has been Manchester United's home since 1910. With a capacity of over 74,000, it is the largest club stadium in England. The ground has hosted FA Cup finals, European Cup finals, and iconic Champions League nights under the floodlights.",
    },
    {
      name:        'Maracanã',
      image:       'game_editions/football-quest/images/landmarks/maracana.jpg',
      description: 'The Maracanã in Rio de Janeiro is one of football\'s most mythical stadiums. Built for the 1950 World Cup, it once held an attendance of nearly 200,000 people. It hosted the 1950 and 2014 World Cup finals, as well as the 2016 Olympic Games. The stadium is a cathedral to the beautiful game in Brazil.',
    },
    {
      name:        'San Siro',
      image:       'game_editions/football-quest/images/landmarks/san-siro.jpg',
      description: 'San Siro (officially Stadio Giuseppe Meazza) in Milan is one of the most atmospheric grounds in European football. Shared by AC Milan and Inter Milan, it holds 75,000 fans and has hosted World Cup matches, European Cup finals, and countless Serie A derbies. Its distinctive circular towers make it unmistakable on the skyline.',
    },
    {
      name:        'Allianz Arena',
      image:       'game_editions/football-quest/images/landmarks/allianz-arena.jpg',
      description: 'The Allianz Arena in Munich is famous for its futuristic exterior of illuminated panels that glow red for Bayern Munich, blue for TSV 1860, and white for Germany. Opened in 2005, it replaced the legendary Olympiastadion and has become one of the most recognisable football venues in the world, hosting the 2012 Champions League final.',
    },
    {
      name:        'Signal Iduna Park',
      image:       'game_editions/football-quest/images/landmarks/signal-iduna-park.jpg',
      description: "Signal Iduna Park in Dortmund is home to Borussia Dortmund and is famous for the 'Yellow Wall' — the Südtribüne, Europe's largest standing terrace, which holds over 24,000 fans. The atmosphere generated by 81,000 passionate supporters makes it one of the loudest stadiums in world football. It hosted matches at the 2006 World Cup.",
    },
    {
      name:        'Estadio Azteca',
      image:       'game_editions/football-quest/images/landmarks/estadio-azteca.jpg',
      description: "The Estadio Azteca in Mexico City is the only stadium to have hosted two FIFA World Cup finals — in 1970 and 1986. It is also the stage for two of football's most famous moments: Diego Maradona's 'Goal of the Century' and the 'Hand of God' in 1986. With a capacity of 87,000, it remains one of the largest stadiums in the Americas.",
    },
    {
      name:        'Lusail Stadium',
      image:       'game_editions/football-quest/images/landmarks/lusail-stadium.jpg',
      description: 'The Lusail Stadium in Qatar hosted the 2022 FIFA World Cup final — the most watched final in football history. With a capacity of 89,000, its design is inspired by the decorative bowls and lanterns of Arab and Islamic culture. It was the centrepiece of the first World Cup held in the Middle East.',
    },
    {
      name:        'Johan Cruyff Arena',
      image:       'game_editions/football-quest/images/landmarks/johan-cruyff-arena.jpg',
      description: "The Johan Cruyff Arena in Amsterdam is the home of AFC Ajax, one of Europe's most celebrated clubs. Renamed in honour of Dutch legend Johan Cruyff in 2018, it was the first stadium in Europe with a retractable roof. Ajax have won the Champions League four times, producing a remarkable lineage of world-class footballers.",
    },
    {
      name:        'Celtic Park',
      image:       'game_editions/football-quest/images/landmarks/celtic-park.jpg',
      description: "Celtic Park in Glasgow, known as 'Paradise', is the home of Celtic FC and one of the most atmospheric grounds in Britain. With a capacity of 60,000, it generates a wall of noise during Old Firm derbies against Rangers. Celtic became the first British club to win the European Cup in 1967, a team known as the 'Lisbon Lions'.",
    },
    {
      name:        'Stamford Bridge',
      image:       'game_editions/football-quest/images/landmarks/stamford-bridge.jpg',
      description: "Stamford Bridge has been Chelsea FC's home since 1905 and sits in the heart of Fulham, West London. Under the ownership of Roman Abramovich, Chelsea became one of Europe's most powerful clubs, winning the Champions League in 2012 and 2021. The ground holds 40,000 fans and sits beside the Fulham Road in one of London's most famous neighbourhoods.",
    },
    {
      name:        'Etihad Stadium',
      image:       'game_editions/football-quest/images/landmarks/etihad-stadium.jpg',
      description: 'The Etihad Stadium is home to Manchester City, one of the dominant forces in modern football. Originally built for the 2002 Commonwealth Games, City moved in the same year and have since transformed it into a 53,000-capacity arena. Under Pep Guardiola, City have won multiple Premier League titles and the 2023 Champions League from this ground.',
    },
    {
      name:        'Estádio da Luz',
      image:       'game_editions/football-quest/images/landmarks/estadio-da-luz.jpg',
      description: "Estádio da Luz ('Stadium of Light') in Lisbon is the home of Sport Lisboa e Benfica, one of Portugal's most beloved clubs. Rebuilt for Euro 2004, it holds 64,000 fans and has hosted a Champions League final. It is named after the Luz neighbourhood and has been graced by Portuguese legends including Eusébio and, more recently, players shaped by Benfica's famous academy.",
    },
    // ── Football Culture ─────────────────────────────────────────────────────
    {
      name:        'FIFA Museum',
      image:       'game_editions/football-quest/images/landmarks/fifa-museum.jpg',
      description: 'The FIFA Museum in Zurich, Switzerland, is a four-floor journey through the history of world football. Opened in 2016, it houses the original FIFA World Cup trophies, iconic kits and boots from the greatest players ever, and interactive exhibits on the global story of the beautiful game. Over 1,000 objects from football history are on display.',
    },
    {
      name:        'National Football Museum',
      image:       'game_editions/football-quest/images/landmarks/national-football-museum.jpg',
      description: "The National Football Museum in Manchester is England's dedicated home of football history. It holds the world's largest collection of football memorabilia — from the shirt Pelé wore at the 1970 World Cup to the ball used in the 1966 World Cup final. It celebrates the invention of the modern game in England and its spread across the globe.",
    },
    {
      name:        'Estadio Centenario',
      image:       'game_editions/football-quest/images/landmarks/estadio-centenario.jpg',
      description: 'The Estadio Centenario in Montevideo, Uruguay, hosted the very first FIFA World Cup final in 1930 — Uruguay beat Argentina 4–2 to become the inaugural champions. Built specifically for the tournament, it was declared a FIFA Historical Monument in 1983 and remains a monument to the origins of the World Cup.',
    },
    {
      name:        'Stade de France',
      image:       'game_editions/football-quest/images/landmarks/stade-de-france.jpg',
      description: "The Stade de France in Saint-Denis, Paris, is France's national stadium and one of the largest in Europe, holding 81,000 spectators. Built for the 1998 FIFA World Cup — which France won on home soil — it has hosted World Cup matches, European Championship finals, and UEFA Champions League finals. It is the centrepiece of French football.",
    },
  ],

  // ── Board background image ──────────────────────────────────────────────────
  // Set image to null to use the CSS gradient fallback.
  // Add a background to game_editions/football-quest/images/backgrounds/ and update the path.
  BOARD_BACKGROUND: {
    image:          null,
    overlayOpacity: 0.75,
    size:           'cover',
    position:       'center',
    blur:           0,
  },

  // ── Space distribution overrides (optional) ─────────────────────────────────
  // Ratios for each non-question space type. Questions always fill whatever
  // space remains after all other types are counted — no 'question' key needed.
  SPACE_DISTRIBUTION: {
    short: {
      action:    0.10,
      good_deed: 0.10,
      bad_deed:  0.10,
      landmark:  0.04,
      skip:      0.05,
    },
    medium: {
      action:    0.10,
      good_deed: 0.10,
      bad_deed:  0.10,
      landmark:  0.05,
      skip:      0.05,
    },
    long: {
      action:    0.12,
      good_deed: 0.10,
      bad_deed:  0.10,
      landmark:  0.06,
      skip:      0.06,
    },
  },

  // ── Icons ──────────────────────────────────────────────────────────────────
  // Only the icons this edition changes; every other icon is the engine's
  // (names: js/shared/icon-registry.js). A value is an emoji, '<set>:<icon>'
  // (e.g. 'lucide:trophy') or 'file:icons/<picture>.svg' in this folder.
  ICONS: {
    tileFinish:    '🏆',
    tileGoodDeed:  '⚽',
    tileBadDeed:   '🟥',
    tileLandmark:  '🏟️',
    awardExplorer: '🏟️',
    awardBigTurn:  '⚽',
    awardBadDeeds: '🟥',
  },

  // ── Space type overrides ────────────────────────────────────────────────────
  SPACE_INFO: {
    finish:    { label: 'The Final' },
    good_deed: { label: 'Good Play',  color: '#2E7D32' },
    bad_deed:  { label: 'Foul Play',  color: '#C62828' },
    landmark:  { label: 'Stadium',    color: '#F57F17' },
  },

  // ── Colour scheme ───────────────────────────────────────────────────────────
  COLORS: {
    // Primary brand colour (pitch green)
    '--green':          '#1B5E20',
    '--green-dark':     '#003300',
    '--green-light':    '#C8E6C9',

    // Secondary / accent (football blue & gold)
    '--blue':           '#0D47A1',
    '--gold':           '#FFD600',
    '--danger':         '#C62828',

    // UI surfaces
    '--bg':             '#F1F8E9',
    '--card':           '#FFFFFF',
    '--text':           '#1A1A1A',
    '--text-muted':     '#555555',
    '--border':         '#DCEDC8',

    // Fixed space colours
    '--c-start':        '#1B5E20',
    '--c-finish':       '#FFD600',

    // Setup & End screen gradient (dark pitch green → navy blue)
    '--gradient-a':     '#1b92c5',
    '--gradient-b':     '#12b199',
    '--gradient-c':     '#5827d6',

    // Board viewport fallback gradient
    '--vp-a':           '#C8E6C9',
    '--vp-b':           '#DCEDC8',
    '--vp-c':           '#C5CAE9',

    // Deed card result colours
    '--deed-good-bg':   '#E8F5E9',
    '--deed-good-text': '#1B5E20',
    '--deed-bad-bg':    '#FFEBEE',
    '--deed-bad-text':  '#B71C1C',
  },

  // ── End-screen awards (G13) — rename any engine award (js/shared/config.js AWARDS)
  AWARDS: {
    quizMaster: { title: 'Football brain' },
    performer:  { title: 'Man of the match' },
    explorer:   { title: 'Groundhopper' },
    bigTurn:    { title: 'Match winner' },
    badDeeds:   { title: 'Red card magnet' },
  },

};
