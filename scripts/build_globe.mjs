/**
 * Builds the landing page's rotating globe data from real map data.
 *
 * Reads content/maps/countries-110m.json (Natural Earth via world-atlas, public domain), simplifies
 * the country outlines and writes them as longitude/latitude rings to frontend/public/data/globe.json.
 * The globe component (components/landing/RotatingGlobe.tsx) loads that file only when the section
 * comes near the screen, and projects it itself as the planet turns.
 *
 *   node scripts/build_globe.mjs
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const topo = JSON.parse(readFileSync(join(ROOT, "content/maps/countries-110m.json"), "utf8"));

// --- TopoJSON decoding -----------------------------------------------------------------------
const { scale, translate } = topo.transform;
const arcs = topo.arcs.map((arc) => {
  let x = 0;
  let y = 0;
  return arc.map(([dx, dy]) => {
    x += dx;
    y += dy;
    return [x * scale[0] + translate[0], y * scale[1] + translate[1]];
  });
});
function ring(indexes) {
  const pts = [];
  for (const i of indexes) {
    const a = i < 0 ? [...arcs[~i]].reverse() : arcs[i];
    pts.push(...(pts.length ? a.slice(1) : a));
  }
  return pts;
}
function rings(geom) {
  if (geom.type === "Polygon") return geom.arcs.map(ring);
  if (geom.type === "MultiPolygon") return geom.arcs.flatMap((poly) => poly.map(ring));
  return [];
}

// --- simplification (Douglas–Peucker in degrees) ----------------------------------------------
function simplify(pts, tol) {
  if (pts.length < 4) return pts;
  const keep = new Uint8Array(pts.length);
  keep[0] = keep[pts.length - 1] = 1;
  const stack = [[0, pts.length - 1]];
  while (stack.length) {
    const [a, b] = stack.pop();
    const [ax, ay] = pts[a];
    const [bx, by] = pts[b];
    const dx = bx - ax;
    const dy = by - ay;
    const len = Math.hypot(dx, dy);
    let best = -1;
    let at = -1;
    for (let i = a + 1; i < b; i++) {
      // Closed rings start and end on the same point: measure from that point instead of a line.
      const d = len < 1e-9
        ? Math.hypot(pts[i][0] - ax, pts[i][1] - ay)
        : Math.abs(dy * pts[i][0] - dx * pts[i][1] + bx * ay - by * ax) / len;
      if (d > best) (best = d), (at = i);
    }
    if (best > tol) {
      keep[at] = 1;
      stack.push([a, at], [at, b]);
    }
  }
  return pts.filter((_, i) => keep[i]);
}
const flat = (pts) => pts.flatMap(([lon, lat]) => [Math.round(lon * 10) / 10, Math.round(lat * 10) / 10]);

const UZ = "860";
const CENTRAL_ASIA = new Set(["398", "417", "762", "795"]); // Kazakhstan, Kyrgyzstan, Tajikistan, Turkmenistan
const out = { w: [], ca: [], uz: [] };
for (const g of topo.objects.countries.geometries) {
  const group = g.id === UZ ? "uz" : CENTRAL_ASIA.has(g.id) ? "ca" : "w";
  const tol = group === "w" ? 0.35 : 0.12; // keep the highlighted countries more detailed
  for (const r of rings(g)) {
    const s = simplify(r, tol);
    if (s.length >= 4) out[group].push(flat(s));
  }
}

// --- places (real coordinates) ----------------------------------------------------------------
const places = {
  hub: { name: "Tashkent", lon: 69.24, lat: 41.3 },
  planned: [
    { name: "Almaty", lon: 76.89, lat: 43.24 },
    { name: "Bishkek", lon: 74.59, lat: 42.87 },
    { name: "Dushanbe", lon: 68.79, lat: 38.56 },
    { name: "Ashgabat", lon: 58.33, lat: 37.96 },
  ],
  vision: [
    { name: "Istanbul", lon: 28.98, lat: 41.01 },
    { name: "Moscow", lon: 37.62, lat: 55.75 },
    { name: "Dubai", lon: 55.27, lat: 25.2 },
    { name: "Delhi", lon: 77.21, lat: 28.61 },
    { name: "Beijing", lon: 116.4, lat: 39.9 },
  ],
};

const json = JSON.stringify({ source: "Natural Earth via world-atlas 2.0.2 (public domain)", countries: out, places });
const file = join(ROOT, "frontend/public/data/globe.json");
mkdirSync(dirname(file), { recursive: true });
writeFileSync(file, json);
const points = Object.values(out).flat().reduce((n, r) => n + r.length / 2, 0);
console.log(`wrote frontend/public/data/globe.json (${(json.length / 1024).toFixed(1)} KB, ${points} points)`);
