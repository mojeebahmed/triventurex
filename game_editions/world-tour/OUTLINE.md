# World Tour 🌍 — outline (step 1)

Design notes for the World Tour edition (step 1 of *How we build an edition* in [../IDEAS.md](../IDEAS.md)). **Status: built.** The final content is in the CSV files and `config.js`; where they differ from this plan, they win (56 deeds instead of 52, three landmark facts reworded after checking sources).

**Pitch:** a trip around the world, collecting passport stamps at famous wonders.
**Audience:** ages 7+ for `easy`; `hard` should challenge adults.

---

## Look and words (`config.js`)

| Setting | Value |
|---|---|
| `editionName` / `editionIcon` | World Tour / 🌍 |
| `subtitle` | Collect passport stamps on a trip around the world. |
| `gameIdPrefix` | `WT` |
| `pointsName` | Stamps |
| `finishLabel` | Home Again |
| `finishCelebration` | Welcome home, world traveller! 🧳 |
| `finishButtonLabel` | 🏠 Land back home |
| `endScreenMessage` | Every traveller is home again! |
| Good deed (`SPACE_INFO.good_deed`) | ✈️ **Smooth Travels** |
| Bad deed (`SPACE_INFO.bad_deed`) | 🧳 **Travel Trouble** |
| Landmark (`SPACE_INFO.landmark`) | 📍 **Wonder** |
| Colours | Primary ocean teal `#00695C` (dark `#004D40`, light `#B2DFDB`), accent sunset amber `#FFB300`, passport navy `#1A237E` for the second colour |
| Board background | A public-domain vintage world map from Wikimedia Commons |

**Awards** (renamed engine awards): Quiz master → 🧠 *Know-it-all Navigator* · Performer → 🎭 *Street Performer* · Do-gooder → 🤝 *Friendly Traveller* · Trouble magnet → 🧳 *Lost Luggage* · Explorer → 🗺️ *Globetrotter* · Patience award → ⏳ *Delayed Flight*.

---

## Questions — about 220

Mix: about 55% `easy` / 45% `hard`, about 70% `multi` (tappable on phones) / 30% `open`.

| Category | Subcategories (≈ questions) | Total |
|---|---|---|
| 🏙️ Countries & Capitals | Capitals (30) · Countries & borders (15) · Biggest, smallest & highest (15) | 60 |
| 🚩 Flags & Languages | Flags (25) · Languages & greetings (20) | 45 |
| 🏛️ Wonders & Nature | Famous buildings (25) · Natural wonders (20) · Ancient wonders (10) | 55 |
| 🎎 Culture & Customs | Festivals & traditions (15) · Money & everyday life (15) · Sports & games (10) | 40 |
| 🍜 A Taste of the World | Dishes and where they come from (20) — the small food side dish, under 10% | 20 |
| | | **220** |

**Topic level:** the continent (Europe, Africa, Asia, Americas, Oceania, World). So a question is e.g. *Countries & Capitals › Capitals › Europe*. Players can then filter to "capitals only" or to one continent's topics.

Rules for writing:
- Only facts that don't change. "Tallest" and "biggest" questions name the year (*"When it opened in 2010, …"*) or use facts that are settled (largest country: Russia; smallest: Vatican City).
- Wonders on the board get questions too, so landing on one and later being asked about it connects.
- No questions that need a picture (flag questions describe the colours and shapes in words).

---

## Landmarks — 26

Spread over every continent. Each one will get a Wikimedia Commons photo in step 2.

### Europe
1. **Eiffel Tower — Paris** — Built for the 1889 World's Fair in Paris, the iron tower is over 320 metres tall. It was the tallest structure in the world until 1930, and it gets a fresh coat of paint about every seven years.
2. **Colosseum — Rome** — This giant amphitheatre opened almost 2,000 years ago, in AD 80. Around 50,000 people came to watch gladiator contests and shows here. It is still the largest amphitheatre ever built.
3. **Big Ben — London** — "Big Ben" is really the name of the huge bell inside the clock tower; the tower itself was renamed the Elizabeth Tower in 2012. The clock has kept time over London since 1859.
4. **Sagrada Família — Barcelona** — Architect Antoni Gaudí designed this church, and building began in 1882. More than 140 years later it is still not completely finished! Its tallest tower was planned for 2026, 100 years after Gaudí's death.
5. **Acropolis — Athens** — A rocky hill above Athens crowned by the Parthenon, a temple built about 2,500 years ago for the goddess Athena. It is a symbol of ancient Greece, where democracy was born.
6. **Neuschwanstein Castle — Bavaria** — King Ludwig II of Bavaria built this fairy-tale castle in the 1800s. It helped inspire the castle in Disney's *Sleeping Beauty*.

