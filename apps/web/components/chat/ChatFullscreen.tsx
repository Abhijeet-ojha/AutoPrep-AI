import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";

interface ChatFullscreenProps {
  isOpen: boolean;
  onClose: () => void;
  modalContainerRef: React.RefObject<HTMLDivElement>;
  children: React.ReactNode;
}

export const ChatFullscreen: React.FC<ChatFullscreenProps> = ({
  isOpen,
  onClose,
  modalContainerRef,
  children,
}) => {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  if (!isOpen || !mounted) return null;

  // Render on the document body to escape nested containers
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/65 dark:bg-black/80 backdrop-blur-sm p-4 animate-fade-in">
      {/* Click outside to close */}
      <div className="absolute inset-0" onClick={onClose} />
      
      {/* Modal Container */}
      <div
        ref={modalContainerRef}
        role="dialog"
        aria-modal="true"
        className="relative w-full max-w-4xl h-[85vh] md:h-[80vh] bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl flex flex-col shadow-2xl overflow-hidden animate-scale-up"
      >
        {children}
      </div>
    </div>,
    document.body
  );
};
