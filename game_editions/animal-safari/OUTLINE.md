# Animal Safari 🦁 — outline (step 1)

Design notes for the Animal Safari edition. Step 1 of *How we build an edition* in [../IDEAS.md](../IDEAS.md): approve or change this, then step 2 (images) starts.

**Pitch:** an expedition through the world's wild places, from the savannah to the poles, collecting paw prints of the animals you meet.
**Audience:** ages 5+ for `easy` (the most kid-friendly edition), `hard` should still challenge adults.

---

## Look and words (`config.js`)

| Setting | Value |
|---|---|
| `editionName` / `editionIcon` | Animal Safari / 🦁 |
| `subtitle` | Collect paw prints on an expedition through the world's wild places. |
| `gameIdPrefix` | `AS` |
| `pointsName` | Paw Prints |
| `finishLabel` | Safari Lodge |
| `finishCelebration` | Back at the lodge with amazing photos! 📸 |
| `finishButtonLabel` | 🛖 Arrive at the lodge |
| `endScreenMessage` | Every explorer is back at the lodge! |
| Good deed (`SPACE_INFO.good_deed`) | 🌿 **Wildlife Hero** |
| Bad deed (`SPACE_INFO.bad_deed`) | 🐊 **Safari Mishap** |
| Landmark (`SPACE_INFO.landmark`) | 🏞️ **Reserve** |
| Colours | Primary acacia green `#558B2F` (dark `#33691E`, light `#DCEDC8`), accent savannah gold `#F9A825`, sunset orange `#E65100` in the setup gradient |
| Board background | A wide savannah photo (acacia trees, golden grass) from Wikimedia Commons, under a light overlay |
| Board mix | The standard mix from the template (same as Swab Quest) |

**Awards** (renamed engine awards): Quiz master → 🦉 *Wise Owl* · Performer → 🐒 *Cheeky Monkey* · Do-gooder → 🌿 *Wildlife Hero* · Trouble magnet → 🐊 *Croc Magnet* · Explorer → 🔭 *Safari Guide* · Big moment → 🦘 *Big Leap* · Lucky roller → 🐆 *Cheetah Speed* · Unluckiest roller → 🐌 *Snail Pace* · Patience award → 🦥 *Slow as a Sloth*.

---

## Questions — about 220

Mix: about 60% `easy` (younger players) / 40% `hard`, about 75% `multi` (tappable on phones) / 25% `open`.

| Category | Subcategories (≈ questions) | Total |
|---|---|---|
| 🦁 Mammals | Big cats & hunters (20) · Giants & grazers (15) · Apes, monkeys & more (15) · Pets & farm animals (10) | 60 |
| 🦜 Birds | Birds of the world (15) · Flight, nests & eggs (15) | 30 |
| 🐍 Reptiles, Frogs & Bugs | Reptiles (15) · Amphibians (8) · Insects & spiders (12) | 35 |
| 🌍 Habitats | Savannah & desert (10) · Rainforest (10) · Polar & mountains (10) · Rivers & wetlands (10) | 40 |
| ⚡ Animal Superpowers | Speed & strength (12) · Senses (8) · Camouflage & tricks (8) · Babies & families (7) | 35 |
| 🐙 Under the Sea | Sea creatures (20) — the small ocean side dish, under 10% (Ocean Deep can go deeper later) | 20 |
| | | **220** |

**Topic level:** where the animal lives — Africa, Asia, Americas, Europe, Oceania, Polar, Ocean, or Everywhere (pets, farm animals, animals found on many continents). Same idea as World Tour's continents, so families can filter by region.

Rules for writing:
- Kind and curious, not scary: hunting is mentioned as a fact of nature, never in gory detail. No hunting by people, no zoo/circus tricks, no animals as food.
- Facts that don't change: no "only N left in the wild" counts unless the question names the year.
- "Record" questions use settled records (fastest land animal: cheetah; biggest animal ever: blue whale).
- Reserves on the board get questions too ("Which animals cross the Mara River?").

---

## Landmarks — 26 wild places

Spread over every continent, chosen so they don't repeat World Tour's wonders. Each will get a Wikimedia Commons photo (ideally with its famous animal) in step 2.

### Africa
1. **Serengeti — Tanzania** — Endless grassy plains where more than a million wildebeest, with zebras and gazelles, travel in a giant circle every year — the Great Migration. Lions, cheetahs and hyenas follow them.
2. **Masai Mara — Kenya** — The northern end of the Great Migration. Every summer the herds have to cross the Mara River, where crocodiles are waiting.
3. **Ngorongoro Crater — Tanzania** — The bowl of a collapsed volcano, about 20 km wide, with a whole world of animals living inside: lions, elephants, hippos and rare black rhinos.
4. **Okavango Delta — Botswana** — A river that never reaches the sea: it spreads out into the Kalahari Desert and makes a huge green maze of channels full of elephants, hippos and crocodiles.
5. **Kruger National Park — South Africa** — One of Africa's biggest wildlife parks, home to the "Big Five": lion, leopard, elephant, rhino and buffalo.
6. **Bwindi Impenetrable Forest — Uganda** — A misty mountain rainforest where about half of the world's mountain gorillas live.
7. **Madagascar's forests** — An island where most animals live nowhere else on Earth, including lemurs, chameleons and the fossa.

