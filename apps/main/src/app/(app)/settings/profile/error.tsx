"use client";

export default function ProfileError({
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <main className="max-w-sm mx-auto p-6 space-y-4">
      <div className="flex items-center gap-3">
        <a href="/" className="text-content-muted hover:text-content-secondary text-lg leading-none">←</a>
        <h1 className="text-h3 text-content-primary">Edit Profile</h1>
      </div>
      <p className="text-body-sm text-content-destructive">Something went wrong loading your profile.</p>
      <div className="flex gap-3">
        <button
          onClick={reset}
          className="text-body-sm text-brand-primary hover:underline"
        >
          Try again
        </button>
        <a href="/" className="text-body-sm text-content-muted hover:underline">
          Go home
        </a>
      </div>
    </main>
  );
}
