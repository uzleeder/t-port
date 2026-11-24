# Map data

`countries-110m.json` — world country outlines at 1:110m scale, from the
[world-atlas](https://github.com/topojson/world-atlas) package v2.0.2 (ISC licence), built from
[Natural Earth](https://www.naturalearthdata.com/) data, which is in the public domain.
Downloaded from cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json.

`scripts/build_globe.mjs` simplifies it into the longitude/latitude outlines in
`frontend/public/data/globe.json` (~16 KB gzipped), which the rotating globe on the landing page loads when it comes into view.
