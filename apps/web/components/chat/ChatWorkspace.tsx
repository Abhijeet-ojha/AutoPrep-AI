import React from "react";
import { ChatController } from "./hooks/useChatController";
import { ChatHeader } from "./ChatHeader";
import { ChatMessages } from "./ChatMessages";
import { ChatSuggestions } from "./ChatSuggestions";
import { ChatInput } from "./ChatInput";

interface ChatWorkspaceProps {
  controller: ChatController;
  isPortalInstance?: boolean;
}

export const ChatWorkspace: React.FC<ChatWorkspaceProps> = React.memo(({
  controller,
  isPortalInstance = false,
}) => {
  // If we are in the portal, we don't want borders/rounded classes, let it fill height/width.
  // If embedded, we want the default container styles.
  const containerClasses = isPortalInstance
    ? "flex flex-col h-full w-full bg-slate-50/30 dark:bg-zinc-950/20"
    : "flex flex-col h-[700px] border border-slate-200 dark:border-zinc-800 rounded-2xl bg-slate-50/50 dark:bg-zinc-900/30 overflow-hidden shadow-inner transition-all duration-300";

  return (
    <div className={containerClasses}>
      {/* Header with Search and Export options */}
      <ChatHeader
        isExpanded={controller.isExpanded}
        showSearch={controller.showSearch}
        setShowSearch={controller.setShowSearch}
        searchQuery={controller.searchQuery}
        setSearchQuery={controller.setSearchQuery}
        matchIndices={controller.matchIndices}
        currentMatchIdx={controller.currentMatchIdx}
        nextMatch={controller.nextMatch}
        prevMatch={controller.prevMatch}
        clearSearch={controller.clearSearch}
        openFullscreen={controller.openFullscreen}
        closeFullscreen={controller.closeFullscreen}
        exportMarkdown={controller.exportMarkdown}
        exportPDF={controller.exportPDF}
        isExporting={controller.isExporting}
        searchInputRef={controller.searchInputRef}
      />

      {/* Message History list */}
      <ChatMessages
        messages={controller.messages}
        isStreaming={controller.isStreaming}
        activePhase={controller.activePhase}
        streamError={controller.streamError}
        searchQuery={controller.searchQuery}
        matchIndices={controller.matchIndices}
        currentMatchIdx={controller.currentMatchIdx}
        scrollContainerRef={controller.scrollContainerRef}
        showScrollDownCta={controller.showScrollDownCta}
        onScroll={controller.handleScroll}
        forceScrollToBottom={controller.forceScrollToBottom}
        onEdit={(messageId) => {
          const text = controller.editPrompt(messageId);
          controller.setQuestion(text);
        }}
        onRegenerate={controller.regenerateLastResponse}
      />

      {/* Suggested chips panel (hidden during streaming or if empty) */}
      {!controller.isStreaming && (
        <ChatSuggestions
          suggestions={controller.suggestedQuestions}
          visible={controller.suggestionsVisible}
          onSuggestionClick={controller.askCopilot}
          disabled={controller.isStreaming}
        />
      )}

      {/* Chat Input form */}
      <ChatInput
        question={controller.question}
        setQuestion={controller.setQuestion}
        textareaRef={controller.textareaRef}
        onKeyDown={controller.handleKeyDown}
        onSubmit={() => {
          controller.askCopilot(controller.question);
          controller.setQuestion("");
        }}
        isStreaming={controller.isStreaming}
        onStop={controller.stopStreaming}
      />
    </div>
  );
});

ChatWorkspace.displayName = "ChatWorkspace";
