"""
Response post-processing for OpenPharma RAG system.

Handles citation extraction and message formatting for frontend display.
"""
import re
from typing import List, Optional

from app.models import Citation, SearchResult
from app.rag.conversation_manager import ConversationManager


# Standardized heading patterns for consistent detection across streaming and non-streaming

# Matches: "## Answer", "##Answer", "## Answer:", "## Answer :", etc.
# \s* allows any whitespace between ## and Answer
# :? allows optional colon after Answer
# (?:^|\n) requires heading at start of string or after newline (prevents mid-sentence matches)
ANSWER_HEADING_PATTERN = r'(?:^|\n)\s*##\s*Answer\s*:?\s*'

# Matches multiple formats:
# - "## References"
# - "##References"
# - "## References:"
# - "References:"
# - "**References**" (bold markdown)
# (?:^|\n) requires heading at start of string or after newline (prevents mid-sentence matches)
REFERENCES_HEADING_PATTERN = r'(?:^|\n)\s*(?:##\s*References|References\s*:|[\*]{2}References[\*]{2})\s*:?\s*'


def strip_answer_heading(text: str) -> str:
    """
    Remove ## Answer heading from start of text.

    Matches: "## Answer", "##Answer", "## Answer:", etc.
    Must be at start of line or start of string.
    """
    # Strip from start only
    stripped = re.sub(r'^##\s*Answer\s*:?\s*\n?', '', text.strip(), flags=re.IGNORECASE | re.MULTILINE)
    # Clean up artifacts (leading colons/whitespace)
    return stripped.lstrip(': \t\n')


def strip_references_section(text: str) -> str:
    """
    Remove ## References section and everything after it.

    Matches: "## References", "##References", "## References:", "References:", "**References**"
    """
    return re.sub(
        REFERENCES_HEADING_PATTERN + r'.*$',
        '',
        text,
        flags=re.IGNORECASE | re.DOTALL | re.MULTILINE
    ).rstrip()


def extract_answer_section(text: str) -> str:
    """
    Extract only the answer section (content before ## References heading).

    Used for citation extraction to avoid counting sources listed in bibliography
    but not actually cited in the answer.
    """
    match = re.search(REFERENCES_HEADING_PATTERN, text, re.IGNORECASE)
    if match:
        return text[:match.start()]
    return text


def prepare_messages_for_display(messages: List[dict], conversation_id: str, conversation_manager: ConversationManager) -> List[dict]:
    """
    Prepare messages for frontend: strip headings, renumber citations [PMCxxxx] -> [1].
    """
    # Fetch citation mapping once for efficiency
    all_citations = conversation_manager.get_all_citations(conversation_id)
    pmc_to_number = {cit.source_id: cit.number for cit in all_citations}

    prepared_messages = []
    for msg in messages:
        if msg['role'] == 'assistant':
            content = msg['content']

            # Strip headings using standardized utilities
            content = strip_answer_heading(content)
            content = strip_references_section(content)

            # Replace all [PMCxxxx] with [number]
            # Supports both single citations [PMC123] and comma-separated [PMC123, PMC456]
            for source_id, number in pmc_to_number.items():
                # Pattern matches:
                # - [PMC123] -> [1]
                # - [PMC123, PMC456] -> [1, 2] (when both are replaced)
                # - [ PMC123 ] -> [1] (with whitespace)
                # - [PMC123,PMC456] -> [1,2] (no space after comma)
                # Uses lookahead to match PMC ID followed by comma, space, or closing bracket
                pattern = r'PMC' + source_id + r'(?=\s*[,\]])'
                content = re.sub(pattern, str(number), content)
            
            # Safety net: strip any remaining bare number brackets that leaked from source papers
            # Matches: [1], [2,3], [3-5], [6-11], [1,3-5,8]
            # Keeps brackets containing valid citation numbers, strips the rest
            valid_numbers = set(str(n) for n in pmc_to_number.values())
            def strip_invalid_citation(match):
                nums_in_bracket = re.findall(r'\d+', match.group(0))
                if any(n in valid_numbers for n in nums_in_bracket):
                    return match.group(0)
                return ''
            content = re.sub(r'\[[\d,\s\-]+\]', strip_invalid_citation, content)

            prepared_messages.append({
                'role': msg['role'],
                'content': content
            })
        else:
            # User messages pass through unchanged
            prepared_messages.append(msg)

    return prepared_messages


def extract_and_store_citations(
    generated_response: str,
    chunks: List[SearchResult],
    conversation_id: str,
    conversation_manager: ConversationManager
) -> List[Citation]:
    """
    Extracts [PMCxxxxx] citations from generated_response text, builds Citation
    objects, assigns conversation-wide numbers and store in conversation manager.

    Only extracts citations from the answer section (before ## References) to avoid
    counting sources listed in bibliography but not actually cited in the answer.
    """
    # Extract only the answer section using standardized utility
    answer_section = extract_answer_section(generated_response)

    # Extract all PMC IDs from brackets in answer section only
    cited_pmc_ids = []
    bracket_contents = re.findall(r'\[([^\]]+)\]', answer_section)
    for content in bracket_contents:
        # Extract PMC IDs, handling formats [PMC123], [PMC123, PMC456], [ PMC123 ], [PMC123,PMC456]
        pmcs = re.findall(r'PMC(\d+)', content)
        cited_pmc_ids.extend(pmcs)

    # Get unique PMC IDs, preserving order of first appearance
    seen = set()
    unique_pmc_ids = []
    for pmc_id in cited_pmc_ids:
        if pmc_id not in seen:
            seen.add(pmc_id)
            unique_pmc_ids.append(pmc_id)

    # Build lookup map: source_id -> SearchResult
    chunk_map = {chunk.source_id: chunk for chunk in chunks}

    # Build Citation objects via ConversationManager
    numbered_citations = []
    for pmc_id in unique_pmc_ids:
        chunk = chunk_map.get(pmc_id)
        if chunk:
            # Let ConversationManager create/retrieve Citation with proper number
            citation = conversation_manager.get_or_create_citation(
                conversation_id=conversation_id,
                chunk=chunk
            )
            numbered_citations.append(citation)

    return numbered_citations