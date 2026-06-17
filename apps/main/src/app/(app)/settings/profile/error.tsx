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
        <a href="/rides" className="text-gray-500 hover:text-gray-700 text-lg leading-none">←</a>
        <h1 className="text-xl font-bold">Edit Profile</h1>
      </div>
      <p className="text-sm text-red-600">Something went wrong loading your profile.</p>
      <div className="flex gap-3">
        <button
          onClick={reset}
          className="text-sm text-blue-600 hover:underline"
        >
          Try again
        </button>
        <a href="/rides" className="text-sm text-gray-500 hover:underline">
          Go to rides
        </a>
      </div>
    </main>
  );
}
