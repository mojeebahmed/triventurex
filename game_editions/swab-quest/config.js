/**
 * game_editions/swab-quest/config.js
 *
 * Edition configuration for "Swab Quest" — the first Triventurex edition.
 *
 * HOW EDITION LOADING WORKS:
 *   This file sets window.EDITION_CONFIG which the engine merges into CONFIG
 *   at load time, so edition values override engine defaults without touching
 *   engine code.
 *
 * TO CREATE A NEW EDITION:
 *   1. Copy this folder (game_editions/swab-quest/) to game_editions/<your-edition>/
 *   2. Edit config.js, questions.js, deeds.js and replace images.
 *   3. Add an entry to game_editions/editions.js.
 *   That's it — engine code is unchanged.
 */

window.EDITION_CONFIG = {

  // ── Brand identity ──────────────────────────────────────────────────────────
  GAME: {
    engineName:   'Triventurex',
    themeName:    'Swab Quest',
    themeIcon:    '🕌',
    subtitle:     'Collect Sawab points on your journey from start to finish.',
    gameIdPrefix: 'TX',
    pointsName:   'Sawab',   // replaces the engine default 'pts' everywhere in the UI
    finishLabel:       "Al-Ka'ba, Mecca",
    finishCelebration: 'Alhamdulillah! MashaAllah! 🌙',
    finishButtonLabel: '🎉 Alhamdulillah!',
    endScreenMessage:  'All players have reached Mecca!',
  },

  // ── Landmarks ───────────────────────────────────────────────────────────────
  // `image` path is relative to index.html.
  // `description` is shown in the landing modal and the info popup.
  LANDMARKS: [
    // ── Ahmadiyya landmarks ──────────────────────────────────────────────────
    {
      name:        'Aqsa Mosque — Rabwah',
      image:       'game_editions/swab-quest/images/landmarks/aqsa-mosque-rabwah.jpg',
      description: 'The Aqsa Mosque in Rabwah, Pakistan is the largest mosque of the Ahmadiyya Muslim Community. Its foundation stone was laid in 1966 and it was inaugurated on 31 March 1972 by Hazrat Mirza Nasir Ahmad (rh), the Third Khalifa. It can accommodate up to 20,000 worshippers.',
    },
    {
      name:        'Fazal Mosque — London',
      image:       'game_editions/swab-quest/images/landmarks/fazal-mosque-london.jpg',
      description: 'Baitul Fazl (House of Grace) in Southfields, London, was inaugurated in 1926 — the first purpose-built mosque in Western Europe. It serves as the UK headquarters of the Ahmadiyya Muslim Community and is a Grade II listed building.',
    },
    {
      name:        'Mubarak Mosque — Tilford',
      image:       'game_editions/swab-quest/images/landmarks/mubarak-mosque-tilford.jpg',
      description: 'The Mubarak Mosque stands at the international headquarters of the Ahmadiyya Muslim Community in Tilford, Surrey (known as Islamabad). It was inaugurated on 17 May 2019 by Hazrat Mirza Masroor Ahmad (aba), the Fifth Khalifa, and is the spiritual centre of the global Ahmadiyya community.',
    },
    {
      name:        'Minarat-ul-Masih — Qadian',
      image:       'game_editions/swab-quest/images/landmarks/minarat-ul-masih-qadian.jpg',
      description: 'The Minarat-ul-Masih (Minaret of the Messiah) rises in Qadian, India — the birthplace of the Ahmadiyya Muslim Community. Its construction was prophesied by the Promised Messiah, Hazrat Mirza Ghulam Ahmad (as), as a heavenly sign. It stands at the heart of the community\'s holiest site in India.',
    },
    {
      name:        'Masjid Mubarak — Qadian',
      image:       'game_editions/swab-quest/images/landmarks/masjid-mubarak-qadian.jpg',
      description: 'Masjid Mubarak (the Blessed Mosque) in Qadian, India, is the personal mosque of Hazrat Mirza Ghulam Ahmad (as), the Promised Messiah and founder of the Ahmadiyya Muslim Community. He led prayers here and it is one of the most revered sites for Ahmadi Muslims worldwide.',
    },
    {
      name:        'Baitul Futuh — London',
      image:       'game_editions/swab-quest/images/landmarks/baitul-futuh-london.jpg',
      description: 'Baitul Futuh (House of Victories) in Morden, London, was inaugurated in 2003 by Hazrat Mirza Masroor Ahmad (aba). With a capacity of over 10,000, it was for many years the largest mosque in Western Europe. The name reflects the remarkable growth of the Ahmadiyya Muslim Community across the world.',
    },
    {
      name:        'Baitul Islam — Vaughan, Canada',
      image:       'game_editions/swab-quest/images/landmarks/baitul-islam-vaughan.jpg',
      description: 'Baitul Islam (House of Islam) in Vaughan, Ontario, was inaugurated in 1992 and is the first Ahmadiyya mosque built in North America. It serves as the national headquarters of Ahmadiyya Muslim Jama\'at Canada and stands as a symbol of the community\'s growth on the continent.',
    },
    {
      name:        'Nusrat Jehan Mosque — Copenhagen',
      image:       'game_editions/swab-quest/images/landmarks/nusrat-jehan-mosque-copenhagen.jpg',
      description: 'The Nusrat Jehan Mosque in Copenhagen, Denmark, was inaugurated in 1967 — the first mosque built in Scandinavia. It was founded through the vision of Hazrat Mirza Nasir Ahmad (rh), the Third Khalifa, and named after his mother. It remains a landmark of the Ahmadiyya presence in Northern Europe.',
    },
    {
      name:        'Masjid Tahir — Koblenz',
      image:       'game_editions/swab-quest/images/landmarks/masjid-tahir-koblenz.jpg',
      description: 'The Tahir Moschee (Tahir Mosque) in Koblenz is the first and most prominent traditional Islamic house of worship built in the city of Koblenz, located in the German state of Rhineland-Palatinate. The mosque is widely recognized for its robust interfaith dialogue and community outreach.',
    },
    {
      name:        'Masjid Aqsa — Qadian',
      image:       'game_editions/swab-quest/images/landmarks/masjid-aqsa-qadian.jpg',
      description: 'Masjid Aqsa in Qadian, India, was built by the Promised Messiah, Hazrat Mirza Ghulam Ahmad (as), and is one of the oldest and most sacred mosques of the Ahmadiyya Muslim Community. It is the site of the historic Jalsa Salana (Annual Convention) gatherings held in Qadian every year.',
    },
    // ── General Muslim landmarks ─────────────────────────────────────────────
    {
      name:        'Masjid Al-Aqsa — Jerusalem',
      image:       'game_editions/swab-quest/images/landmarks/masjid-al-aqsa-jerusalem.jpg',
      description: 'Al-Masjid Al-Aqsa (the Furthest Mosque) in Jerusalem is the third holiest site in Islam. It is mentioned in the Holy Quran as the destination of the Night Journey (Isra) of the Prophet Muhammad ﷺ. The compound, known as Haram al-Sharif, holds immense spiritual significance for Muslims everywhere.',
    },
    {
      name:        'Dome of the Rock — Jerusalem',
      image:       'game_editions/swab-quest/images/landmarks/dome-of-the-rock-jerusalem.jpg',
      description: 'The Dome of the Rock (Qubbat al-Sakhra) in Jerusalem, completed in 691 CE by Caliph Abd al-Malik, is one of the oldest and most iconic Islamic monuments. It enshrines the sacred rock from which the Prophet Muhammad ﷺ is believed to have ascended to the heavens during the Night Journey (Mi\'raj).',
    },
    {
      name:        'Masjid Al-Nabawi — Madinah',
      image:       'game_editions/swab-quest/images/landmarks/masjid-nabwi-madinah.jpg',
      description: 'Al-Masjid An-Nabawi (the Prophet\'s Mosque ﷺ) in Madinah, Saudi Arabia, is the second holiest site in Islam. Built by the Prophet Muhammad ﷺ himself after the Hijra, it houses his blessed tomb beneath the iconic Green Dome. Praying here carries the reward of one thousand prayers compared to any other mosque.',
    },
    {
      name:        "Al-Ka'ba — Makkah",
      image:       'game_editions/swab-quest/images/landmarks/khana-kaba-makkah.jpg',
      description: "The Holy Ka'ba in Makkah is the most sacred site in Islam and the focal point of Hajj and Umrah. Muslims worldwide face towards it in every prayer. Built by Prophet Ibrahim (as) and his son Ismail (as), the Quran calls it Baytullah — the House of Allah.",
    },
    {
      name:        'Masjid Quba — Madinah',
      image:       'game_editions/swab-quest/images/landmarks/masjid-quba-madinah.jpg',
      description: 'Masjid Quba on the outskirts of Madinah was the very first mosque built in Islam — laid by the Prophet Muhammad ﷺ himself upon his arrival after the Hijra in 622 CE. The Prophet ﷺ said that praying two rak\'ahs here carries the reward of an Umrah.',
    },
    {
      name:        "Masjid al-Haram — Makkah",
      image:       'game_editions/swab-quest/images/landmarks/masjid-al-haram-makkah.jpg',
      description: "Al-Masjid al-Haram (the Grand Mosque) in Makkah is the largest mosque in the world and surrounds the Holy Ka'ba. It is the primary destination of the Hajj pilgrimage and can accommodate over two million worshippers. Every Muslim who is able is obligated to visit at least once in their lifetime.",
    },
    {
      name:        'Sultan Ahmed Mosque — Istanbul',
      image:       'game_editions/swab-quest/images/landmarks/sultan-ahmed-mosque-istanbul.jpg',
      description: 'The Sultan Ahmed Mosque (Blue Mosque) in Istanbul, Turkey, was built between 1609 and 1616 during the reign of Sultan Ahmed I. Renowned for its six minarets and stunning interior of hand-painted blue Iznik tiles, it is one of the most visited Islamic sites in the world.',
    },
    {
      name:        'Hassan II Mosque — Casablanca',
      image:       'game_editions/swab-quest/images/landmarks/hassan-ii-mosque-casablanca.jpg',
      description: 'The Hassan II Mosque in Casablanca, Morocco, completed in 1993, is the largest mosque in Africa and the seventh largest in the world. Its minaret, at 210 metres, is the tallest religious structure on earth. The mosque is built partly over the Atlantic Ocean, inspired by the Quranic verse: "His throne was on water."',
    },
    {
      name:        'Umayyad Mosque — Damascus',
      image:       'game_editions/swab-quest/images/landmarks/umayyad-mosque-damascus.jpg',
      description: 'The Umayyad Mosque (Great Mosque of Damascus) in Syria, completed in 715 CE, is one of the oldest and most magnificent mosques in the world. It is believed to enshrine the shrine of Prophet Yahya (John the Baptist) (as) and is a landmark of early Islamic architecture and history.',
    },
    {
      name:        'Al-Azhar Mosque — Cairo',
      image:       'game_editions/swab-quest/images/landmarks/al-azhar-mosque-cairo.jpg',
      description: 'Al-Azhar Mosque in Cairo, Egypt, was founded in 970 CE by the Fatimid dynasty. It is home to Al-Azhar University, the oldest continuously operating university in the world and a leading centre of Islamic scholarship. For over a thousand years it has shaped Islamic thought and jurisprudence.',
    },
  ],

  // ── Board background image ──────────────────────────────────────────────────
  // Set image to null to use the CSS gradient fallback only.
  BOARD_BACKGROUND: {
    image:          'game_editions/swab-quest/images/backgrounds/game-bg-2.jpg',
    overlayOpacity: 0.85,
    size:           'cover',
    position:       'center',
    blur:           0,
  },

  // ── Space distribution overrides (optional) ─────────────────────────────────
  // Ratios for each non-question space type. Questions always fill whatever
  // space remains after all other types are counted — no 'question' key needed.
  // Can be flat (same for all lengths) or keyed by 'short'/'medium'/'long'.
  // Omit entirely to use the engine defaults from js/config.js.
  SPACE_DISTRIBUTION: {
    short: {
      action:    0.10,
      good_deed: 0.10,
      bad_deed:  0.10,
      landmark:  0.08,
      skip:      0.05,
    },
    medium: {
      action:    0.10,
      good_deed: 0.10,
      bad_deed:  0.10,
      landmark:  0.08,
      skip:      0.05,
    },
    long: {
      action:    0.12,
      good_deed: 0.10,
      bad_deed:  0.10,
      landmark:  0.08,
      skip:      0.05,
    },
  },

  // ── Space type overrides ────────────────────────────────────────────────────
  // Optional — only specify types whose icon, label or colour differs from
  // the engine defaults in config.js SPACE_INFO.
  // The 'finish' label says "Finish" for this theme — other themes can change it.
  SPACE_INFO: {
    finish: { icon: '🕌', label: 'Finish' },
    good_deed: { icon: '🌟', label: 'Good Deed',  color: '#2E7D32' },
    bad_deed:  { icon: '💢', label: 'Bad Deed',  color: '#C62828' },
  },

  // ── Colour scheme ───────────────────────────────────────────────────────────
  // CSS custom properties applied via _applyTheme() in game.js.
  // All values here override the fallbacks in styles.css :root.
  THEME: {
    // Primary brand colour (Islamic green)
    '--green':          '#2E7D32',
    '--green-dark':     '#1B5E20',
    '--green-light':    '#d4f3d7',

    // Secondary / accent
    '--blue':           '#1565C0',
    '--gold':           '#F9A825',
    '--danger':         '#C62828',

    // UI surfaces
    '--bg':             '#F0EBE0',
    '--card':           '#FFFFFF',
    '--text':           '#1A1A1A',
    '--text-muted':     '#666666',
    '--border':         '#E0E0E0',

    // Fixed space colours (start / finish)
    '--c-start':        '#00695C',
    '--c-finish':       '#FFD700',

    // Setup & End screen gradient
    '--gradient-a':     '#5c93d2',
    '--gradient-b':     '#f3a174',
    '--gradient-c':     '#f5d580',

    // Board viewport fallback gradient (no bg image)
    '--vp-a':           '#C8E6C9',
    '--vp-b':           '#B2DFDB',
    '--vp-c':           '#C5CAE9',

    // Deed card result colours
    '--deed-good-bg':   '#E8F5E9',
    '--deed-good-text': '#1B5E20',
    '--deed-bad-bg':    '#FFEBEE',
    '--deed-bad-text':  '#C62828',
  },

};
