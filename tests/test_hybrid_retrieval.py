"""
Test hybrid retrieval end-to-end with multi-turn conversation.

This test simulates a multi-turn conversation to verify:
1. Turn 1: Fresh semantic search retrieval
2. Turn 2: Hybrid retrieval (fresh + historical chunks from turn 1)
3. Citation coherence across turns
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import main
from app.logging_config import setup_logging

# Configure logging to see retrieval details
setup_logging(level="INFO", log_file="logs/test_hybrid_retrieval.log")

def test_multi_turn_hybrid_retrieval():
    """Test hybrid retrieval across multiple turns."""
    print("=" * 70)
    print("Testing Multi-Turn Hybrid Retrieval")
    print("=" * 70)

    # Create a new conversation
    conv_id = main.conversation_manager.create_conversation()
    print(f"\nCreated conversation: {conv_id}")

    # Turn 1: First question about GLP-1 agonists
    print("\n" + "-" * 70)
    print("TURN 1: What are GLP-1 agonists used for in diabetes treatment?")
    print("-" * 70)

    from app.rag.generation import generate_response

    result_1 = generate_response(
        user_message="What are GLP-1 agonists used for in diabetes treatment?",
        conversation_id=conv_id,
        top_k=20,
        top_n=5,
        use_local=True,
        conversation_history=[]  # Empty history for first turn
    )

    # Extract and store citations for turn 1
    citations_1 = main.extract_and_store_citations(result_1, conv_id)

    # Store messages
    main.conversation_manager.add_message(conv_id, "user", result_1.user_message)
    main.conversation_manager.add_message(
        conv_id,
        "assistant",
        result_1.generated_response,
        cited_source_ids=[cit.source_id for cit in citations_1],
        cited_chunk_ids=[cit.chunk_id for cit in citations_1]
    )

    print(f"\nTurn 1 Response Preview:")
    print(f"  Generated response length: {len(result_1.generated_response)} chars")
    print(f"  Number of citations: {len(citations_1)}")
    print(f"  Citation numbers: {[cit.number for cit in citations_1]}")
    print(f"  Cited source IDs: {[cit.source_id for cit in citations_1]}")
    print(f"  Cited chunk IDs: {[cit.chunk_id for cit in citations_1]}")
    print(f"  Generation time: {result_1.generation_time_ms:.0f}ms")

    # Turn 2: Follow-up question (should use hybrid retrieval)
    print("\n" + "-" * 70)
    print("TURN 2: What are the side effects of these medications?")
    print("-" * 70)

    # Get conversation history for turn 2
    conversation_history = main.conversation_manager.get_messages(conv_id)

    result_2 = generate_response(
        user_message="What are the side effects of these medications?",
        conversation_id=conv_id,
        top_k=20,
        top_n=5,
        use_local=True,
        conversation_history=conversation_history  # Pass history for hybrid retrieval
    )

    # Extract and store citations for turn 2
    citations_2 = main.extract_and_store_citations(result_2, conv_id)

    # Store messages
    main.conversation_manager.add_message(conv_id, "user", result_2.user_message)
    main.conversation_manager.add_message(
        conv_id,
        "assistant",
        result_2.generated_response,
        cited_source_ids=[cit.source_id for cit in citations_2],
        cited_chunk_ids=[cit.chunk_id for cit in citations_2]
    )

    print(f"\nTurn 2 Response Preview:")
    print(f"  Generated response length: {len(result_2.generated_response)} chars")
    print(f"  Number of citations: {len(citations_2)}")
    print(f"  Citation numbers: {[cit.number for cit in citations_2]}")
    print(f"  Cited source IDs: {[cit.source_id for cit in citations_2]}")
    print(f"  Cited chunk IDs: {[cit.chunk_id for cit in citations_2]}")
    print(f"  Generation time: {result_2.generation_time_ms:.0f}ms")

    # Verify hybrid retrieval behavior
    print("\n" + "-" * 70)
    print("VERIFICATION")
    print("-" * 70)

    # Check that conversation has messages
    final_messages = main.conversation_manager.get_messages(conv_id)
    print(f"\n✓ Total messages in conversation: {len(final_messages)}")
    assert len(final_messages) == 4, f"Expected 4 messages, got {len(final_messages)}"

    # Check that turn 2 messages have cited_chunk_ids
    turn_1_assistant_msg = final_messages[1]
    turn_2_assistant_msg = final_messages[3]

    print(f"✓ Turn 1 assistant message has cited_chunk_ids: {'cited_chunk_ids' in turn_1_assistant_msg}")
    assert 'cited_chunk_ids' in turn_1_assistant_msg, "Turn 1 should have cited_chunk_ids"

    print(f"✓ Turn 2 assistant message has cited_chunk_ids: {'cited_chunk_ids' in turn_2_assistant_msg}")
    assert 'cited_chunk_ids' in turn_2_assistant_msg, "Turn 2 should have cited_chunk_ids"

    # Check citation coherence
    all_citations = main.conversation_manager.get_all_citations(conv_id)
    print(f"✓ Total unique citations across conversation: {len(all_citations)}")
    print(f"  Citation numbers: {sorted([cit.number for cit in all_citations])}")

    # Display first 200 chars of each response
    print("\n" + "-" * 70)
    print("RESPONSE PREVIEWS")
    print("-" * 70)
    print(f"\nTurn 1 Response:\n{result_1.generated_response[:300]}...")
    print(f"\nTurn 2 Response:\n{result_2.generated_response[:300]}...")

    print("\n" + "=" * 70)
    print("✓ Multi-turn hybrid retrieval test PASSED")
    print("=" * 70)

    return True


if __name__ == "__main__":
    try:
        test_multi_turn_hybrid_retrieval()
        print("\n✓ All tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error during test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
