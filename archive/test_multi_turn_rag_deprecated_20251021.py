"""
Integration tests for multi-turn RAG conversations with conversation-wide citation numbering.

Tests the full flow: ConversationManager + citation renumbering + multi-turn context.
"""
import unittest
from app.rag.generation import extract_citations_with_pmc_ids, Citation, RAGResponse
from app.rag.conversation_manager import ConversationManager
from app.retrieval import SearchResult
from app import main  # Import module to access conversation_manager


def create_mock_chunk(source_id: str, title: str, journal: str = "Test Journal") -> SearchResult:
    """Helper to create mock SearchResult objects for testing."""
    return SearchResult(
        chunk_id=1,
        section="results",
        content="Test content",
        query="test query",
        similarity_score=0.9,
        document_id=1,
        source_id=source_id,
        title=title,
        authors=["Author A", "Author B"],
        publication_date="2024-01-01",
        journal=journal,
        doi="10.1234/test"
    )


class TestExtractCitationsWithPMCIds(unittest.TestCase):
    """Test the extract_citations_with_pmc_ids function (keeps PMC format)."""

    def test_extract_keeps_pmc_format(self):
        """Test that extraction keeps [PMC...] format in answer text."""
        answer_text = "GLP-1 agonists improve glycemic control [PMC12345678]."
        chunks = [create_mock_chunk("12345678", "Test Paper 1")]

        result_text, citations = extract_citations_with_pmc_ids(answer_text, chunks)

        # Should NOT renumber yet - keeps PMC format
        assert result_text == "GLP-1 agonists improve glycemic control [PMC12345678]."
        assert len(citations) == 1
        assert citations[0].number == 0  # Placeholder
        assert citations[0].source_id == "12345678"
        assert citations[0].title == "Test Paper 1"

    def test_extract_multiple_citations(self):
        """Test extracting multiple citations."""
        answer_text = "Studies show benefits [PMC11111111, PMC22222222] in patients."
        chunks = [
            create_mock_chunk("11111111", "Study A"),
            create_mock_chunk("22222222", "Study B")
        ]

        result_text, citations = extract_citations_with_pmc_ids(answer_text, chunks)

        assert "[PMC11111111, PMC22222222]" in result_text
        assert len(citations) == 2
        assert all(c.number == 0 for c in citations)  # All placeholders


