"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/*
 * A real-map globe (Natural Earth outlines, public/data/globe.json built by scripts/build_globe.mjs)
 * that turns slowly on its axis. Uzbekistan is highlighted and routes start at Tashkent: gold to the
 * Central Asian capitals (planned), faint blue further out (long-term vision).
 *
 * Drawn on a canvas in a 480×480 design space. The data loads only when the section comes near the
 * screen; the animation runs only while the globe is visible and the tab is open, and never with
 * reduced motion (then it shows one still frame). Colours come from the --g-* theme variables.
 */

type Place = { name: string; lon: number; lat: number };
type GlobeData = { countries: { w: number[][]; ca: number[][]; uz: number[][] }; places: { hub: Place; planned: Place[]; vision: Place[] } };

const C = 240;
const R = 190;
const TILT = 24; // latitude at the centre of the view
const START_LON = 62; // first frame: Uzbekistan just left of centre
const DEG_PER_SEC = 6;
const rad = Math.PI / 180;

type Colors = Record<"a" | "b" | "c" | "line" | "shade" | "dot" | "region" | "uz" | "land" | "landLine" | "regionFill", string>;

function readColors(el: Element): Colors {
  const cs = getComputedStyle(el);
  const v = (n: string) => cs.getPropertyValue(n).trim() || "#888";
  return {
    a: v("--g-a"), b: v("--g-b"), c: v("--g-c"), line: v("--g-line"), shade: v("--g-shade"), dot: v("--g-dot"),
    region: v("--g-region"), uz: v("--g-uz"), land: v("--g-land"), landLine: v("--g-land-line"), regionFill: v("--g-region-fill"),
  };
}

