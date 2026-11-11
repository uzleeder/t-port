import { AuthForm } from "./AuthForm";

export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mx-auto max-w-md px-4 py-12 sm:py-16">
      <div className="rounded-2xl border border-line bg-surface p-6 sm:p-8">
        <h1 className="text-2xl font-bold">{title}</h1>
        <p className="mt-1 mb-6 text-muted">{subtitle}</p>
        {children}
      </div>
    </div>
  );
}

/** Reads ?next= (request-time) inside a Suspense boundary and renders the form. */
export async function AuthFormWithNext({
  searchParams,
  mode,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
  mode: "login" | "register";
}) {
  const next = (await searchParams).next;
  return <AuthForm mode={mode} next={Array.isArray(next) ? next[0] : next} />;
}
