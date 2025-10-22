"""
Test the refactored citation flow end-to-end.

Tests:
- Citation extraction from response text
- Citation creation via ConversationManager
- Message storage with cited_source_ids
- Ollama API message filtering
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models import SearchResult, Citation, RAGResponse, Conversation
from app.rag.conversation_manager import ConversationManager
from app import main


def create_mock_search_result(source_id: str, title: str = "Test Paper") -> SearchResult:
    """Helper to create mock SearchResult."""
    return SearchResult(
        chunk_id=int(source_id),
        section="results",
        content="Test content about diabetes.",
        query="test query",
        similarity_score=0.95,
        document_id=1,
        source_id=source_id,
        title=title,
        authors=["Smith J", "Doe A"],
        publication_date="2024-01-01",
        journal="Test Journal",
        doi="10.1234/test"
    )


def test_citation_extraction_and_storage():
    """Test extracting citations from RAGResponse and storing them."""
    print("Test: Citation extraction and storage...")

    # Create mock RAGResponse
    response_text = "GLP-1 agonists improve glycemic control [PMC12345] and reduce risk [PMC67890]."
    chunks = [
        create_mock_search_result("12345", "GLP-1 Study"),
        create_mock_search_result("67890", "Risk Study")
    ]

    rag_response = RAGResponse(
        user_message="What are GLP-1 agonists?",
        generated_response=response_text,
        prompt_literature_chunks=chunks,
        llm_provider="ollama",
        generation_time_ms=1000.0,
        conversation_id="test-123"
    )

    # Create conversation using main's conversation_manager
    conv_id = main.conversation_manager.create_conversation()

    # Extract and store citations
    citations = main.extract_and_store_citations(rag_response, conv_id)

    # Assertions
    assert len(citations) == 2, f"Expected 2 citations, got {len(citations)}"
    assert citations[0].number == 1, f"First citation should be numbered 1, got {citations[0].number}"
    assert citations[0].source_id == "12345", f"First citation source_id wrong: {citations[0].source_id}"
    assert citations[1].number == 2, f"Second citation should be numbered 2, got {citations[1].number}"
    assert citations[1].source_id == "67890", f"Second citation source_id wrong: {citations[1].source_id}"

    print("  ✓ Extracted 2 citations correctly")
    print(f"  ✓ Citation 1: [{citations[0].number}] {citations[0].title}")
    print(f"  ✓ Citation 2: [{citations[1].number}] {citations[1].title}")


def test_comma_separated_citations():
    """Test extracting comma-separated citations."""
    print("\nTest: Comma-separated citations...")

    response_text = "Studies show benefits [PMC11111, PMC22222] in patients."
    chunks = [
        create_mock_search_result("11111", "Study A"),
        create_mock_search_result("22222", "Study B")
    ]

    rag_response = RAGResponse(
        user_message="Test question",
        generated_response=response_text,
        prompt_literature_chunks=chunks,
        llm_provider="ollama",
        generation_time_ms=1000.0,
        conversation_id="test-456"
    )

    conv_id = main.conversation_manager.create_conversation()
    citations = main.extract_and_store_citations(rag_response, conv_id)

    assert len(citations) == 2, f"Expected 2 citations from comma-separated, got {len(citations)}"
    assert citations[0].source_id == "11111"
    assert citations[1].source_id == "22222"

    print("  ✓ Extracted comma-separated citations correctly")


def test_message_storage_with_citations():
    """Test storing messages with cited_source_ids."""
    print("\nTest: Message storage with citations...")

    conv_id = main.conversation_manager.create_conversation()

    # Add user message
    main.conversation_manager.add_message(conv_id, "user", "What are GLP-1 agonists?")

    # Add assistant message with citations
    main.conversation_manager.add_message(
        conv_id,
        "assistant",
        "GLP-1 agonists improve glycemic control [PMC12345].",
        cited_source_ids=["12345"]
    )

    # Retrieve messages
    messages = main.conversation_manager.get_messages(conv_id)

    assert len(messages) == 2, f"Expected 2 messages, got {len(messages)}"
    assert messages[0]["role"] == "user"
    assert "cited_source_ids" not in messages[0], "User message should not have cited_source_ids"
    assert messages[1]["role"] == "assistant"
    assert "cited_source_ids" in messages[1], "Assistant message should have cited_source_ids"
    assert messages[1]["cited_source_ids"] == ["12345"], f"Wrong cited_source_ids: {messages[1]['cited_source_ids']}"

    print("  ✓ Messages stored correctly")
    print(f"  ✓ User message: no citations")
    print(f"  ✓ Assistant message: cited_source_ids = {messages[1]['cited_source_ids']}")


def test_multi_turn_citation_numbering():
    """Test conversation-wide citation numbering across turns."""
    print("\nTest: Multi-turn citation numbering...")

    conv_id = main.conversation_manager.create_conversation()

    # Turn 1: Cite PMC12345 and PMC67890
    chunks_1 = [
        create_mock_search_result("12345", "Paper A"),
        create_mock_search_result("67890", "Paper B")
    ]

    rag_1 = RAGResponse(
        user_message="Question 1",
        generated_response="Answer with [PMC12345] and [PMC67890].",
        prompt_literature_chunks=chunks_1,
        llm_provider="ollama",
        generation_time_ms=1000.0,
        conversation_id=conv_id
    )

    citations_1 = main.extract_and_store_citations(rag_1, conv_id)
    main.conversation_manager.add_message(conv_id, "user", "Question 1")
    main.conversation_manager.add_message(
        conv_id,
        "assistant",
        rag_1.generated_response,
        cited_source_ids=[c.source_id for c in citations_1]
    )

    # Turn 2: Cite PMC12345 again (should reuse number 1) and PMC99999 (new, should be 3)
    chunks_2 = [
        create_mock_search_result("12345", "Paper A"),  # Already cited
        create_mock_search_result("99999", "Paper C")   # New
    ]

    rag_2 = RAGResponse(
        user_message="Question 2",
        generated_response="Answer with [PMC12345] and [PMC99999].",
        prompt_literature_chunks=chunks_2,
        llm_provider="ollama",
        generation_time_ms=1000.0,
        conversation_id=conv_id
    )

    citations_2 = main.extract_and_store_citations(rag_2, conv_id)
    main.conversation_manager.add_message(conv_id, "user", "Question 2")
    main.conversation_manager.add_message(
        conv_id,
        "assistant",
        rag_2.generated_response,
        cited_source_ids=[c.source_id for c in citations_2]
    )

    # Verify numbering
    assert citations_1[0].number == 1, "Turn 1, citation 1 should be [1]"
    assert citations_1[1].number == 2, "Turn 1, citation 2 should be [2]"
    assert citations_2[0].number == 1, "Turn 2, PMC12345 should reuse [1]"
    assert citations_2[1].number == 3, "Turn 2, PMC99999 should be new [3]"

    # Verify messages
    messages = main.conversation_manager.get_messages(conv_id)
    assert len(messages) == 4, f"Expected 4 messages (2 turns), got {len(messages)}"
    assert messages[1]["cited_source_ids"] == ["12345", "67890"], "Turn 1 citations wrong"
    assert messages[3]["cited_source_ids"] == ["12345", "99999"], "Turn 2 citations wrong"

    print("  ✓ Turn 1: Cited [12345, 67890] → numbered [1, 2]")
    print("  ✓ Turn 2: Cited [12345, 99999] → numbered [1, 3] (reused 1, new 3)")
    print(f"  ✓ Turn 1 message citations: {messages[1]['cited_source_ids']}")
    print(f"  ✓ Turn 2 message citations: {messages[3]['cited_source_ids']}")


def test_ollama_message_filtering():
    """Test that cited_source_ids are filtered out for Ollama."""
    print("\nTest: Ollama message filtering...")

    from app.rag.generation import build_messages

    # Create conversation history with cited_source_ids
    conversation_history = [
        {"role": "user", "content": "Question 1"},
        {"role": "assistant", "content": "Answer 1 [PMC12345]", "cited_source_ids": ["12345"]},
        {"role": "user", "content": "Question 2"},
    ]

    chunks = [create_mock_search_result("67890", "Test")]

    # Build messages for Ollama
    ollama_messages = build_messages(
        user_message="Question 3",
        chunks=chunks,
        top_n=1,
        conversation_history=conversation_history
    )

    # Check that cited_source_ids are filtered out
    for msg in ollama_messages:
        if msg['role'] != 'system':  # Skip system prompt
            assert 'cited_source_ids' not in msg, f"Message should not have cited_source_ids: {msg}"
            assert 'role' in msg, "Message should have 'role'"
            assert 'content' in msg, "Message should have 'content'"

    print("  ✓ cited_source_ids filtered out from Ollama messages")
    print(f"  ✓ Ollama receives clean messages with only 'role' and 'content'")


def run_all_tests():
    """Run all tests and report results."""
    print("=" * 60)
    print("Testing Refactored Citation Flow")
    print("=" * 60)

    tests = [
        test_citation_extraction_and_storage,
        test_comma_separated_citations,
        test_message_storage_with_citations,
        test_multi_turn_citation_numbering,
        test_ollama_message_filtering,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n✗ FAILED: {test_func.__name__}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n✗ ERROR: {test_func.__name__}")
            print(f"  {type(e).__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
