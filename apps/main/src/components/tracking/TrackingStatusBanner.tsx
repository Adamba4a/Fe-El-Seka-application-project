"use client";

import { useEffect, useState } from "react";

interface TrackingStatusBannerProps {
  isStale: boolean;
  rideCompleted: boolean;
  onRedirectComplete: () => void;
}

export function TrackingStatusBanner({
  isStale,
  rideCompleted,
  onRedirectComplete,
}: TrackingStatusBannerProps) {
  const [countdown, setCountdown] = useState(3);

  useEffect(() => {
    if (!rideCompleted) return;
    setCountdown(3);
    const interval = setInterval(() => {
      setCountdown((n) => {
        if (n <= 1) {
          clearInterval(interval);
          onRedirectComplete();
          return 0;
        }
        return n - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [rideCompleted, onRedirectComplete]);

  if (rideCompleted) {
    return (
      <div className="w-full bg-green-600 text-white text-center py-3 px-4 text-sm font-medium">
        Ride Completed — redirecting in {countdown}s…
      </div>
    );
  }

  if (isStale) {
    return (
      <div className="w-full bg-yellow-400 text-yellow-900 text-center py-3 px-4 text-sm font-medium">
        Driver location may be outdated
      </div>
    );
  }

  return null;
}
