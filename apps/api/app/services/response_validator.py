import re
import logging

logger = logging.getLogger(__name__)

def validate_and_repair_response(text: str) -> str:
    """
    Validate and repair formatting issues in the assistant's generated output.
    Never modifies factual content, only formatting syntax.
    """
    if not text or not text.strip():
        return "I apologize, but I received an empty response. Please let me know how I can assist you with your dataset."

    # 1. Heading Repair: e.g., '##Heading' -> '## Heading'
    text = re.sub(r'^(#{1,6})([^#\s])', r'\1 \2', text, flags=re.MULTILINE)

    # 2. Paragraph Deduplication: Remove repeating identical paragraph blocks
    paragraphs = text.split("\n\n")
    unique_paragraphs = []
    seen = set()
    for p in paragraphs:
        p_strip = p.strip()
        # Only deduplicate longer blocks to avoid stripping list items or small headers
        if p_strip and len(p_strip) > 40:
            # Simple content normalization for checking duplicates
            normalized = re.sub(r'\s+', ' ', p_strip).lower()
            if normalized in seen:
                logger.info(f"ResponseValidator: Deduplicated repeating paragraph block: {p_strip[:30]}...")
                continue
            seen.add(normalized)
        unique_paragraphs.append(p)
    text = "\n\n".join(unique_paragraphs)

    # 3. Code Fences Repair: Close any unclosed code blocks
    code_fence_count = text.count("```")
    if code_fence_count % 2 != 0:
        logger.info("ResponseValidator: Closing unclosed code block fence.")
        text += "\n```\n"

    # 4. Table Format Repair: Ensure table rows are complete
    lines = text.split("\n")
    table_open = False
    repaired_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            table_open = True
            # Ensure row ends with pipe
            if not stripped.endswith("|"):
                line = line + " |"
        else:
            if table_open:
                table_open = False
        repaired_lines.append(line)
    
    text = "\n".join(repaired_lines)
    return text
