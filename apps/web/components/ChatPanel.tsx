"use client";

import React from "react";
import { useChatController } from "./chat/hooks/useChatController";
import { ChatWorkspace } from "./chat/ChatWorkspace";
import { ChatFullscreen } from "./chat/ChatFullscreen";
import { ChatErrorBoundary } from "./chat/ChatErrorBoundary";
import { Message } from "./chat/types";

interface ChatPanelProps {
  datasetId: string;
  initialHistory?: Message[];
}

export function ChatPanel({ datasetId, initialHistory = [] }: ChatPanelProps) {
  const controller = useChatController(datasetId, initialHistory);

  return (
    <ChatErrorBoundary>
      {/* 1. Standard Embedded Workspace */}
      <ChatWorkspace controller={controller} />

      {/* 2. Fullscreen Portal modal: Mounts workspace on document.body when expanded */}
      <ChatFullscreen
        isOpen={controller.isExpanded}
        onClose={controller.closeFullscreen}
        modalContainerRef={controller.modalContainerRef}
      >
        <ChatWorkspace controller={controller} isPortalInstance={true} />
      </ChatFullscreen>
    </ChatErrorBoundary>
  );
}
