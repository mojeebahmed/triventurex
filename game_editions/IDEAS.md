# Edition ideas

A backlog of possible Triventurex editions. Add new ideas at the bottom of the list, check each one against the **content target** below, and pick the next edition to build from the table.

How to build one: see [template/README.md](template/README.md).

---

## Content target (per edition)

An edition should have enough content that repeat play stays fresh, but not so much that it becomes two games in one.

| Content | Target | Why |
|---|---|---|
| Landmarks | **20+** | A medium/long board shows many of them; deeds jump to the previous/next one |
| Deed cards | **50+** (about half good, half bad), most with 2–3 effects | Same size as Swab Quest / Football Quest (52); multiple effects make the same card play differently |
| Action cards | **25+** across `act` / `explain` / `sound` | Drawn without repeats; 25 covers several games |
| Questions | **200+**, a good mix of `easy` and `hard`, `multi` and `open` | Asked-question tracking recycles when a difficulty runs out; 200 is several evenings without repeats |
| Categories | **3–5**, each with enough for **40–80 questions** | Players filter by topic. A category with fewer than ~30 questions runs dry fast when it's the only one selected |

### Sizing check

Ask these before choosing a theme:

1. **Too thin?** Can you name 20 distinct places/stops in a natural order? Can you write 200 questions *without* padding (e.g. "what colour is…" ×30)? Are there 25 things to act/explain/make a sound of?
2. **Too wide?** Do the categories have little to do with each other (e.g. space + inventions + human body)? Would a player who loves one category be bored by the rest? Could each half reach 200 questions on its own? → **split it** into two editions.
3. **Overlap?** Does it repeat another edition's content? Keep the shared part in one edition only.
4. **Lasting?** Will the answers still be right in 5 years? Avoid content that dates fast (charts, current celebrities, records that keep changing) or note the year in the question.
5. **Family-friendly?** Can a 7-year-old play the easy questions while adults get challenged by the hard ones?

Verdicts used below: ✅ right size · ⚠️ thin, needs widening · ✂️ too wide, split · 🔀 merge with another idea.

---

## How we build an edition

Each edition is built on its own branch (`feat/edition-<id>`) in five steps. Claude does the research and writing; Mojeeb approves each step before the next one starts.

1. **Outline**: categories › subcategories › topics with rough question counts, the 20+ landmarks (name + 2–3 sentence description), the look (colours, icon, `pointsName`, good/bad deed labels in `SPACE_INFO`, finish texts, award names). → approve
2. **Images**: one photo per landmark plus a board background (see *Images* below), and a `CREDITS.md`. → approve
3. **Questions**: written one category at a time (≈50 per batch) into `questions.csv`. Facts checked against at least two sources; the fact behind the answer goes in `note`. → review each batch
4. **Deeds and actions**: 50+ deeds with 2–3 effects each, 25+ edition actions.
5. **Check and play**: `npm run build:content <id>` → add to `editions.js` → `npm test` → play one offline and one network game → fix what was 🚩 marked → merge.

### Images

