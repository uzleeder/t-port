import Link from "next/link";
import { Assistant } from "@/components/Assistant";
import { Logo } from "@/components/Logo";
import { ModeIcon } from "@/components/ModeIcon";
import { DemoNotice } from "@/components/Notices";
import { SearchForm } from "@/components/SearchForm";
import { MODE_LABEL } from "@/lib/format";
import { ALL_MODES } from "@/lib/types";

const POPULAR: [string, string, string, string][] = [
  ["tashkent", "Tashkent", "samarkand", "Samarkand"],
  ["tashkent", "Tashkent", "bukhara", "Bukhara"],
  ["samarkand", "Samarkand", "bukhara", "Bukhara"],
  ["tashkent", "Tashkent", "fergana", "Fergana"],
  ["urgench", "Urgench", "khiva", "Khiva"],
  ["tashkent", "Tashkent", "termez", "Termez"],
];

const PRINCIPLES = [
  {
    title: "Every way, side by side",
    body: "Trains, coaches, flights and taxis for the same trip in one list — compared by price, duration and departure time.",
  },
  {
    title: "Sources you can see",
    body: "Each result shows where its data came from and how fresh it is. Out-of-date fares are hidden, not guessed.",
  },
  {
    title: "AI that doesn't make things up",
    body: "Describe your trip in plain words. The assistant only turns it into a search — prices and times come from the data.",
  },
];

export default function Home() {
  return (
    <>
      <section className="relative overflow-hidden">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(60rem_30rem_at_70%_-10%,rgba(55,125,255,0.25),transparent),radial-gradient(40rem_20rem_at_0%_10%,rgba(214,173,97,0.08),transparent)]"
        />
        <div className="relative mx-auto max-w-6xl px-4 pb-12 pt-12 sm:px-6 sm:pt-20">
          <div className="mb-6">
            <Logo size="lg" />
          </div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-gold">
            Global AI Transit &amp; Logistics Architecture
          </p>
          <h1 className="mt-3 max-w-3xl text-4xl font-extrabold leading-tight tracking-tight sm:text-6xl">
            One Destination.
            <br />
            <span className="text-blue">Every Way</span> to Get There.
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-muted">
            Plan journeys across Uzbekistan by train, bus, plane and taxi — compared honestly, with
            every source shown.
          </p>
          <div className="mt-8">
            <SearchForm />
          </div>
          <div className="mt-4">
            <Assistant />
          </div>
          <div className="mt-4">
            <DemoNotice />
          </div>
        </div>
      </section>

      <section aria-labelledby="popular" className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <h2 id="popular" className="text-xl font-semibold">
          Popular routes
        </h2>
        <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {POPULAR.map(([o, on, d, dn]) => (
            <li key={`${o}-${d}`}>
              <Link
                href={`/search?origin=${o}&destination=${d}`}
                className="flex items-center justify-between rounded-xl border border-line bg-surface px-4 py-3 transition hover:border-blue"
              >
                <span>
                  {on} <span className="text-muted">→</span> {dn}
                </span>
                <span className="text-sm text-blue">Search</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="how" className="mx-auto max-w-6xl px-4 pb-16 sm:px-6">
        <h2 id="how" className="sr-only">
          How T-Port works
        </h2>
        <div className="grid gap-4 md:grid-cols-3">
          {PRINCIPLES.map((p) => (
            <div key={p.title} className="rounded-2xl border border-line bg-surface p-5">
              <h3 className="font-semibold">{p.title}</h3>
              <p className="mt-2 text-sm text-muted">{p.body}</p>
            </div>
          ))}
        </div>
        <ul className="mt-8 flex flex-wrap justify-center gap-6 text-muted" aria-label="Supported modes">
          {ALL_MODES.map((m) => (
            <li key={m} className="flex items-center gap-2">
              <ModeIcon mode={m} /> {MODE_LABEL[m]}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
