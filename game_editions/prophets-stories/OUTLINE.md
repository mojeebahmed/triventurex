# Prophets' Stories 📖 — outline (step 1)

Design notes for the Prophets' Stories edition. Step 1 of *How we build an edition* in [../IDEAS.md](../IDEAS.md): approve or change this, then step 2 (images) starts.

**Pitch:** a journey through the stories of the prophets, from Hadhrat Adam (as) to the Holy Prophet Muhammad (sa) and the Promised Messiah (as), visiting the places where the stories happened.
**Audience:** families who play Swab Quest; ages 5+ to adults in a good mix, with the stories told for children.

## Decisions already made (2026-10-18)

| Topic | Decision |
|---|---|
| Perspective | **Ahmadiyya** understanding, as in Swab Quest (e.g. Hadhrat Isa (as) survived the crucifixion and died in Kashmir; miracles explained as the Promised Messiah (as) explained them) |
| Qur'an references | Surah name + number with **Bismillah counted as verse 1** (as in Ahmadiyya Qur'an editions), e.g. *Surah Hud 11:45* for the Ark resting on Judi |
| Prophets | All prophets named in the Qur'an, the Holy Prophet Muhammad (sa), the Promised Messiah (as), and prophets known from hadith and other Islamic sources |
| Names | Swab Quest style: **Hadhrat Nuh (as) (Noah)** — English name in brackets where it helps; *the Holy Prophet Muhammad (sa)*, *the Promised Messiah (as)*, companions with (ra) |

## Content rules (respect first)