### Asia
8. **Sundarbans — India & Bangladesh** — The world's largest mangrove forest, where Bengal tigers swim between the islands.
9. **Borneo Rainforest — Malaysia & Indonesia** — One of the oldest rainforests on Earth and home of the orangutan, whose name means "person of the forest".
10. **Wolong Panda Reserve — China** — Bamboo-covered mountains in Sichuan where giant pandas live and are protected.
11. **Komodo National Park — Indonesia** — Islands that are the home of the Komodo dragon, the biggest lizard in the world.
12. **Gobi Desert — Mongolia & China** — A cold, rocky desert where two-humped Bactrian camels and wild horses roam.
13. **Hemis National Park — Himalayas, India** — High, snowy mountains known as one of the best places to spot the shy snow leopard.

### The Americas
14. **Amazon Rainforest — South America** — The largest rainforest on Earth, home to jaguars, sloths, toucans, pink river dolphins and millions of insects.
15. **Galápagos Islands — Ecuador** — Volcanic islands where giant tortoises, marine iguanas and blue-footed boobies live. Charles Darwin's visit in 1835 helped him think about how animals change over time.
16. **Pantanal — Brazil** — The world's largest tropical wetland and one of the best places to see jaguars, capybaras and caimans.
17. **Monteverde Cloud Forest — Costa Rica** — A forest wrapped in clouds, full of sloths, hummingbirds and the bright green quetzal.
18. **Yellowstone National Park — USA** — The world's first national park (1872), with bison, grizzly bears, wolves — and steaming geysers.
19. **Everglades — USA** — A slow "river of grass" in Florida, the only place where alligators and crocodiles live side by side.
20. **Monarch Butterfly Reserve — Mexico** — Every winter millions of orange monarch butterflies fly thousands of kilometres here and cover the trees.

### Oceania
21. **Kangaroo Island — Australia** — An island where kangaroos, koalas, echidnas and sea lions can all be seen in one day.
22. **Daintree Rainforest — Australia** — One of the oldest rainforests in the world, home of the cassowary, a tall bird that cannot fly.
23. **Great Barrier Reef — Australia** — The largest coral reef system in the world, full of turtles, clownfish and colourful corals (our small "under the sea" stop).

### Europe & the poles
24. **Białowieża Forest — Poland & Belarus** — One of the last ancient forests in Europe, where European bison roam free again.
25. **Svalbard — Norway** — Arctic islands where polar bears, walruses and Arctic foxes live, with the midnight sun in summer.
26. **Antarctica** — The coldest place on Earth. Emperor penguins huddle together through the dark winter to keep their eggs warm.

**Spares:** Etosha (Namibia), Kakadu (Australia), Ranthambore (India), Churchill (Canada, polar bears), Scottish Highlands, Danube Delta, Sahara (fennec fox, camels).

*Facts above are checked against sources again when they go into `config.js`.*

---

## Deeds — 56 (28 good / 28 bad), 2–3 effects each

| 🌿 Wildlife Hero (examples) | 🐊 Safari Mishap (examples) |
|---|---|
| You helped a baby turtle reach the sea | Your jeep got stuck in the mud |
| You planted trees for the orangutans | A cheeky monkey stole your hat |
| You waited quietly and saw a leopard! | You shouted and scared all the animals away |
| You picked up litter at the waterhole | You forgot your binoculars at the lodge |
| A ranger showed you a secret lookout | An elephant is blocking the road — wait! |
| You spotted the Big Five in one day | You fell asleep and missed the lions |

Effects: the usual mix (points, move forward/back, next/previous **reserve**, extra turn, skip turn, all players gain/lose, protection — *a ranger by your side*). `{landmark}` cards, e.g. *"A light plane flies you straight to {landmark}!"*

---

## Action cards — 25+ edition cards (plus the 40 general ones)

- 🎭 **Act:** move like a penguin / a kangaroo / a crab, a gorilla beating its chest, a chameleon catching a fly, a sloth doing everything slowly.
- 💬 **Explain:** *Camouflage* (don't say: hide, colour, blend), *Hibernate*, *Migration*, *Nocturnal*, *Herbivore*, *Endangered*.
- 🔊 **Sound:** a lion's roar, a wolf howling, an elephant trumpeting, a hyena laughing, a frog chorus at night.

---

## Open questions for Mojeeb

1. Points name *Paw Prints* and finish *Safari Lodge* — OK?
2. Topic level = where the animal lives (Africa, Asia, … Polar, Ocean, Everywhere) — OK?
3. Easy questions aimed at ages 5+ (World Tour aimed at 7+) — OK, or the same 7+?
4. Include pets & farm animals (10 questions) — fun for the youngest players, but not very "safari". Keep?
