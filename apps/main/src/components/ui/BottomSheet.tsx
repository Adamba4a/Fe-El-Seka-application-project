"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

interface BottomSheetProps {
  isOpen: boolean;
  onClose: () => void;
  maxHeightPercent?: number;
  children: React.ReactNode;
}

export function BottomSheet({
  isOpen,
  onClose,
  maxHeightPercent = 65,
  children,
}: BottomSheetProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    document.body.style.overflow = isOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [isOpen]);

  if (!mounted) return null;

  return createPortal(
    <div
      className={`fixed inset-0 z-50 ${isOpen ? "pointer-events-auto" : "pointer-events-none"}`}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-surface-overlay transition-opacity duration-300"
        style={{ opacity: isOpen ? 1 : 0 }}
        onClick={onClose}
      />

      {/* Panel */}
      <div
        className="absolute bottom-0 left-0 right-0 bg-surface-card rounded-t-2xl shadow-xl flex flex-col overflow-hidden"
        style={{
          maxHeight: `${maxHeightPercent}vh`,
          transform: isOpen ? "translateY(0)" : "translateY(100%)",
          transition: "transform 300ms ease-out",
          willChange: "transform",
        }}
      >
        {/* Drag handle */}
        <button
          type="button"
          onClick={onClose}
          aria-label="Close panel"
          className="flex items-center justify-center pt-3 pb-2 w-full flex-shrink-0"
        >
          <div className="w-8 h-1 rounded-full bg-border-default" />
        </button>

        {/* Scrollable content */}
        <div className="overflow-y-auto flex-1 px-4 pb-6">
          {children}
        </div>
      </div>
    </div>,
    document.body
  );
}