### Africa
7. **Pyramids of Giza — Egypt** — The Great Pyramid is about 4,500 years old and was the tallest building made by people for almost 4,000 years. It is the only one of the Seven Wonders of the Ancient World still standing.
8. **Mount Kilimanjaro — Tanzania** — Africa's highest mountain, 5,895 metres tall. It is a sleeping volcano, and even though it is close to the equator, its top has snow and ice.
9. **Victoria Falls — Zambia & Zimbabwe** — One of the largest waterfalls in the world. Its local name, *Mosi-oa-Tunya*, means "the smoke that thunders" — you can see its spray from far away.
10. **Table Mountain — Cape Town** — A mountain with a flat top, about 3 km wide, looking over Cape Town. When clouds spill over it, people say the "tablecloth" is on.

### Asia & the Middle East
11. **Petra — Jordan** — A city carved straight into rose-red cliffs by the Nabataean people more than 2,000 years ago. Its most famous building, the Treasury, is cut out of a single rock face.
12. **Taj Mahal — Agra** — Mughal emperor Shah Jahan built this white marble tomb in the 1600s in memory of his wife, Mumtaz Mahal. Its marble seems to change colour from pink in the morning to gold at sunset.
13. **Great Wall of China** — Built and rebuilt over more than 2,000 years, the wall and its branches stretch for thousands of kilometres. A popular myth says you can see it from the Moon — you can't!
14. **Mount Fuji — Japan** — Japan's highest mountain, 3,776 metres tall, with an almost perfect cone shape. It is a volcano, and its snowy top is one of the most famous sights in Japan.
15. **Angkor Wat — Cambodia** — Built in the 1100s, it is the largest religious monument in the world. It is so important to Cambodia that it appears on the country's flag.
16. **Burj Khalifa — Dubai** — When it opened in 2010, this 828-metre skyscraper became the tallest building in the world. It has more than 150 floors.
17. **Hagia Sophia — Istanbul** — Finished in the year 537, its giant dome amazed the world for centuries. It has been a church, a mosque, a museum and is a mosque again today.

### Oceania
18. **Sydney Opera House — Sydney** — Its roofs look like white sails on the harbour. Designed by Danish architect Jørn Utzon, it opened in 1973.
19. **Uluru — Australia** — A huge sandstone rock rising from the desert in the middle of Australia. It is sacred to the Anangu, its traditional owners, and glows red at sunset.
20. **Moai of Rapa Nui — Easter Island** — Nearly 900 giant stone statues (many with bodies buried!) carved by the Rapa Nui people. The island is one of the most remote places on Earth where people live.

### The Americas
21. **Statue of Liberty — New York** — A gift from France to the United States, opened in 1886. It is made of copper, which turned green over the years.
22. **Grand Canyon — Arizona** — Carved by the Colorado River over millions of years, it is about 1.8 km deep in places. Its rock layers show almost two billion years of Earth's history.
23. **Niagara Falls — USA & Canada** — Three waterfalls on the border between the USA and Canada. Boats take visitors right into the spray at the bottom.
24. **Chichén Itzá — Mexico** — A great city of the Maya. Its pyramid, El Castillo, has 365 steps — one for each day of the year.
25. **Machu Picchu — Peru** — An Inca city built in the 1400s high in the Andes mountains. It was hidden from most of the world until 1911.
26. **Christ the Redeemer — Rio de Janeiro** — This 30-metre statue has watched over Rio from the top of Corcovado mountain since 1931. Its arms stretch about 28 metres wide.

**Spares** (if a photo or fact doesn't work out): St Basil's Cathedral (Moscow), Forbidden City (Beijing), Golden Gate Bridge (San Francisco), Leaning Tower of Pisa, Iguazu Falls, Stonehenge, Mount Everest.

*Facts above are checked against sources again when they go into `config.js`.*

---

## Deeds — 56 (28 good / 28 bad), 2–3 effects each

| ✈️ Smooth Travels (examples) | 🧳 Travel Trouble (examples) |
|---|---|
| You learned the local greeting — the locals love it | You missed your train |
| A friendly local showed you a shortcut | You left your passport at the hotel |
| You caught an earlier flight | Your luggage went to the wrong country |
| You helped a lost tourist find their way | You got on the bus going the wrong way |
| Free upgrade to first class! | Your flight was delayed by a storm |
| You packed light and moved fast | You forgot to charge your phone — no map! |

Effects: the usual mix (points, move forward/back, next/previous **wonder**, extra turn, skip turn, all players gain/lose, protection — *travel insurance*). `{landmark}` cards, e.g. *"Your tour bus takes you straight to {landmark}!"*

---

## Action cards — 25+ edition cards (plus the 40 general ones)

- 🎭 **Act:** mime a wonder (the Statue of Liberty, the Leaning Tower), pack a suitcase in a hurry, eat with chopsticks, ride a camel, ski down the Alps.
- 💬 **Explain:** *Passport* (don't say: travel, photo, border), *Airport*, *Volcano*, *Pyramid*, *Jet lag*.
- 🔊 **Sound:** a busy airport, a waterfall, a city traffic jam, a camel, a ship's horn.

---

## Decisions

Approved as written: the continent is the *topic*, points are *Stamps*, finish is *Home Again*, Hagia Sophia's history is included.
