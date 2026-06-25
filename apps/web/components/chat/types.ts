export interface MessageMetadata {
  response_id: string;
  timestamp: string;
  generation_time: number;
  model_used: string;
  provider_used: string;
  response_length: number;
  streamed: boolean;
  edited?: boolean;
  edited_at?: string | null;
  retry_count?: number;
  latency_ms?: number;
}

export interface Message {
  id: string;
  parent_id?: string | null;
  branch_ids?: string[];
  role: "user" | "assistant";
  message: string;
  metadata?: MessageMetadata;
}

export type StreamStatus = "Thinking" | "Analyzing Dataset" | "Generating Response" | "Finalizing" | null;

export interface StreamEvent {
  type: "status" | "content" | "metadata" | "suggestions" | "error" | "done";
  payload: any;
}

export interface ConversationState {
  messages: Message[];
  isExpanded: boolean;
  isStreaming: boolean;
  activePhase: StreamStatus;
  searchQuery: string;
}
