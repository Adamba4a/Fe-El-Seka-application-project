interface LockoutMessageProps {
  lockoutMessage: string;
  supportEmail?: string;
}

export function LockoutMessage({ lockoutMessage, supportEmail }: LockoutMessageProps) {
  const email = supportEmail ?? lockoutMessage.match(/[\w.+-]+@[\w-]+\.[\w.]+/)?.[0];

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-2">
      <p className="font-semibold text-amber-800">Submission limit reached</p>
      <p className="text-sm text-amber-700">{lockoutMessage}</p>
      {email && (
        <a
          href={`mailto:${email}`}
          className="inline-block text-sm text-blue-600 underline font-medium"
        >
          Contact {email}
        </a>
      )}
    </div>
  );
}
