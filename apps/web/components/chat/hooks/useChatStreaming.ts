import { useState, useRef, useCallback, useEffect } from "react";
import { Message, StreamStatus, StreamEvent } from "../types";
import { postJSONStream } from "@/lib/api";
import { sanitizeStreamingMarkdown } from "../utils/markdown";
import { STREAMING_SPEEDS } from "../constants";

export function useChatStreaming(
  datasetId: string,
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>,
  setSuggestedQuestions: React.Dispatch<React.SetStateAction<string[]>>
) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [activePhase, setActivePhase] = useState<StreamStatus>(null);
  const [streamError, setStreamError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const tokenQueueRef = useRef<string[]>([]);
  const animFrameIdRef = useRef<number | null>(null);
  const streamEndedRef = useRef(false);

  // Clean up streaming on unmount
  useEffect(() => {
    return () => {
      if (animFrameIdRef.current) cancelAnimationFrame(animFrameIdRef.current);
    };
  }, []);

  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (animFrameIdRef.current) {
      cancelAnimationFrame(animFrameIdRef.current);
      animFrameIdRef.current = null;
    }
    
    // Flush remaining buffered tokens
    const remainingText = tokenQueueRef.current.join("");
    if (remainingText) {
      setMessages((prev) => {
        const lastIdx = prev.length - 1;
        if (lastIdx >= 0 && prev[lastIdx].role === "assistant") {
          return [
            ...prev.slice(0, lastIdx),
            {
              ...prev[lastIdx],
              message: prev[lastIdx].message + remainingText,
            },
          ];
        }
        return prev;
      });
    }

    tokenQueueRef.current = [];
    setIsStreaming(false);
    setActivePhase(null);
  }, [setMessages]);

  const startStreaming = useCallback(
    async (text: string, isRegenerate: boolean = false) => {
      stopStreaming();
      setStreamError(null);
      setIsStreaming(true);
      setActivePhase("Thinking");
      streamEndedRef.current = false;

      // Add user prompt and placeholder for assistant response
      const userMsgId = `msg-${Date.now()}-user`;
      const assistantMsgId = `msg-${Date.now()}-assistant`;
      const userMsg: Message = {
        id: userMsgId,
        role: "user",
        message: text,
        metadata: {
          response_id: userMsgId,
          timestamp: new Date().toISOString(),
          generation_time: 0,
          model_used: "User",
          provider_used: "Client",
          response_length: text.length,
          streamed: false,
        },
      };
      
      const assistantPlaceholder: Message = {
        id: assistantMsgId,
        parent_id: userMsgId,
        role: "assistant",
        message: "",
        metadata: {
          response_id: assistantMsgId,
          timestamp: new Date().toISOString(),
          generation_time: 0,
          model_used: "Pending",
          provider_used: "Pending",
          response_length: 0,
          streamed: true,
        },
      };

      setMessages((prev) => [...prev, userMsg, assistantPlaceholder]);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      // Setup animFrame loop to pull tokens from queue smoothly
      let accumulatedText = "";
      
      const startLoop = () => {
        const tick = () => {
          const queue = tokenQueueRef.current;
          if (queue.length === 0) {
            if (streamEndedRef.current) {
              setIsStreaming(false);
              setActivePhase(null);
              animFrameIdRef.current = null;
              return;
            }
            animFrameIdRef.current = requestAnimationFrame(tick);
            return;
          }

          // Dynamic rendering speeds to catch up if queue is large
          let tokensToConsume = STREAMING_SPEEDS.normalSpeed;
          if (queue.length > STREAMING_SPEEDS.queueThresholdCatchUp) {
            tokensToConsume = STREAMING_SPEEDS.flushSpeed;
          } else if (queue.length > STREAMING_SPEEDS.queueThresholdNormal) {
            tokensToConsume = STREAMING_SPEEDS.catchUpSpeed;
          }

          const tokens = queue.slice(0, tokensToConsume);
          tokenQueueRef.current = queue.slice(tokensToConsume);

          accumulatedText += tokens.join("");

          // Safety buffer check: delay showing incomplete fences/tables
          const safeText = sanitizeStreamingMarkdown(accumulatedText);

          setMessages((prev) => {
            const lastIdx = prev.length - 1;
            if (lastIdx >= 0 && prev[lastIdx].role === "assistant") {
              return [
                ...prev.slice(0, lastIdx),
                {
                  ...prev[lastIdx],
                  message: safeText || prev[lastIdx].message,
                },
              ];
            }
            return prev;
          });

          animFrameIdRef.current = requestAnimationFrame(tick);
        };
        animFrameIdRef.current = requestAnimationFrame(tick);
      };

      startLoop();

      try {
        await postJSONStream(
          `/datasets/${datasetId}/copilot/stream`,
          { message: text },
          (event: StreamEvent) => {
            if (event.type === "status") {
              setActivePhase(event.payload.status);
            } else if (event.type === "content") {
              // Hide status since content starts rendering
              setActivePhase(null);
              tokenQueueRef.current.push(event.payload.text);
            } else if (event.type === "metadata") {
              // Update assistant message metadata block
              setMessages((prev) => {
                const lastIdx = prev.length - 1;
                if (lastIdx >= 0 && prev[lastIdx].role === "assistant") {
                  const updated = { ...prev[lastIdx] };
                  updated.metadata = { ...updated.metadata, ...event.payload };
                  return [...prev.slice(0, lastIdx), updated];
                }
                return prev;
              });
            } else if (event.type === "suggestions") {
              setSuggestedQuestions(event.payload.questions);
            } else if (event.type === "error") {
              setStreamError(event.payload.message);
            }
          },
          controller.signal
        );
        streamEndedRef.current = true;
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setStreamError(err instanceof Error ? err.message : "Connection interrupted.");
        setIsStreaming(false);
        setActivePhase(null);
      } finally {
        abortControllerRef.current = null;
      }
    },
    [datasetId, stopStreaming, setMessages, setSuggestedQuestions]
  );

  return {
    isStreaming,
    activePhase,
    streamError,
    startStreaming,
    stopStreaming,
  };
}