- **Real places** (cities, wonders, parks, planets): photos from [Wikimedia Commons](https://commons.wikimedia.org), which are free to reuse. Never random web images — they are usually copyrighted.
- **Fictional places** (fairy tales, myths): no photos exist. Use public-domain storybook illustrations from Commons, images made with an image generator from prompts in one shared style, or simple SVG illustrations.
- **Size**: resize and crop with macOS `sips` to the same shape, JPEG, about 100 KB each, saved as `images/landmarks/<kebab-name>.jpg`.
- **Credits**: CC BY / CC BY-SA images need attribution. Each edition keeps a `CREDITS.md` with file, title, author, licence and source link for every image.

### Avoid

- Facts that change (records, "the current…", number of moons) — or put the year in the question.
- Content that only works for one age group: `easy` should suit a 7-year-old, `hard` should challenge adults.
- Repeating another edition's content — note the overlap in the idea and keep it in one place.
- Reusing or renumbering question ids (asked-question tracking and 🚩 marks are stored by id).

---

## Overview

| # | Edition | Source | Verdict | Notes |
|---|---|---|---|---|
| 1 | Animal Safari | Claude + Gemini (*Wild Kingdom*) | ✅ | Huge topic, easy for kids. Keep the ocean out (→ Ocean Deep) |
| 2 | Space Explorer | Claude + Gemini (*Science & Innovation*, part) | ✅ | Strong journey (Earth → edge of the solar system) |
| 3 | World Tour | Claude + Gemini (*Global Trekker*) | ✅ | Best landmarks of any idea. Leave food to #6 |
| 4 | Dino Quest (Prehistoric) | Claude | ⚠️ → widened | Dinosaurs alone are thin for 200 questions; add fossils, ice age, early life |
| 5 | Fairy Tales & Stories | Claude | ✅ | Classic tales + fables + children's books |
| 6 | Food Around the World | Claude + Gemini (*Culinary World Tour*) | ✅ | Easiest action cards of all |
| 7 | Time Machine | Gemini | ✅ (hard-leaning) | History by era. Easy questions need care for kids |
| 8 | Movie Night | Gemini (*Cinephile & Pop Culture*) | ⚠️ | Dates fast; keep to family/animated films and classics |
| 9 | Inventions & Science Lab | Gemini (*Science & Innovation*, part) | ✂️ from Gemini's idea | Gemini's version is too wide — split into Space (#2), this, and Human Body (#10) |
| 10 | Human Body Adventure | Claude | ✅ | Journey through the body |
| 11 | Ocean Deep | Claude | ✅ | Journey down through the depth zones |
| 12 | Nordic Quest | Claude | ✅ | Sweden + Nordic countries |
| 13 | Myths & Legends | Claude | ✅ | Norse, Greek, Egyptian… |
| 14 | Planet Earth (Wild Weather) | Claude | ✅ | Volcanoes, weather, rivers, mountains |
| 15 | Sports Champions | Claude | ✅ | All sports except football (Football Quest exists) |
| 16 | Prophets' Stories (Kids) | Claude | ✅ | Kid-level companion to Swab Quest |
| 17 | Music Maestro | Claude | ⚠️ | Sound action cards are great; questions date fast if pop-heavy |

---

## 1. Animal Safari 🦁

*Merges Gemini's "Wild Kingdom".*

**Pitch:** an expedition through the world's habitats, from the savannah to the Arctic.
**Audience:** ages 5+, the most kid-friendly idea.
**Look:** jungle green, savannah gold, paw-print path.

**Categories (≈ questions):**
- Mammals (60): big cats, apes, pets, record holders
- Birds, reptiles & bugs (50): flight, migration, snakes, insects
- Habitats (50): savannah, rainforest, desert, Arctic, mountains
- Animal superpowers (40): camouflage, senses, speed, survival tricks

**Landmarks (20+):** Serengeti, Masai Mara, Okavango Delta, Sahara, Amazon Rainforest, Galápagos Islands, Borneo Rainforest, Himalayas, Gobi Desert, Australian Outback, Yellowstone, Rocky Mountains, Arctic Ice, Antarctica, Madagascar, Congo Basin, Kruger Park, Pantanal, Sundarbans, Bamboo Forest (pandas), Komodo Island

**Deeds:** good — *Rescued a baby turtle*, *Planted trees for orangutans*; bad — *Fed the monkeys your sandwich*, *Woke the sleeping lion*, *Lost the binoculars*.
**Actions:** act like an animal (no sound), make an animal's sound, explain an animal without saying its name.
**Sizing:** ✅ Plenty of content. **Overlap:** ocean animals belong to Ocean Deep (#11); keep only a few here.

---

## 2. Space Explorer 🚀

**Pitch:** a mission from the launch pad through the solar system and beyond.
**Audience:** ages 7+.
**Look:** deep navy, neon accents, orbit-line path, constellation background.

**Categories (≈ questions):**
- Solar system (70): planets, moons, the Sun, asteroids, comets
- Astronauts & missions (50): Apollo, ISS, rovers, famous astronauts
- Stars & galaxies (40): constellations, black holes, the Milky Way
- Space science (40): gravity, light-years, rockets, telescopes

**Landmarks (20+):** Launch Pad, Earth Orbit, ISS, The Moon, Sea of Tranquility, Mars, Olympus Mons, Phobos, Asteroid Belt, Jupiter, Great Red Spot, Europa, Saturn, Saturn's Rings, Titan, Uranus, Neptune, Pluto, Kuiper Belt, Voyager 1, James Webb Telescope, Milky Way Centre

**Deeds:** good — *Fixed the solar panel*, *Found water ice*; bad — *Forgot to refuel*, *Hit by space debris*, *Floated off during a spacewalk*.
**Actions:** act out a moonwalk / a rocket launch, explain gravity without saying "fall", make the sound of a rocket countdown.
**Sizing:** ✅ The journey order is natural (good for prev/next landmark deeds). Note the year on "current" facts (number of moons changes).

---

## 3. World Tour 🌍

*Merges Gemini's "Global Trekker".*

**Pitch:** a trip around the world, collecting passport stamps.
**Audience:** ages 7+; adults enjoy the hard questions.
**Look:** world-map board, passport-stamp tiles, flight-path lines, compass.

**Categories (≈ questions):**
- Countries & capitals (60)
- Flags & languages (40): "hello" in other languages, flag colours
- Wonders & landmarks (50): who built it, where is it
- Culture & customs (50): festivals, traditions, clothing, money

**Landmarks (20+):** Eiffel Tower, Big Ben, Colosseum, Leaning Tower of Pisa, Sagrada Família, Acropolis, Pyramids of Giza, Petra, Taj Mahal, Great Wall of China, Mount Fuji, Angkor Wat, Sydney Opera House, Christ the Redeemer, Machu Picchu, Chichén Itzá, Statue of Liberty, Grand Canyon, Niagara Falls, Kilimanjaro, Burj Khalifa, Table Mountain

**Deeds:** good — *Learned the local greeting*, *Caught a shortcut flight*; bad — *Missed the train*, *Lost your passport*, *Took the wrong bus*.
**Actions:** mime a landmark, say "hello" in another language, act out a local activity (skiing the Alps, eating with chopsticks).
**Sizing:** ✅ The richest landmarks of any idea. **Overlap:** food questions go to Food Around the World (#6), myths to #13.

---

## 4. Dino Quest 🦖 (widened: Prehistoric World)

**Pitch:** dig back through time, from the first life to the ice age.
**Audience:** ages 5+, a favourite topic for many kids.
**Look:** earthy browns and jungle greens, fossil tiles, footprint path.

**Categories (≈ questions):**
- Dinosaurs (80): famous species, meat- vs plant-eaters, records
- Fossils & palaeontology (40): how fossils form, famous finds, digs
- Before & after the dinosaurs (40): first life, sea monsters, flying reptiles, extinction
- Ice age & early humans (40): mammoths, sabre-tooth cats, cave paintings

**Landmarks (20+):** eras and dig sites — Primordial Ocean, Cambrian Reef, Triassic Desert, Jurassic Forest, Cretaceous Swamp, Hell Creek, Gobi Dig Site, Dinosaur Provincial Park, Jurassic Coast, Ghost Ranch, Patagonia Dig, Liaoning Feathered Fossils, Chicxulub Crater, Ice Age Tundra, La Brea Tar Pits, Lascaux Cave, Natural History Museum, Dino Nest Valley, Volcano Ridge, Mammoth Steppe

**Deeds:** good — *Found a complete fossil*, *Hid from the T-Rex*; bad — *Got chased by a raptor*, *Dropped the fossil*, *Stepped in a tar pit*.
**Actions:** roar like a T-Rex, walk like a Stegosaurus, explain "extinct" without saying it.
**Sizing:** ⚠️ Dinosaurs alone run out at ~100 good questions, so the edition is widened to the whole prehistoric world.

---

## 5. Fairy Tales & Stories 📖

**Pitch:** travel through storybook lands and meet famous characters.
**Audience:** ages 4+; the easiest edition for young players.
**Look:** pastel storybook colours, book-page tiles, a winding path.

**Categories (≈ questions):**
- Classic fairy tales (70): Grimm, Andersen, Perrault
- Fables (40): Aesop, the moral of the story
- Children's books (50): Astrid Lindgren, Roald Dahl, picture books
- Nursery rhymes & songs (40): finish the line, who's in it

**Landmarks (20+):** Gingerbread House, Beanstalk, Giant's Castle, Rapunzel's Tower, Three Bears' Cottage, Grandma's House, Big Bad Wolf's Woods, Sleeping Beauty's Castle, Little Mermaid's Rock, Snow Queen's Palace, Seven Dwarfs' Mine, Cinderella's Ball, Villa Villekulla, Lönneberga, Chocolate Factory, Hundred Acre Wood, Wonderland, Neverland, Emerald City, Narnia's Lamppost

**Deeds:** good — *Helped the Three Little Pigs*, *Found the glass slipper*; bad — *Woke the giant*, *Ate the poisoned apple*, *Followed the wolf's shortcut*.
**Actions:** act out a character, tell a story in three words, make the sound of a creaking door / a giant's footsteps.
**Sizing:** ✅ Check copyright for modern characters — names and questions are fine, but don't copy book text.

---

## 6. Food Around the World 🍕

*Merges Gemini's "Culinary World Tour".*

**Pitch:** a culinary journey through the world's food capitals.
**Audience:** ages 6+; everyone has an opinion on food.
**Look:** warm kitchen colours, recipe-card tiles, utensil icons.

**Categories (≈ questions):**
- National dishes (70): where it comes from, what's in it
- Fruit, veg & ingredients (50): spices, where they grow
- Cooking & kitchen (40): techniques, tools, science of cooking
- Sweets & food facts (40): desserts, records, healthy eating

**Landmarks (20+):** Naples (pizza), Bologna (pasta), Paris (croissants), Brussels (waffles), Valencia (paella), Istanbul (baklava), Marrakech (tagine), Cairo (koshari), Lahore (biryani), Mumbai (street food), Bangkok (pad thai), Tokyo (sushi), Seoul (kimchi), Beijing (dumplings), Mexico City (tacos), Lima (ceviche), New Orleans (gumbo), Stockholm (cinnamon buns), Addis Ababa (injera), Beirut (mezze)

**Deeds:** good — *Cooked for your neighbours*, *Mastered the secret recipe*; bad — *Burned the pancakes*, *Too much chilli!*, *Dropped the cake*.
**Actions:** act out cooking steps (flipping a pancake, kneading dough, rolling sushi), describe a dish only with taste words, make the sound of sizzling.
**Sizing:** ✅ Mind dietary/religious sensitivities in deed and question text (Swab Quest players will play this too).

---

## 7. Time Machine ⏳ (Gemini)

**Pitch:** jump through the eras, from ancient Egypt to the future.
**Audience:** ages 9+; harder for young kids.
**Look:** clockwork gears, parchment; each era of the board in its own colour.

**Categories (≈ questions):**
- Ancient world (60): Egypt, Greece, Rome, China, Mesopotamia
- Middle Ages & golden ages (50): castles, Islamic golden age, explorers
- Inventions & discoveries (40): what came first
- Modern times (50): flight, the Moon landing, the internet

**Landmarks (20+):** Stonehenge, Pyramids of Giza, Babylon, Great Wall, Athens, Rome, Colosseum, Petra, House of Wisdom (Baghdad), Alhambra, Viking Village, Medieval Castle, Timbuktu, Forbidden City, Renaissance Florence, Columbus' Ship, Industrial Revolution, Wright Brothers' Field, Apollo 11, Berlin Wall, Year 3000

**Deeds:** good — *Fixed the time machine*, *Met a famous inventor*; bad — *Stuck in the wrong century*, *Time machine ran out of power*.
**Actions:** freeze like an ancient statue, act out an invention being used for the first time, explain an old object without naming it.
**Sizing:** ✅ Lots of content; the work is writing *easy* questions kids can answer. **Overlap:** inventions also in #9 — keep them here as history, there as science.

---

## 8. Movie Night 🎬 (Gemini: "Cinephile & Pop Culture")

**Pitch:** a red-carpet walk through famous films and their worlds.
**Audience:** families; narrowed from Gemini's general pop culture.
**Look:** red carpet, film-strip path, gold and black.

**Categories (≈ questions):** animated films (70), family classics (50), film music & songs (40), behind the scenes (40).
**Landmarks:** famous fictional places — Emerald City, Hogwarts, Neverland, Arendelle, Pride Rock, Toy Box, Atlantis, Wonka's Factory, Monstropolis, Bikini Bottom, Hollywood Walk of Fame…
**Actions:** hum a film tune, act a famous scene, walk like a film character.
**Sizing:** ⚠️ Plenty of content, but it **dates fast** and needs regular updates, and characters/places are trademarked (fine for a private game; keep it private). Lower priority.

---

## 9. Inventions & Science Lab 🔬

*Gemini's "Science & Innovation" covered space, inventions, physics and the human body — four editions' worth. ✂️ Split into Space Explorer (#2), this edition, and Human Body (#10).*

**Pitch:** visit the world's great labs and workshops.
**Audience:** ages 8+.
**Look:** blueprint grid, neon lab colours, gadget icons.

**Categories (≈ questions):** inventors & inventions (60), everyday physics (50), chemistry & materials (40), "what happens if…" experiments (50).
**Landmarks (20+):** Archimedes' Bath, Al-Jazari's Workshop, Gutenberg's Press, Galileo's Tower, Newton's Apple Tree, Edison's Lab, Tesla's Tower, Curie's Lab, Wright Brothers' Field, Bell's Telephone, Nobel's Lab, CERN, Silicon Valley, Bletchley Park, NASA Mission Control, Volcano Experiment, Magnet Mountain, Lightning Rod, Rainbow Prism, Robot Factory
**Actions:** draw an invention with basic shapes, explain an everyday object without forbidden words, act out using an invention.
**Sizing:** ✅ after the split.

---

## 10. Human Body Adventure 🫀

**Pitch:** shrink down and travel through the body.
**Audience:** ages 6+; teaches healthy habits.
**Categories:** organs (60), senses (40), bones & muscles (40), health & food (50).
**Landmarks:** Mouth, Teeth, Throat, Stomach, Small Intestine, Liver, Heart, Arteries, Lungs, Brain, Eye, Ear, Nose, Skin, Skeleton, Muscles, Spine, Kidneys, Blood Cells, Fingertips.
**Deeds:** good — *Ate your vegetables*, *Slept 10 hours*; bad — *Skipped brushing teeth*, *Too much candy*.
**Actions:** act out a sneeze / a heartbeat, explain a body part without naming it.
**Sizing:** ✅ The body gives a natural route for the board.

---

## 11. Ocean Deep 🐙

**Pitch:** dive from the beach down to the deepest point on Earth.
**Categories:** sea creatures (80), ocean zones (40), coral reefs & coasts (40), ships & explorers (40).
**Landmarks:** Beach, Tide Pools, Coral Reef, Kelp Forest, Great Barrier Reef, Sunlight Zone, Shipwreck, Twilight Zone, Midnight Zone, Abyss, Hydrothermal Vents, Mariana Trench, Challenger Deep, Bermuda Triangle, Titanic Wreck, Galápagos, Antarctic Ice Shelf, Whale Highway, Sargasso Sea, Atlantis.
**Sizing:** ✅ The board goes deeper as you play. **Overlap:** take ocean animals out of Animal Safari.

---

## 12. Nordic Quest 🇸🇪

**Pitch:** a trip through Sweden and the Nordic countries.
**Categories:** places & nature (60), history & Vikings (50), traditions & food (40), famous Nordic people & inventions (50).
**Landmarks:** Stockholm, Gamla Stan, Vasa Museum, Skansen, Gothenburg, Malmö, Öresund Bridge, Gotland, Visby, Kiruna, Ice Hotel, Abisko, Lapland, Dalarna, Vimmerby, Oslo, Fjords, Copenhagen, Helsinki, Reykjavík, Northern Lights.
**Sizing:** ✅ A good choice for families in Sweden; could also be played in Swedish later.

---

## 13. Myths & Legends 🐉

**Pitch:** a quest through the worlds of ancient myths.
**Categories:** Norse (50), Greek & Roman (60), Egyptian (40), world legends (50) — dragons, King Arthur, Sinbad.
**Landmarks:** Asgard, Bifröst, Valhalla, Yggdrasil, Mount Olympus, the Labyrinth, Troy, Underworld, Atlantis, Camelot, Avalon, Valley of the Kings, Sphinx, El Dorado, Shangri-La, Dragon's Lair, Sinbad's Island, Loch Ness, Kraken's Sea, Phoenix Nest.
**Sizing:** ✅ Faith-sensitive families may want to skip it; keep the tone "stories", not belief.

---

## 14. Planet Earth (Wild Weather) 🌋

**Pitch:** explore the forces that shape the planet.
**Categories:** volcanoes & earthquakes (50), weather & climate (50), rivers, mountains & deserts (50), saving the planet (40).
**Landmarks:** Mount Everest, Mount Vesuvius, Yellowstone Geysers, Ring of Fire, Sahara, Amazon River, Nile, Victoria Falls, Grand Canyon, Dead Sea, Lake Baikal, Antarctica, Tornado Alley, Monsoon Coast, Iceland's Volcanoes, Aurora Skies, Great Rift Valley, Atacama Desert, Mariana Trench, Rainforest Canopy.
**Sizing:** ✅ Overlaps a little with World Tour and Ocean Deep; keep this one about nature's forces.

---

## 15. Sports Champions 🏅

**Pitch:** compete at the world's great sports venues.
**Categories:** Olympics (60), ball sports except football (50), winter sports (40), sport science & rules (40).
**Landmarks:** Olympia, Wimbledon, Madison Square Garden, Tour de France finish, Wembley, Augusta, Holmenkollen, Monaco Grand Prix, Lord's, Melbourne Park, Olympic Stadium Athens, Beijing Bird's Nest, Fenway Park, Le Mans, Vasaloppet, Kitzbühel, Boston Marathon, Daytona, Hockey Hall of Fame, Rio Maracanã.
**Sizing:** ✅ Keep football to Football Quest. Records change — note the year.

---

## 16. Prophets' Stories (Kids) 🕌

**Pitch:** a kid-level journey through the stories of the prophets, for families who play Swab Quest.
**Categories:** stories of the prophets (80), the Prophet Muhammad's (saw) life (50), Islamic manners & worship (50), the Qur'an for kids (40).
**Landmarks:** places from the stories — Ark of Nuh, Ka'ba, Zamzam, Mount Sinai, the Nile, Yusuf's Well, Cave of Hira, Mount Uhud, Masjid an-Nabawi, Ta'if, Qadian…
**Sizing:** ✅ Some content can be adapted from Swab Quest's easy questions — but keep the editions separate (different audience), and never reuse question ids across editions' tracking.

---

## 17. Music Maestro 🎵

**Pitch:** a tour through instruments, composers and music around the world.
**Categories:** instruments (60), classical & composers (40), world music (40), songs & musicals (40).
**Actions:** the best `sound` cards of any edition (hum, clap a rhythm, play air-instrument).
**Sizing:** ⚠️ Only fun if the questions stay away from current pop charts; for a faith-sensitive audience, music may not fit. Lower priority.

---

## Add a new idea

Copy this block:

```markdown
## N. Name 🙂

**Pitch:** one sentence.
**Audience:** ages …
**Look:** colours / path / tile style.

**Categories (≈ questions):** … (aim for 3–5, each 40–80)
**Landmarks (20+):** …
**Deeds:** good — …; bad — …
**Actions:** act / explain / sound ideas
**Sizing:** ✅ / ⚠️ / ✂️ / 🔀 and why
```

Then add a row to the overview table.
