# T-PORT public landing page

The home page (`/`) is now the public introduction to T-PORT and a gateway into the existing app.
Every section uses real app functionality; nothing is a mock-up.

Screenshots (dark theme; 1280 px is the light theme): `docs/screenshots/landing/`
at 1920, 1440, 1280, 1024, 768, 430 and 360 px.

## What is on the page

| Section | Component (`frontend/src/components/landing/`) | Wired to |
|---|---|---|
| Opening animation (~2.3 s) | `IntroAnimation` | CSS only; first visit to `/` per browser session; skip button and Escape; never with reduced motion |
| Floating glass navigation | `LandingNav` (inside the global header) | Home, Explore, How It Works, AI Planner (`/planner`), About; language picker; Sign in / Get started; phone menu below 1024 px; header turns more opaque on scroll (`HeaderScroll`) |
| Cinematic hero | `CinematicHero` | Montage of the place-card illustrations (Charvak, Humo Arena, Registan, Kalon minaret, Itchan Kala) with transport line art; labelled "Artistic illustration montage" |
| Transport search | `TransportSearch` → existing `SearchForm` | Real search and location autocomplete; All / Train / Flight / Bus / Taxi / Multimodal (= all modes, up to 2 changes); swap button |
| Explore Uzbekistan | `ExploreUzbekistan` | All 14 regions → `/explore/[region]`; text from the verified place-card pack |
| T-AI showcase | `AIPlannerShowcase` | A real search (Tashkent → Samarkand, tomorrow) for the recommended / cheapest / fastest picks; labelled "Demonstration data" while the data is demo; "Ask T-AI this" opens the planner |
| How it works | `HowItWorks` | Four steps; states that bookings and payments happen with the provider |
| Why T-PORT | `FeatureBento` | Six features, no partnership or coverage claims |
| Vision / About | `GlobalVision` | Real-map globe that turns slowly (Natural Earth outlines, `scripts/build_globe.mjs` → `public/data/globe.json`, drawn by `RotatingGlobe`; still with reduced motion, paused off screen) with Uzbekistan highlighted and routes to real capitals; roadmap: Uzbekistan "Pilot now", Central Asia "Planned", Global "Vision", with "plans, not live services" |
| Final call to action | `FinalCTA` | Get started (`/register`), Explore destinations (`/explore`) |
| Footer (all pages) | `SiteFooter` | Product links, transport modes, About, Help (how it works), Privacy (`/privacy`, new), Photo credits, language picker |

## Languages

English, Uzbek (Latin) and Russian for the landing page, navigation, footer and `/privacy`.
`<T>` (`components/T.tsx`) renders all three; CSS shows the one matching `<html lang>`, which an
inline script sets before first paint from the saved choice or the browser language. Switching is
instant and needs no extra JavaScript. Strings live in `lib/i18n.ts`.

## Themes

Dark (navy glass) is the default; light mode follows the cream design: cream page, white cards, near-black primary actions, blue accents. The hero, intro, vision globe and closing horizon each have a designed light version (landing theme variables in `globals.css`).

## Design system changes

### T-AI identity

`components/TAILogo.tsx` displays the user's exact Option 2 artwork through an SVG silhouette
clip, excluding the surrounding diagram. The source PNG is preserved in `public/images/t-ai/`.
It belongs only to T-AI: navigation and entry links, the introduction,
chat preview, assistant avatars, thinking indicator and planner headings.
The T-PORT navigation and product mark remain in `components/Logo.tsx`.
The artwork gently cycles through the full colour spectrum over 24 seconds, without a picker
or surrounding control card. Larger marks gently wave, with small light pulses moving along
the neural connections. Reduced motion stops the wave, hides moving pulses and keeps the original
colours still. Its geometry and
source image remain unchanged. No WebGL runtime is required. The supplied source is 446 × 250
pixels, so large displays are limited by that resolution.

Dark palette moved to the brief: midnight navy `#050B18`, deep blue `#0B1830`, ice blue `#62CFFF`,
soft gold `#D6B36A`, secondary text `#A4B2C8`. Filled buttons use `#0A6CF0` (electric blue
darkened just enough for white text to pass WCAG AA, 4.7:1); `#007AFF` is the hover and accent.
Motion is CSS only (scroll-driven fade-ins and a slight hero parallax) and switches off with
reduced motion.

## Tests

- `e2e/landing.spec.ts`: intro plays once and can be skipped; no intro with reduced motion;
  language switching and memory; 14 region links; multimodal search with swap; T-AI showcase
  labels demo data; roadmap says "planned"; phone menu.
- The rest of the suite runs with reduced motion (no intro).

## Measured performance (local production build)

| | First content | Largest content | Layout shift | Main-thread blocking |
|---|---|---|---|---|
| Desktop 1440 px | 0.4 s | 0.6 s | 0.004 | ~80 ms |
| Phone, 4× CPU slowdown, ~1.6 Mbps | 1.8 s | 2.0–2.1 s | 0.005 | 660–1,040 ms (other app pages: ~530 ms) |

Measured with the browser's own performance APIs in Playwright, not Lighthouse (Lighthouse is not
installed in this project). The phone blocking time is the main risk to a 90+ Lighthouse mobile
score: the landing has a larger DOM than other pages, partly because each text exists in three
languages.

## Known limitations and missing assets

- **Logo**: the site uses the vector T-PORT mark already in `components/Logo.tsx`, traced from the
  supplied artwork. The original logo file is not in the repository; replace the paths in
  `Logo.tsx` when it is supplied.
- **Hero panorama**: built from the existing place-card illustrations, not a single commissioned
  panorama (no such asset exists yet).
- **Regions**: cards describe the two verified places per region from the place-card pack. Landmarks
  named in the brief that are not in the verified pack (TV Tower, Amir Temur Square, Gur-e-Amir,
  Ark Fortress, Fayaz Tepe, Ayaz Kala) are not claimed.
- **Translations**: written for this page; a native Uzbek and Russian review is recommended. The
  rest of the app (search results, journey pages, T-AI replies except Uzbek place answers) is
  English for now.
- **Footer**: no Contact link (no contact address supplied) and no Terms of Use (needs owner-provided
  legal text). `/privacy` is a plain summary of what the pilot stores, not a formal policy.
- **Font**: Manrope (already in the app) is used as the "equivalent modern sans-serif".
