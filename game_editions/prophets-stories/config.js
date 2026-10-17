/**
 * game_editions/prophets-stories/config.js
 *
 * Prophets' Stories — a journey through the stories of the prophets, from
 * Hadhrat Adam (as) to the Holy Prophet Muhammad (sa) and the Promised
 * Messiah (as), collecting Noor. Ahmadiyya understanding; Qur'an references
 * count Bismillah as verse 1. Questions, deeds and action cards are in the CSV
 * files next to this one (edit those, then run
 * `npm run build:content prophets-stories`). Design notes: OUTLINE.md.
 *
 * Place photos (places only, never people): images/landmarks/ — credits in CREDITS.md.
 */

window.EDITION_CONFIG = {

  // ── Brand identity ──────────────────────────────────────────────────────────
  GAME: {
    engineName:   'Triventurex',
    editionName:  "Prophets' Stories",
    editionIcon:  '📖',
    subtitle:     'Travel through the stories of the prophets and collect Noor.',
    gameIdPrefix: 'PS',
    pointsName:   'Noor',
    finishLabel:       "Al-Ka'ba, Mecca",
    finishCelebration: 'Alhamdulillah! MashaAllah! 🌙',
    finishButtonLabel: '🕋 Alhamdulillah!',
    endScreenMessage:  'All players have reached Mecca!',
  },

  // ── Landmarks (blessed places) ──────────────────────────────────────────────
  // `image` path is relative to index.html.
  // `description` is shown in the landing modal when a player arrives.
  // Qur'an references count Bismillah as verse 1.
  LANDMARKS: [
    // ── Makkah & Madinah ─────────────────────────────────────────────────────
    {
      name:        'Cave of Hira — Makkah',
      image:       'game_editions/prophets-stories/images/landmarks/cave-of-hira.jpg',
      description: 'A small cave high on Jabal al-Nour, the "Mountain of Light". Here the first revelation came to the Holy Prophet Muhammad (sa) in about 610: "Read in the name of thy Lord who created" (Surah Al-\'Alaq 96:2).',
    },
    {
      name:        'Cave of Thawr — Makkah',
      image:       'game_editions/prophets-stories/images/landmarks/cave-of-thawr.jpg',
      description: 'At the start of the Hijrah, the Holy Prophet (sa) and Hadhrat Abu Bakr (ra) hid in a cave on this mountain for three days. He comforted his friend: "Grieve not, for Allah is with us" (Surah At-Taubah 9:40).',
    },
    {
      name:        'Mount Arafat — Makkah',
      image:       'game_editions/prophets-stories/images/landmarks/mount-arafat.jpg',
      description: 'The plain and hill where the Holy Prophet (sa) gave his Farewell Sermon during his last Hajj. Pilgrims gather here on the Day of Arafah to pray.',
    },
    {
      name:        "Ta'if",
      image:       'game_editions/prophets-stories/images/landmarks/taif.jpg',
      description: 'A mountain town near Makkah. When its people threw stones at the Holy Prophet (sa), he did not curse them but prayed that their children would one day worship Allah (Bukhari).',
    },
    {
      name:        'Masjid Quba — Madinah',
      image:       'game_editions/prophets-stories/images/landmarks/masjid-quba.jpg',
      description: 'The first mosque built by the Holy Prophet (sa), when he arrived near Madinah after the Hijrah. He and his companions carried the stones themselves.',
    },
    {
      name:        'Masjid an-Nabawi — Madinah',
      image:       'game_editions/prophets-stories/images/landmarks/masjid-nabawi.jpg',
      description: 'The Prophet\'s Mosque, first built by the Holy Prophet (sa) and his companions with palm trunks and mud bricks. He is buried here, under the Green Dome.',
    },
    {
      name:        'Masjid al-Qiblatayn — Madinah',
      image:       'game_editions/prophets-stories/images/landmarks/masjid-qiblatayn.jpg',
      description: 'The "Mosque of the Two Qiblas". By tradition, this is where the Muslims turned during a prayer from Jerusalem towards the Ka\'ba, when the new qibla was revealed (Surah Al-Baqarah 2:145).',
    },
    {
      name:        'Mount Uhud — Madinah',
      image:       'game_editions/prophets-stories/images/landmarks/mount-uhud.jpg',
      description: 'The Holy Prophet (sa) said: "Uhud is a mountain that loves us, and we love it" (Bukhari). The Battle of Uhud took place at its foot in the year 3 AH.',
    },
    {
      name:        'Badr',
      image:       'game_editions/prophets-stories/images/landmarks/badr.jpg',
      description: 'The place of the Battle of Badr (2 AH), where about 313 Muslims stood firm against an army three times bigger. The Qur\'an calls it "the Day of Distinction" (Surah Al-Anfal 8:42).',
    },

    // ── Arabia's earlier prophets ────────────────────────────────────────────
    {
      name:        "Hegra (Mada'in Salih)",
      image:       'game_editions/prophets-stories/images/landmarks/hegra.jpg',
      description: 'Tombs carved into giant rocks near AlUla. Many link this valley to the Thamud, the people of Hadhrat Salih (as), who "hewed houses in the mountains" (Surah Al-Hijr 15:83).',
    },
    {
      name:        'The Empty Quarter (Al-Ahqaf)',
      image:       'game_editions/prophets-stories/images/landmarks/empty-quarter.jpg',
      description: 'The great sand dunes of southern Arabia. The Qur\'an tells how Hadhrat Hud (as) warned his people, the \'Ad, "among the sand dunes" (Al-Ahqaf) (Surah Al-Ahqaf 46:22).',
    },

    // ── From Iraq to Egypt ───────────────────────────────────────────────────
    {
      name:        'Ziggurat of Ur — Iraq',
      image:       'game_editions/prophets-stories/images/landmarks/ziggurat-of-ur.jpg',
      description: 'A temple tower in the ancient city of Ur, which tradition names as the birthplace of Hadhrat Ibrahim (as) (Abraham). Its people worshipped idols, and he called them to the One God.',
    },
    {
      name:        'Mount Judi',
      image:       'game_editions/prophets-stories/images/landmarks/mount-judi.jpg',
      description: 'The Qur\'an says the Ark of Hadhrat Nuh (as) (Noah) came to rest on Al-Judi (Surah Hud 11:45). It is traditionally placed in the mountains of south-east Turkey.',
    },
    {
      name:        'Nineveh — Iraq',
      image:       'game_editions/prophets-stories/images/landmarks/nineveh.jpg',
      description: 'The great city to which Hadhrat Yunus (as) (Jonah) was sent. When its people believed, Allah removed the punishment from them (Surah Yunus 10:99).',
    },
    {
      name:        'The Nile — Egypt',
      image:       'game_editions/prophets-stories/images/landmarks/nile.jpg',
      description: 'Trusting Allah, the mother of Hadhrat Musa (as) (Moses) placed her baby in a chest on the river, and Allah brought him back to her (Surah Al-Qasas 28:8, 28:14).',
    },
    {
      name:        'Mount Sinai — Egypt',
      image:       'game_editions/prophets-stories/images/landmarks/mount-sinai.jpg',
      description: 'Traditionally the Mount (At-Tur) where Allah spoke to Hadhrat Musa (as) and gave him the Torah. That is why he is called Kalimullah, "the one to whom Allah spoke".',
    },

    // ── The Holy Land & Damascus ─────────────────────────────────────────────
    {
      name:        'Hebron (Al-Khalil)',
      image:       'game_editions/prophets-stories/images/landmarks/hebron.jpg',
      description: 'The city is named after Hadhrat Ibrahim (as), Khalilullah, "the Friend of Allah". By tradition, he, Hadhrat Ishaq (as) and Hadhrat Ya\'qub (as) are buried at the Ibrahimi Mosque.',
    },
    {
      name:        'The Dead Sea',
      image:       'game_editions/prophets-stories/images/landmarks/dead-sea.jpg',
      description: 'The lowest place on land, so salty that you float. Tradition links the area to the people of Hadhrat Lut (as) (Lot), who were warned to give up their wrongdoing.',
    },
    {
      name:        'Al-Aqsa Mosque — Jerusalem',
      image:       'game_editions/prophets-stories/images/landmarks/al-aqsa.jpg',
      description: 'Al-Masjid al-Aqsa, "the Farthest Mosque", named in the Qur\'an in the story of the Isra\', the night journey of the Holy Prophet (sa) (Surah Bani Isra\'il 17:2). It was the first qibla.',
    },
    {
      name:        'The Jordan River',
      image:       'game_editions/prophets-stories/images/landmarks/jordan-river.jpg',
      description: 'By tradition, Hadhrat Yahya (as) (John) baptised people in this river and called them to repent. The Qur\'an praises him as kind to his parents and never proud (Surah Maryam 19:15).',
    },
    {
      name:        'Bethlehem',
      image:       'game_editions/prophets-stories/images/landmarks/bethlehem.jpg',
      description: 'By tradition the birthplace of Hadhrat Isa (as) (Jesus). The Qur\'an tells how Hadhrat Maryam was comforted under a palm tree with fresh dates and a stream (Surah Maryam 19:24–27).',
    },
    {
      name:        'Umayyad Mosque — Damascus',
      image:       'game_editions/prophets-stories/images/landmarks/umayyad-mosque.jpg',
      description: 'A hadith says the Messiah would descend "at the white minaret, east of Damascus" (Muslim). The Promised Messiah (as) explained this as a sign of his own coming, and had a white minaret built in Qadian, which lies east of Damascus.',
    },

    // ── Kashmir & Qadian ─────────────────────────────────────────────────────
    {
      name:        'Roza Bal — Srinagar, Kashmir',
      image:       'game_editions/prophets-stories/images/landmarks/roza-bal.jpg',
      description: 'The shrine of Yuz Asaf. The Promised Messiah (as) showed that Hadhrat Isa (as) survived the crucifixion, travelled east to find the lost tribes of Israel, and is buried here (Masih Hindustan Mein — Jesus in India).',
    },
    {
      name:        'Minaratul Masih — Qadian',
      image:       'game_editions/prophets-stories/images/landmarks/minaratul-masih.jpg',
      description: 'The white minaret next to Masjid Aqsa in Qadian. The Promised Messiah (as) laid its foundation stone on 13 March 1903, and it was completed in 1916, during the time of the second Khalifa.',
    },
  ],

  // ── Board background image ──────────────────────────────────────────────────
  BOARD_BACKGROUND: {
    image:          'game_editions/prophets-stories/images/backgrounds/desert-night.jpg',
    overlayOpacity: 0.55,
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
    finish:    { icon: '🕋', label: "Al-Ka'ba" },
    good_deed: { icon: '🌟', label: 'Good Deed',       color: '#2E7D32' },
    bad_deed:  { icon: '📖', label: 'Lesson to Learn', color: '#C62828' },
    landmark:  { icon: '🕌', label: 'Blessed Place',   color: '#F9A825' },
  },

  // ── Colour scheme (night sky and storybook gold) ────────────────────────────
  COLORS: {
    '--green':          '#283593',
    '--green-dark':     '#1A237E',
    '--green-light':    '#E8EAF6',

    '--blue':           '#1A237E',
    '--gold':           '#F9A825',
    '--danger':         '#C62828',

    '--bg':             '#F8F3E6',
    '--card':           '#FFFFFF',
    '--text':           '#1A1A1A',
    '--text-muted':     '#5A5A5A',
    '--border':         '#E6DCC3',

    '--c-start':        '#283593',
    '--c-finish':       '#F9A825',

    // Setup & End screen gradient (night sky → dusk)
    '--gradient-a':     '#0D1442',
    '--gradient-b':     '#283593',
    '--gradient-c':     '#B26A00',

    '--vp-a':           '#E8EAF6',
    '--vp-b':           '#F8F3E6',
    '--vp-c':           '#FFE0B2',

    '--deed-good-bg':   '#E8F5E9',
    '--deed-good-text': '#1B5E20',
    '--deed-bad-bg':    '#FFF3E0',
    '--deed-bad-text':  '#8D3A00',
  },

  // ── End-screen awards (G13) — rename any engine award (js/shared/config.js AWARDS)
  AWARDS: {
    quizMaster: { icon: '📚', title: 'Storyteller' },
    performer:  { icon: '🎭', title: 'Star of the Show' },
    goodDeeds:  { icon: '🌟', title: 'Helper of All' },
    badDeeds:   { icon: '📖', title: 'Still Learning' },
    explorer:   { icon: '🧭', title: "Traveller of the Prophets' Lands" },
    patience:   { icon: '🌱', title: 'Patient like Ayyub' },
  },

};