class TestConversationWideRenumbering(unittest.TestCase):
    """Test conversation-wide citation numbering across multiple turns."""

    def setUp(self):
        """Set up - use global conversation manager from main.py."""
        self.manager = main.conversation_manager

    def test_single_turn_renumbering(self):
        """Test basic renumbering for a single turn."""
        conv_id = self.manager.create_conversation()

        # Simulate RAGResponse with PMC IDs
        mock_response = RAGResponse(
            user_message="What is metformin?",
            generated_response="Metformin is used for diabetes [PMC12345].",
            response_citations=[
                Citation(number=0, title="Study A", journal="Journal", source_id="12345")
            ],
            chunks_used=[],
            llm_provider="ollama",
            generation_time_ms=100.0,
            conversation_id=conv_id
        )

        # Renumber using conversation manager
        result = main.renumber_and_store_citations_for_conversation(mock_response, conv_id)

        assert result.generated_response == "Metformin is used for diabetes [1]."
        assert result.response_citations[0].number == 1

    def test_multi_turn_citation_reuse(self):
        """Test that citations are reused across turns in same conversation."""
        conv_id = self.manager.create_conversation()

        # Turn 1: Cite PMC12345 and PMC67890
        mock_response1 = RAGResponse(
            user_message="What is metformin?",
            generated_response="Metformin [PMC12345] is used with GLP-1s [PMC67890].",
            response_citations=[
                Citation(number=0, title="Study A", journal="Journal", source_id="12345"),
                Citation(number=0, title="Study B", journal="Journal", source_id="67890")
            ],
            chunks_used=[],
            llm_provider="ollama",
            generation_time_ms=100.0,
            conversation_id=conv_id
        )

        result1 = main.renumber_and_store_citations_for_conversation(mock_response1, conv_id)
        assert result1.generated_response == "Metformin [1] is used with GLP-1s [2]."
        assert result1.response_citations[0].number == 1
        assert result1.response_citations[1].number == 2

        # Turn 2: Cite PMC12345 again (should reuse [1]) and new PMC99999
        mock_response2 = RAGResponse(
            user_message="What about side effects?",
            generated_response="Metformin [PMC12345] may cause issues [PMC99999].",
            response_citations=[
                Citation(number=0, title="Study A", journal="Journal", source_id="12345"),
                Citation(number=0, title="Study C", journal="Journal", source_id="99999")
            ],
            chunks_used=[],
            llm_provider="ollama",
            generation_time_ms=100.0,
            conversation_id=conv_id
        )

        result2 = main.renumber_and_store_citations_for_conversation(mock_response2, conv_id)

        # PMC12345 should still be [1], new PMC99999 should be [3]
        assert result2.generated_response == "Metformin [1] may cause issues [3]."
        assert result2.response_citations[0].number == 1  # Reused
        assert result2.response_citations[1].number == 3  # New (next available)

    def test_multi_turn_citation_consistency(self):
        """Test that citation numbers remain consistent throughout conversation."""
        conv_id = self.manager.create_conversation()

        # Turn 1
        cit1 = Citation(number=0, title="A", journal="J", source_id="12345")
        cit2 = Citation(number=0, title="B", journal="J", source_id="67890")
        self.manager.get_or_store_citation(conv_id, cit1)  # Gets 1
        self.manager.get_or_store_citation(conv_id, cit2)  # Gets 2

        # Turn 2
        cit1_again = Citation(number=0, title="A", journal="J", source_id="12345")
        num_reused = self.manager.get_or_store_citation(conv_id, cit1_again)
        assert num_reused == 1  # Same as turn 1

        # Turn 3
        cit3 = Citation(number=0, title="C", journal="J", source_id="99999")
        num_new = self.manager.get_or_store_citation(conv_id, cit3)
        assert num_new == 3  # Sequential after 1, 2

        # Turn 4 - reuse multiple
        cit1_again2 = Citation(number=0, title="A", journal="J", source_id="12345")
        cit2_again = Citation(number=0, title="B", journal="J", source_id="67890")
        num1 = self.manager.get_or_store_citation(conv_id, cit1_again2)
        num2 = self.manager.get_or_store_citation(conv_id, cit2_again)
        assert num1 == 1
        assert num2 == 2

    def test_different_conversations_isolated(self):
        """Test that different conversations have independent citation numbering."""
        conv_id1 = self.manager.create_conversation()
        conv_id2 = self.manager.create_conversation()

        # Both conversations cite same PMC ID
        cit1_conv1 = Citation(number=0, title="A", journal="J", source_id="12345")
        cit1_conv2 = Citation(number=0, title="A", journal="J", source_id="12345")
        num1 = self.manager.get_or_store_citation(conv_id1, cit1_conv1)
        num2 = self.manager.get_or_store_citation(conv_id2, cit1_conv2)

        # Both should get [1] in their respective conversations
        assert num1 == 1
        assert num2 == 1

        # Verify isolation with second citation
        cit2_conv1 = Citation(number=0, title="B", journal="J", source_id="67890")
        cit2_conv2 = Citation(number=0, title="C", journal="J", source_id="99999")
        num1_b = self.manager.get_or_store_citation(conv_id1, cit2_conv1)
        num2_b = self.manager.get_or_store_citation(conv_id2, cit2_conv2)

        assert num1_b == 2  # Conv1: [1]=12345, [2]=67890
        assert num2_b == 2  # Conv2: [1]=12345, [2]=99999

    def test_renumbering_with_duplicate_citations(self):
        """Test renumbering when same PMC appears multiple times in one response."""
        conv_id = self.manager.create_conversation()

        mock_response = RAGResponse(
            user_message="Test",
            generated_response="First [PMC12345] and second [PMC12345] mention.",
            response_citations=[
                Citation(number=0, title="Study A", journal="Journal", source_id="12345")
            ],
            chunks_used=[],
            llm_provider="ollama",
            generation_time_ms=100.0,
            conversation_id=conv_id
        )

        result = main.renumber_and_store_citations_for_conversation(mock_response, conv_id)

        # Both mentions should become [1]
        assert result.generated_response == "First [1] and second [1] mention."
        assert len(result.response_citations) == 1
        assert result.response_citations[0].number == 1

    def test_complex_multi_turn_scenario(self):
        """Test complex scenario with multiple turns and overlapping citations."""
        conv_id = self.manager.create_conversation()

        # Turn 1: Introduce A, B, C
        mock1 = RAGResponse(
            user_message="What drugs exist?",
            generated_response="Drug A [PMCAAA], B [PMCBBB], C [PMCCCC].",
            response_citations=[
                Citation(number=0, title="A", journal="J", source_id="AAA"),
                Citation(number=0, title="B", journal="J", source_id="BBB"),
                Citation(number=0, title="C", journal="J", source_id="CCC")
            ],
            chunks_used=[], llm_provider="ollama", generation_time_ms=100.0,
            conversation_id=conv_id
        )
        result1 = main.renumber_and_store_citations_for_conversation(mock1, conv_id)
        assert "A [1], B [2], C [3]" in result1.generated_response

        # Turn 2: Reuse A, introduce D
        mock2 = RAGResponse(
            user_message="Tell me about A",
            generated_response="Drug A [PMCAAA] works with D [PMCDDD].",
            response_citations=[
                Citation(number=0, title="A", journal="J", source_id="AAA"),
                Citation(number=0, title="D", journal="J", source_id="DDD")
            ],
            chunks_used=[], llm_provider="ollama", generation_time_ms=100.0,
            conversation_id=conv_id
        )
        result2 = main.renumber_and_store_citations_for_conversation(mock2, conv_id)
        assert result2.generated_response == "Drug A [1] works with D [4]."

        # Turn 3: Mix of old and new
        mock3 = RAGResponse(
            user_message="Compare them",
            generated_response="B [PMCBBB] vs D [PMCDDD] vs E [PMCEEE].",
            response_citations=[
                Citation(number=0, title="B", journal="J", source_id="BBB"),
                Citation(number=0, title="D", journal="J", source_id="DDD"),
                Citation(number=0, title="E", journal="J", source_id="EEE")
            ],
            chunks_used=[], llm_provider="ollama", generation_time_ms=100.0,
            conversation_id=conv_id
        )
        result3 = main.renumber_and_store_citations_for_conversation(mock3, conv_id)
        assert result3.generated_response == "B [2] vs D [4] vs E [5]."

        # Verify final mapping
        mapping = self.manager.get_citation_mapping(conv_id)
        assert mapping == {"AAA": 1, "BBB": 2, "CCC": 3, "DDD": 4, "EEE": 5}


if __name__ == "__main__":
    unittest.main()
