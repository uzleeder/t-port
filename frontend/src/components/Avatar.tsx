import type { User } from "@/lib/session";

export const displayName = (u: Pick<User, "display_name" | "email">) => u.display_name || u.email.split("@")[0];

/**
 * Profile photo, or the first letter of the name on a blue disc. Decorative: the name is always
 * shown or announced next to it. `src` overrides the saved photo (e.g. a preview before saving).
 */
export function Avatar({
  user,
  size,
  src,
  className = "",
}: {
  user: Pick<User, "display_name" | "email" | "avatar_url">;
  size: number;
  src?: string | null;
  className?: string;
}) {
  const url = src === undefined ? user.avatar_url : src;
  const box = { width: size, height: size };
  if (url) {
    return (
      // A private, per-user image served by the API (never cached), so next/image adds nothing.
      // eslint-disable-next-line @next/next/no-img-element
      <img src={url} alt="" {...box} className={`shrink-0 rounded-full object-cover ${className}`} style={box} />
    );
  }
  return (
    <span
      aria-hidden="true"
      style={{ ...box, fontSize: Math.round(size * 0.42) }}
      className={`flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#1f6bff] to-[#3cc8ff] font-bold uppercase leading-none text-white ${className}`}
    >
      {displayName(user).slice(0, 1)}
    </span>
  );
}