- **No pictures of people.** Landmark photos show places only, never prophets or companions (no paintings or illustrations of them).
- **Nobody plays a prophet.** Action cards act out animals, objects and events from the stories (the Ark, the whale, the spider's web), never a prophet himself.
- **Every question has a source** in its `note`: Surah:verse (Bismillah = 1), a hadith collection, or a book of the Promised Messiah (as) / the Khulafa. Where something comes from tradition rather than the Qur'an, the question says so ("according to tradition…").
- **Stories for children:** told kindly; punishments of past nations are mentioned as lessons, not in frightening detail.
- **Review before play:** the questions should be checked by someone knowledgeable (Mojeeb, and ideally a local missionary/murabbi) before the edition goes live. Claude is not a religious authority; the sources in the notes make that check quick.

---

## Look and words (`config.js`) — suggestions

| Setting | Value |
|---|---|
| `editionName` / `editionIcon` | Prophets' Stories / 📖 |
| `subtitle` | Travel through the stories of the prophets and collect Noor. |
| `gameIdPrefix` | `PS` |
| `pointsName` | **Noor** ✨ (light) |
| `finishLabel` | **Qadian** — the town of the Promised Messiah (as), where the chain of stories reaches our time |
| `finishCelebration` | You have travelled through the stories of the prophets! ✨ |
| `finishButtonLabel` | 🕌 Arrive in Qadian |
| Good deed (`SPACE_INFO.good_deed`) | 🌟 **Good Deed** — actions inspired by the prophets (sharing like Hadhrat Ibrahim (as), patience like Hadhrat Ayyub (as)) |
| Bad deed (`SPACE_INFO.bad_deed`) | 📖 **Lesson to Learn** — a kinder name for kids |
| Landmark (`SPACE_INFO.landmark`) | 🕌 **Blessed Place** |
| Colours | Night-sky navy `#1A237E` with warm gold `#F9A825` and sand `#F8F3E6`, like an old storybook |
| Board background | A photo of desert dunes under a starry sky (Commons), with a light overlay |
| Board mix | The standard mix from the template (same as Swab Quest) |

**Awards:** Quiz master → 📚 *Storyteller* · Performer → 🎭 *Star of the Show* · Do-gooder → 🌟 *Helper of All* · Trouble magnet → 📖 *Still Learning* · Explorer → 🧭 *Traveller of the Prophets' Lands* · Patience award → 🌱 *Patient like Ayyub*.

---

## Questions — about 220

Mix: about 55% `easy` / 45% `hard`, about 75% `multi` / 25% `open`. **Category** = an era of the stories, **subcategory** = the prophet, **topic** = *Story*, *Miracles & signs* or *Prayers & lessons*. So families can play "only Hadhrat Musa (as)" or "only stories" with the topic filter.

| Category | Prophets (subcategories) | ≈ |
|---|---|---|
| 🌍 From Adam to Nuh | Adam, Idris, Nuh (as) | 20 |
| 🏜️ Prophets of Arabia | Hud, Salih, Shu'ayb (as) | 15 |
| 🕋 Ibrahim and his Family | Ibrahim, Isma'il, Ishaq, Lut, Ya'qub, Yusuf (as) | 40 |
| 🌊 Musa and the Prophets of Israel | Musa, Harun, Dawud, Sulayman, Ilyas, Al-Yasa', Yunus, Ayyub, Dhul-Kifl (as) | 45 |
| 🌴 Zakariyya, Yahya, Maryam and Isa | Zakariyya, Yahya, Isa (as), Hadhrat Maryam | 25 |
| 🌙 The Holy Prophet Muhammad (sa) | Life in Makkah, Hijrah, Madinah, character & sayings | 35 |
| ✨ The Promised Messiah (as) | Life, claims, books, prophecies (kept small — Swab Quest covers the Community's history) | 15 |
| 📜 More Prophets & Lessons | Prophets from hadith and other sources (e.g. Shith, Yusha', Danyal, Shamwil); prayers (du'as) of the prophets from the Qur'an; "a messenger to every people" | 25 |
| | | **220** |

**Prayers of the prophets** get special care: the du'as are given with their meaning (and short Arabic where children know it), e.g. Hadhrat Yunus (as) in the whale, Hadhrat Musa (as) "My Lord, open my chest for me", Hadhrat Adam (as) and Hawwa asking forgiveness.

**Overlap:** Swab Quest already has 69 prophet questions and 27 on the Promised Messiah (as). Some overlap is fine (see IDEAS.md), but the new questions focus on the *stories* and their lessons, told for children.

---

## Landmarks — 24 blessed places

Places from the stories, as photos of the place only. Where a link comes from tradition rather than the Qur'an, the description says so. Five overlap with Swab Quest (Ka'ba, Quba, Masjid an-Nabawi, Al-Aqsa, Qadian is the finish) — kept because they belong in the stories.

### Makkah & Madinah
1. **Khana Ka'ba — Makkah** — Built by Hadhrat Ibrahim (as) and Hadhrat Isma'il (as), who prayed that Allah would accept it (Surah Al-Baqarah 2:128).
2. **Cave of Hira — Makkah** — On Jabal al-Nour; where the first revelation came to the Holy Prophet (sa) in about 610: "Read in the name of your Lord" (Surah Al-'Alaq 96:2).
3. **Cave of Thawr — Makkah** — Where the Holy Prophet (sa) and Hadhrat Abu Bakr (ra) hid for three days at the start of the Hijrah.
4. **Mount Arafat — Makkah** — Where the Holy Prophet (sa) gave his Farewell Sermon; pilgrims stand here on the Day of Arafah.
5. **Ta'if** — A mountain town where people threw stones at the Holy Prophet (sa); he prayed for them instead of against them.
6. **Masjid Quba — Madinah** — The first mosque built by the Holy Prophet (sa), on arriving near Madinah.
7. **Masjid an-Nabawi — Madinah** — The Prophet's Mosque, built by him and his companions.
8. **Mount Uhud — Madinah** — "Uhud is a mountain that loves us and we love it" (Bukhari); site of the Battle of Uhud.
9. **Badr** — Where 313 Muslims stood firm in the Battle of Badr (in the year 2 AH).

### Arabia's earlier prophets
10. **Hegra (Mada'in Salih) — AlUla** — Homes carved into the rocks; many link them to the Thamud, the people of Hadhrat Salih (as), who "carved houses out of the mountains" (Surah Al-Hijr 15:83).
11. **The Empty Quarter (Al-Ahqaf)** — Great sand dunes of southern Arabia, where the people of 'Ad and Hadhrat Hud (as) are placed (Surah Al-Ahqaf 46:22).
12. **Midian (Maghaer Shu'ayb)** — North-west Arabia; linked to Hadhrat Shu'ayb (as), and where Hadhrat Musa (as) lived for years after leaving Egypt.

### From Iraq to Egypt
13. **Ziggurat of Ur — Iraq** — The ancient city that tradition names as the birthplace of Hadhrat Ibrahim (as).
14. **Mount Judi** — The mountain where the Ark came to rest (Surah Hud 11:45); traditionally placed in south-east Turkey.
15. **Nineveh — Iraq** — The great city to which Hadhrat Yunus (as) was sent; its people believed and were forgiven (Surah Yunus 10:99).
16. **The Nile — Egypt** — Where the mother of Hadhrat Musa (as) placed her baby in a basket on the river, trusting Allah (Surah Al-Qasas 28:8).
17. **Mount Sinai — Egypt** — Traditionally the Mount Tur, where Allah spoke to Hadhrat Musa (as).

### The Holy Land
18. **Hebron (Al-Khalil)** — The Ibrahimi Mosque, where by tradition Hadhrat Ibrahim, Ishaq and Ya'qub (as) are buried.
19. **The Dead Sea** — The lowest place on land; tradition links it to the people of Hadhrat Lut (as).
20. **Al-Aqsa Mosque — Jerusalem** — The "Farthest Mosque" of the Isra' (Surah Bani Isra'il 17:2), linked with many prophets.
21. **The Jordan River** — Where, by tradition, Hadhrat Yahya (as) (John) baptised people.
22. **Bethlehem** — By tradition the birthplace of Hadhrat Isa (as); the Qur'an tells of Hadhrat Maryam under a palm tree (Surah Maryam 19:24).

### Kashmir & Qadian
23. **Roza Bal — Srinagar, Kashmir** — The tomb that the Promised Messiah (as) showed to be the resting place of Hadhrat Isa (as), who came to Kashmir after surviving the crucifixion (*Masih Hindustan Mein* — Jesus in India).
24. **Minaratul Masih — Qadian** — The minaret built at the Promised Messiah's (as) wish. *If Qadian is the finish, this becomes a spare.*

**Spares:** Masjid al-Haram (wider view), Mount Tur alternative views, Damascus (Umayyad Mosque), the Cave of the Companions (Amman), Masjid al-Qiblatayn.

*Facts and references above are checked again when they go into `config.js`.*

---

## Deeds — 56 (28 good / 28 bad), 2–3 effects each

Good deeds follow the prophets' example; bad cards are everyday mistakes with a lesson, never mocking anyone.

| 🌟 Good Deed (examples) | 📖 Lesson to Learn (examples) |
|---|---|
| You welcomed guests and shared your food, like Hadhrat Ibrahim (as) | You told a fib — the Holy Prophet (sa) was called *Al-Amin*, the trustworthy |
| You stayed patient when you were ill, like Hadhrat Ayyub (as) | You gave up too quickly — Hadhrat Nuh (as) kept trying for 950 years |
| You forgave your brother, like Hadhrat Yusuf (as) did | You got angry and walked away, like Hadhrat Yunus (as) — say sorry and come back |
| You prayed for someone who was unkind to you | You wasted water when making wudu |
| You thanked Allah for a small blessing, like Hadhrat Sulayman (as) and the ant | You forgot to say Bismillah before eating |

Effects: the usual mix; `{landmark}` cards, e.g. *"Your caravan reaches {landmark}!"*; protection = *"Allah's protection"*.

---

## Action cards — 25+ (plus the 40 general ones)

- 🎭 **Act:** building a huge ark, a whale swimming in the deep sea, a spider spinning a web over a cave, a camel walking through the desert, ants marching in a line, a baby in a basket floating down the river.
- 💬 **Explain:** *Ark* (don't say: boat, Nuh, flood), *Hijrah*, *Patience*, *Wudu*, *Mosque*, *Prophet*, *Revelation*.
- 🔊 **Sound:** rain and thunder before the flood, the sea parting, a camel, birds singing praise (like with Hadhrat Dawud (as)), wind in the desert.

---

## Open questions for Mojeeb

1. Points name **Noor** and finish **Qadian** — OK? (Alternatives: *Barakah*; finish *Masjid an-Nabawi*.)
2. Deed labels **Good Deed** / **Lesson to Learn**, landmark label **Blessed Place** — OK?
3. **"Prophets from hadith and other sources":** which should be included? Suggested: Shith (Seth), Yusha' (Joshua), Danyal (Daniel), Shamwil (Samuel), Hizqil (Ezekiel), Armiya (Jeremiah). Should questions also mention the Promised Messiah's (as) teaching that prophets were sent to every nation, with examples he gave (e.g. Hadhrat Krishna, Hadhrat Buddha), or leave those out for children?
4. **Review:** who checks the questions before the edition goes live (Mojeeb, a murabbi, both)?
5. **Swab Quest note:** a few Swab Quest answers describe miracles literally (e.g. Hadhrat Isa (as) "raised the dead", clay birds "became real birds") where the Ahmadiyya understanding is different. Should those be reviewed separately?
