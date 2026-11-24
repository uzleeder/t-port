"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Avatar, displayName } from "./Avatar";
import { DeleteAccount } from "./Dashboard";
import { Icon, type IconName } from "./Icons";
import { StateMessage } from "./Notices";
import { PageBanner } from "./PageBanner";
import { PreferencesForm } from "./PreferencesForm";
import { ThemeChooser } from "./ThemeToggle";
import { ApiError, clientApi } from "@/lib/api";
import { AVATAR_ACCEPT, AvatarError, prepareAvatar } from "@/lib/avatar";
import { formatTimestamp } from "@/lib/format";
import { notifySessionChanged, useMe, type Me } from "@/lib/session";

/** Profile & settings, in one simple column: your profile, then three groups of settings. */
export function Profile() {
  const [me] = useMe({ keepPrevious: true });

  if (me.status === "loading") {
    return <div role="status" aria-label="Loading" className="h-64 animate-pulse rounded-3xl bg-surface" />;
  }
  if (me.status === "error") {
    return (
      <StateMessage tone="error" title="Profile unavailable">
        <p>{me.message}</p>
      </StateMessage>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <PageBanner icon="user" title="Profile & Settings" subtitle="Your photo, your name and how T-Port works for you." />
      {me.status === "anonymous" ? (
        <>
          <StateMessage title="Sign in to manage your profile" action={{ href: "/login?next=/profile", label: "Sign in" }}>
            <p>Your photo, name and travel preferences live here.</p>
          </StateMessage>
          <Group icon="sparkle" title="Appearance" hint="How T-Port looks on this device.">
            <ThemeChooser />
          </Group>
        </>
      ) : (
        <SignedIn me={me.me} />
      )}
    </div>
  );
}

function SignedIn({ me }: { me: Me }) {
  return (
    <>
      <ProfileCard me={me} />
      <Group icon="route" title="Travel preferences" hint="New searches start with these.">
        <PreferencesForm />
      </Group>
      <Group icon="sparkle" title="Appearance" hint="How T-Port looks on this device.">
        <ThemeChooser />
      </Group>
      <AccountGroup me={me} />
    </>
  );
}

// --- profile card ----------------------------------------------------------------------------------
type PhotoDraft = { kind: "keep" } | { kind: "remove" } | { kind: "new"; blob: Blob; url: string };

function ProfileCard({ me }: { me: Me }) {
  const { user, saved_count } = me;
  const id = useId();
  const fileInput = useRef<HTMLInputElement>(null);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(user.display_name ?? "");
  const [photo, setPhoto] = useState<PhotoDraft>({ kind: "keep" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Free the preview image when it is replaced or the card goes away.
  const previewUrl = photo.kind === "new" ? photo.url : null;
  useEffect(() => () => void (previewUrl && URL.revokeObjectURL(previewUrl)), [previewUrl]);

  function startEditing(pickPhoto = false) {
    setName(user.display_name ?? "");
    setPhoto({ kind: "keep" });
    setError(null);
    setNotice(null);
    setEditing(true);
    if (pickPhoto) fileInput.current?.click();
  }

  async function onPick(file: File | undefined) {
    if (!file) return;
    setError(null);
    try {
      const blob = await prepareAvatar(file);
      setPhoto({ kind: "new", blob, url: URL.createObjectURL(blob) });
      setEditing(true);
    } catch (e) {
      setError(e instanceof AvatarError ? e.message : "Couldn't use that photo. Try another one.");
    } finally {
      if (fileInput.current) fileInput.current.value = ""; // picking the same file again still fires
    }
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      if (photo.kind === "new") {
        await clientApi("/api/v1/me/avatar", {
          method: "PUT",
          body: photo.blob,
          headers: { "Content-Type": photo.blob.type },
        });
      } else if (photo.kind === "remove") {
        await clientApi("/api/v1/me/avatar", { method: "DELETE" });
      }
      if (name.trim() !== (user.display_name ?? "")) {
        await clientApi("/api/v1/me", { method: "PATCH", body: JSON.stringify({ display_name: name }) });
      }
      setEditing(false);
      setPhoto({ kind: "keep" });
      setNotice("Profile saved.");
      notifySessionChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  const shownPhoto = photo.kind === "new" ? photo.url : photo.kind === "remove" ? null : undefined;
  const hasPhoto = photo.kind === "new" || (photo.kind === "keep" && !!user.avatar_url);

  return (
    <section aria-labelledby={`${id}-name`} className="rounded-3xl bg-surface p-5 shadow-soft sm:p-6">
      <input
        ref={fileInput}
        type="file"
        accept={AVATAR_ACCEPT}
        className="sr-only"
        tabIndex={-1}
        aria-label="Choose a profile photo"
        onChange={(e) => onPick(e.target.files?.[0])}
      />
      <div className="flex flex-col items-center gap-5 text-center sm:flex-row sm:items-center sm:text-left">
        <div className="relative">
          <Avatar user={user} src={shownPhoto} size={104} className="ring-4 ring-gold/40" />
          <button
            type="button"
            onClick={() => (editing ? fileInput.current?.click() : startEditing(true))}
            className="absolute -bottom-1 -right-1 grid h-9 w-9 place-items-center rounded-full bg-blue text-white shadow-glow ring-2 ring-white/80 hover:bg-blue-hover"
          >
            <Icon name="camera" className="h-[18px] w-[18px]" />
            <span className="sr-only">{user.avatar_url ? "Change photo" : "Add a photo"}</span>
          </button>
        </div>

        {!editing ? (
          <div className="min-w-0 flex-1">
            <h2 id={`${id}-name`} className="text-2xl font-bold leading-tight">
              {displayName(user)}
            </h2>
            <p className="truncate text-sm text-muted">{user.email}</p>
            <p className="mt-1 text-xs text-muted">
              Member since {formatTimestamp(user.created_at).split(",")[0]} · {saved_count} saved{" "}
              {saved_count === 1 ? "journey" : "journeys"}
            </p>
          </div>
        ) : (
          <form
            className="w-full min-w-0 flex-1 space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              void save();
            }}
          >
            <h2 id={`${id}-name`} className="sr-only">
              Edit profile
            </h2>
            <div>
              <label htmlFor={`${id}-input`} className="text-sm font-medium">
                Name
              </label>
              <input
                id={`${id}-input`}
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={80}
                autoComplete="name"
                placeholder={user.email.split("@")[0]}
                className="mt-1 w-full rounded-2xl bg-card px-4 py-2.5 ring-1 ring-line focus:outline-none focus:ring-2 focus:ring-blue"
              />
              <p className="mt-1 text-xs text-muted">Shown on your account. Leave empty to use your email name.</p>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
              <button
                type="button"
                onClick={() => fileInput.current?.click()}
                className="rounded-full px-4 py-2 text-sm font-medium ring-1 ring-line hover:bg-surface-2"
              >
                {hasPhoto ? "Change photo" : "Upload photo"}
              </button>
              {hasPhoto && (
                <button
                  type="button"
                  onClick={() => setPhoto({ kind: "remove" })}
                  className="rounded-full px-4 py-2 text-sm font-medium text-danger ring-1 ring-line hover:bg-danger/10"
                >
                  Remove photo
                </button>
              )}
              <span className="text-xs text-muted">JPG, PNG or WebP · cropped to a square</span>
            </div>
            <div className="flex flex-wrap justify-center gap-2 pt-1 sm:justify-start">
              <button
                type="submit"
                disabled={busy}
                className="rounded-full bg-blue px-5 py-2 text-sm font-semibold text-white hover:bg-blue-hover disabled:opacity-60"
              >
                {busy ? "Saving…" : "Save"}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  setEditing(false);
                  setPhoto({ kind: "keep" });
                  setError(null);
                }}
                className="rounded-full px-5 py-2 text-sm font-medium text-muted hover:text-ink"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {!editing && (
          <button
            type="button"
            onClick={() => startEditing()}
            className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold ring-1 ring-gold/60 hover:bg-gold/10"
          >
            <Icon name="pencil" className="h-4 w-4" /> Edit profile
          </button>
        )}
      </div>
      {error && (
        <p role="alert" className="mt-4 rounded-2xl bg-danger/10 px-4 py-2.5 text-sm text-danger">
          {error}
        </p>
      )}
      {notice && !error && (
        <p role="status" className="mt-4 rounded-2xl bg-success/10 px-4 py-2.5 text-sm text-success">
          {notice}
        </p>
      )}
    </section>
  );
}

// --- account: session, privacy, deletion ------------------------------------------------------------
function AccountGroup({ me }: { me: Me }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function signOut() {
    setBusy(true);
    try {
      await clientApi("/api/v1/auth/logout", { method: "POST" });
    } catch {
      // Signed out locally either way.
    } finally {
      notifySessionChanged();
      router.push("/");
      router.refresh();
    }
  }

  return (
    <Group icon="shield" title="Account & privacy" hint="Your sign-in and what T-Port keeps about you.">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-card px-4 py-3">
        <div className="text-sm">
          <p className="font-medium">Signed in on this browser</p>
          <p className="text-muted">Until {formatTimestamp(me.session_expires_at)}</p>
        </div>
        <button
          type="button"
          onClick={signOut}
          disabled={busy}
          className="rounded-full px-4 py-2 text-sm font-semibold ring-1 ring-gold/60 hover:bg-gold/10 disabled:opacity-60"
        >
          {busy ? "Signing out…" : "Sign out"}
        </button>
      </div>
      <details className="group mt-3 rounded-2xl bg-card px-4 py-3 text-sm">
        <summary className="flex cursor-pointer list-none items-center justify-between font-medium">
          What T-Port keeps about you
          <Icon name="chevronDown" className="h-4 w-4 transition group-open:rotate-180" />
        </summary>
        <ul className="mt-2 space-y-1.5 text-muted">
          {[
            "Your name, email and photo are shown only to you.",
            "Your password is stored only as a salted hash.",
            "Assistant requests are not stored as text; only counts and timings.",
            "Booking hand-offs are counted per provider and day, never linked to you.",
            "Deleting your account removes your photo, saved journeys and preferences.",
          ].map((t) => (
            <li key={t} className="flex items-start gap-2">
              <Icon name="check" className="mt-0.5 h-4 w-4 shrink-0 text-success" /> {t}
            </li>
          ))}
        </ul>
      </details>
      <div className="mt-3">
        <DeleteAccount />
      </div>
    </Group>
  );
}

// --- building blocks ---------------------------------------------------------------------------------
function Group({ icon, title, hint, children }: { icon: IconName; title: string; hint: string; children: ReactNode }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="rounded-3xl bg-surface p-5 shadow-soft sm:p-6">
      <div className="mb-4 flex items-center gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-blue/15 text-sky ring-1 ring-blue/30">
          <Icon name={icon} className="h-5 w-5" />
        </span>
        <div>
          <h2 id={id} className="text-lg font-semibold leading-tight">
            {title}
          </h2>
          <p className="text-sm text-muted">{hint}</p>
        </div>
      </div>
      {children}
    </section>
  );
}