/** "#rrggbb" + alpha -> rgba(); other colour strings are returned unchanged. */
function alpha(color: string, a: number) {
  const m = /^#([0-9a-f]{6})$/i.exec(color);
  if (!m) return color;
  const n = parseInt(m[1], 16);
  return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`;
}

/** Points along the great circle from a to b, raised in the middle like a flight path: [lon, lat, lift]. */
function route(a: Place, b: Place, height: number, steps = 40): number[][] {
  const vec = (p: Place) => [Math.cos(p.lat * rad) * Math.cos(p.lon * rad), Math.cos(p.lat * rad) * Math.sin(p.lon * rad), Math.sin(p.lat * rad)];
  const va = vec(a);
  const vb = vec(b);
  const omega = Math.acos(Math.min(1, va[0] * vb[0] + va[1] * vb[1] + va[2] * vb[2]));
  const out: number[][] = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const k1 = Math.sin((1 - t) * omega) / Math.sin(omega);
    const k2 = Math.sin(t * omega) / Math.sin(omega);
    const v = [k1 * va[0] + k2 * vb[0], k1 * va[1] + k2 * vb[1], k1 * va[2] + k2 * vb[2]];
    out.push([Math.atan2(v[1], v[0]) / rad, Math.asin(v[2]) / rad, 1 + height * Math.sin(Math.PI * t)]);
  }
  return out;
}

export function RotatingGlobe({ label }: { label: ReactNode }) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const tag = useRef<HTMLSpanElement>(null);
  const [data, setData] = useState<GlobeData | null>(null);

  // Load the map only when the globe is about to scroll into view.
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    let cancelled = false;
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        io.disconnect();
        fetch("/data/globe.json")
          .then((r) => (r.ok ? r.json() : null))
          .then((d: GlobeData | null) => !cancelled && d && setData(d))
          .catch(() => {});
      },
      { rootMargin: "600px 0px" },
    );
    io.observe(el);
    return () => {
      cancelled = true;
      io.disconnect();
    };
  }, []);

  useEffect(() => {
    const cv = canvas.current;
    const el = wrap.current;
    if (!data || !cv || !el) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;

    const { hub, planned, vision } = data.places;
    const routes = [
      ...planned.map((p) => ({ pts: route(hub, p, 0.03), kind: "planned" as const, end: p })),
      ...vision.map((p) => ({ pts: route(hub, p, 0.09), kind: "vision" as const, end: p })),
    ];
    let colors = readColors(el);
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let lon0 = START_LON;
    let dash = 0;
    let visible = false;
    let frame = 0;
    let last = 0;

    const sin0 = Math.sin(TILT * rad);
    const cos0 = Math.cos(TILT * rad);
    // Orthographic projection: [x, y, facing] where facing > 0 is the visible side.
    const project = (lon: number, lat: number, lift = 1): [number, number, number] => {
      const l = (lon - lon0) * rad;
      const p = lat * rad;
      const cp = Math.cos(p);
      return [C + R * lift * cp * Math.sin(l), C - R * lift * (cos0 * Math.sin(p) - sin0 * cp * Math.cos(l)), sin0 * Math.sin(p) + cos0 * cp * Math.cos(l)];
    };

    const resize = () => {
      const size = el.clientWidth;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      cv.width = Math.round(size * dpr);
      cv.height = Math.round(size * dpr);
      cv.style.width = cv.style.height = `${size}px`;
      ctx.setTransform((size * dpr) / 480, 0, 0, (size * dpr) / 480, 0, 0);
    };

    /** A ring as a closed path; points behind the globe are pulled onto its edge. */
    const ringPath = (ring: number[]) => {
      let seen = false;
      for (let i = 0; i < ring.length; i += 2) {
        const p = project(ring[i], ring[i + 1]);
        let [x, y] = p;
        if (p[2] > 0) seen = true;
        else {
          const d = Math.hypot(x - C, y - C) || 1;
          x = C + ((x - C) / d) * R;
          y = C + ((y - C) / d) * R;
        }
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      return seen;
    };
    const fillGroup = (rings: number[][], fill: string, stroke: string, width: number, fillAlpha = 1) => {
      ctx.beginPath();
      for (const r of rings) {
        // Skip rings entirely on the far side (cheap check on a few points).
        let any = false;
        for (let i = 0; i < r.length && !any; i += 6) any = project(r[i], r[i + 1])[2] > 0;
        if (any) ringPath(r);
      }
      ctx.globalAlpha = fillAlpha;
      ctx.fillStyle = fill;
      ctx.fill("evenodd");
      ctx.globalAlpha = 1;
      ctx.strokeStyle = stroke;
      ctx.lineWidth = width;
      ctx.stroke();
    };
    /** Polyline of [lon, lat, lift?] points, only the parts on the visible side. */
    const strokeVisible = (pts: number[][]) => {
      let down = false;
      for (const [lon, lat, lift] of pts) {
        const [x, y, f] = project(lon, lat, lift ?? 1);
        if (f > 0) {
          if (down) ctx.lineTo(x, y);
          else ctx.moveTo(x, y);
          down = true;
        } else down = false;
      }
    };

    const draw = () => {
      ctx.clearRect(0, 0, 480, 480);
      // halo
      const halo = ctx.createRadialGradient(C, C, R * 0.95, C, C, R * 1.22);
      halo.addColorStop(0, alpha(colors.uz, 0.18));
      halo.addColorStop(1, alpha(colors.uz, 0));
      ctx.fillStyle = halo;
      ctx.beginPath();
      ctx.arc(C, C, R * 1.22, 0, Math.PI * 2);
      ctx.fill();
      // body
      const body = ctx.createRadialGradient(C - 50, C - 65, 10, C, C, R * 1.15);
      body.addColorStop(0, colors.a);
      body.addColorStop(0.55, colors.b);
      body.addColorStop(1, colors.c);
      ctx.fillStyle = body;
      ctx.beginPath();
      ctx.arc(C, C, R, 0, Math.PI * 2);
      ctx.fill();

      ctx.save();
      ctx.beginPath();
      ctx.arc(C, C, R, 0, Math.PI * 2);
      ctx.clip();
      // graticule
      ctx.beginPath();
      for (let lon = -180; lon < 180; lon += 20) strokeVisible(Array.from({ length: 41 }, (_, i) => [lon, -80 + i * 4]));
      for (let lat = -60; lat <= 60; lat += 20) strokeVisible(Array.from({ length: 91 }, (_, i) => [-180 + i * 4, lat]));
      ctx.strokeStyle = alpha(colors.line, 0.12);
      ctx.lineWidth = 0.7;
      ctx.stroke();
      // countries
      ctx.lineJoin = "round";
      fillGroup(data.countries.w, colors.land, colors.landLine, 0.6);
      fillGroup(data.countries.ca, colors.regionFill, alpha(colors.region, 0.6), 0.7);
      fillGroup(data.countries.uz, colors.uz, colors.uz, 0.8, 0.85);
      // shading
      const shade = ctx.createRadialGradient(C - 60, C - 70, R * 0.4, C, C, R * 1.05);
      shade.addColorStop(0, alpha(colors.shade, 0));
      shade.addColorStop(1, alpha(colors.shade, 0.6));
      ctx.fillStyle = shade;
      ctx.fillRect(0, 0, 480, 480);
      ctx.restore();

      // rim
      ctx.beginPath();
      ctx.arc(C, C, R, 0, Math.PI * 2);
      ctx.strokeStyle = alpha(colors.line, 0.3);
      ctx.lineWidth = 1;
      ctx.stroke();

      // routes and places
      ctx.lineCap = "round";
      for (const r of routes) {
        ctx.beginPath();
        strokeVisible(r.pts);
        ctx.setLineDash(r.kind === "planned" ? [3, 3] : [1, 5]);
        ctx.lineDashOffset = -dash;
        ctx.strokeStyle = r.kind === "planned" ? colors.region : alpha(colors.dot, 0.6);
        ctx.lineWidth = r.kind === "planned" ? 1.6 : 1.2;
        ctx.stroke();
        const [x, y, f] = project(r.end.lon, r.end.lat);
        if (f > 0) {
          ctx.setLineDash([]);
          ctx.beginPath();
          ctx.arc(x, y, r.kind === "planned" ? 2.4 : 2.6, 0, Math.PI * 2);
          ctx.fillStyle = r.kind === "planned" ? colors.region : alpha(colors.dot, 0.8);
          ctx.fill();
        }
      }
      ctx.setLineDash([]);
      const [hx, hy, hf] = project(hub.lon, hub.lat);
      if (hf > 0) {
        const pulse = reduce ? 0 : (Math.sin(dash / 6) + 1) / 2;
        ctx.beginPath();
        ctx.arc(hx, hy, 9 + pulse * 6, 0, Math.PI * 2);
        ctx.fillStyle = alpha(colors.uz, 0.22 - pulse * 0.12);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(hx, hy, 4.5, 0, Math.PI * 2);
        ctx.fillStyle = colors.uz;
        ctx.fill();
        ctx.strokeStyle = colors.a;
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
      // label follows Tashkent and fades out on the far side
      if (tag.current) {
        tag.current.style.left = `${(hx / 480) * 100 + 2.5}%`;
        tag.current.style.top = `${(hy / 480) * 100 - 1.5}%`;
        tag.current.style.opacity = String(Math.max(0, Math.min(1, hf * 5)));
      }
    };

    const tick = (now: number) => {
      frame = requestAnimationFrame(tick);
      if (now - last < 32) return; // ~30 fps is plenty for a slow turn
      const dt = last ? Math.min(0.1, (now - last) / 1000) : 0;
      last = now;
      lon0 -= DEG_PER_SEC * dt; // the surface moves west to east, like the real Earth
      dash += dt * 12;
      draw();
    };
    const start = () => {
      if (reduce || frame || !visible || document.hidden) return;
      last = 0;
      frame = requestAnimationFrame(tick);
    };
    const stop = () => {
      cancelAnimationFrame(frame);
      frame = 0;
    };

    resize();
    draw();
    const ro = new ResizeObserver(() => {
      resize();
      draw();
    });
    ro.observe(el);
    const io = new IntersectionObserver((entries) => {
      visible = entries.some((e) => e.isIntersecting);
      if (visible) start();
      else stop();
    });
    io.observe(el);
    const onVis = () => (document.hidden ? stop() : start());
    document.addEventListener("visibilitychange", onVis);
    // Theme switch: re-read the colours.
    const mo = new MutationObserver(() => {
      colors = readColors(el);
      draw();
    });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    return () => {
      stop();
      ro.disconnect();
      io.disconnect();
      mo.disconnect();
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [data]);

  return (
    <div ref={wrap} aria-hidden="true" className="reveal relative mx-auto aspect-square w-full max-w-[34rem]">
      <canvas ref={canvas} className="absolute inset-0 h-full w-full" />
      <span
        ref={tag}
        className="l-card l-text pointer-events-none absolute -translate-y-full rounded-full px-2.5 py-1 text-xs font-semibold opacity-0 backdrop-blur transition-opacity"
      >
        {label}
      </span>
    </div>
  );
}
