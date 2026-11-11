"use client";

export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <div role="alert" className="rounded-2xl border border-danger/60 bg-surface px-6 py-10 text-center">
        <h2 className="text-lg font-semibold text-danger">Something went wrong</h2>
        <p className="mt-2 text-muted">An unexpected error occurred while loading this page.</p>
        <button
          type="button"
          onClick={reset}
          className="mt-4 rounded-xl border border-line px-4 py-2 text-sm hover:border-blue"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
