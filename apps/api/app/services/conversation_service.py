import uuid
from datetime import datetime
import logging
from app.services.conversation_context import resolve_contextual_question, update_conversation_context

logger = logging.getLogger(__name__)

def create_message(role: str, content: str, parent_id: str = None, metadata: dict = None) -> dict:
    """Create a standardized message object with future-ready branching metadata."""
    msg_id = str(uuid.uuid4())
    now_iso = datetime.utcnow().isoformat() + "Z"
    
    meta_defaults = {
        "response_id": msg_id,
        "timestamp": now_iso,
        "generation_time": 0.0,
        "model_used": "Unknown",
        "provider_used": "Unknown",
        "response_length": len(content),
        "streamed": True,
        "edited": False,
        "edited_at": None,
        "retry_count": 0,
        "latency_ms": 0.0
    }
    if metadata:
        meta_defaults.update(metadata)

    return {
        "id": msg_id,
        "parent_id": parent_id,
        "branch_ids": [],
        "role": role,
        "message": content,
        "metadata": meta_defaults
    }

def edit_message_history(history: list[dict], message_id: str, new_text: str) -> list[dict]:
    """
    Handle message edits:
    Locate message_id in history, slice out all downstream conversation blocks,
    and update the user prompt at that index.
    """
    target_idx = -1
    for i, msg in enumerate(history):
        if msg.get("id") == message_id:
            target_idx = i
            break

    if target_idx == -1:
        logger.warning(f"Message ID {message_id} not found in conversation history.")
        return history

    # Create new sliced history up to the edited message
    sliced_history = history[:target_idx]
    
    parent_id = sliced_history[-1]["id"] if sliced_history else None
    
    # Archive the old message ID in branch_ids of the new edited message to preserve relations
    old_msg = history[target_idx]
    edited_msg = create_message("user", new_text, parent_id=parent_id)
    edited_msg["branch_ids"].append(old_msg["id"])
    edited_msg["metadata"]["edited"] = True
    edited_msg["metadata"]["edited_at"] = datetime.utcnow().isoformat() + "Z"

    sliced_history.append(edited_msg)
    logger.info(f"ConversationHistory: Edited message {message_id}, pruned downstream history.")
    return sliced_history

def prune_conversation_history(history: list[dict], max_messages: int = 20) -> list[dict]:
    """Prune conversation history keeping the link relationships clean."""
    if len(history) <= max_messages:
        return history
    
    pruned = history[-max_messages:]
    # Fix the first pruned message parent_id to prevent dangling pointers
    if pruned:
        pruned[0]["parent_id"] = None
    return pruned
