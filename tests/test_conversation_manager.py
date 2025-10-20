"""
Tests for ConversationManager and conversation-wide citation numbering.
"""
import unittest
import time
from app.rag.conversation_manager import ConversationManager, Conversation


class TestConversationManager(unittest.TestCase):
    """Test suite for ConversationManager."""

    def test_create_conversation(self):
        """Test creating a new conversation returns a UUID."""
        manager = ConversationManager()
        conv_id = manager.create_conversation()

        assert isinstance(conv_id, str)
        assert len(conv_id) == 36  # UUID format
        assert conv_id in manager.conversations

    def test_get_conversation(self):
        """Test retrieving an existing conversation."""
        manager = ConversationManager()
        conv_id = manager.create_conversation()

        conversation = manager.get_conversation(conv_id)

        assert conversation is not None
        assert conversation.conversation_id == conv_id
        assert isinstance(conversation.messages, list)
        assert len(conversation.messages) == 0

    def test_get_nonexistent_conversation(self):
        """Test retrieving a conversation that doesn't exist returns None."""
        manager = ConversationManager()

        conversation = manager.get_conversation("nonexistent-id")

        assert conversation is None

    def test_get_conversation_updates_last_accessed(self):
        """Test that getting a conversation updates its last_accessed timestamp."""
        manager = ConversationManager()
        conv_id = manager.create_conversation()

        conversation = manager.get_conversation(conv_id)
        initial_time = conversation.last_accessed

        time.sleep(0.1)
        conversation = manager.get_conversation(conv_id)
        updated_time = conversation.last_accessed

        assert updated_time > initial_time

    def test_add_message(self):
        """Test adding messages to a conversation."""
        manager = ConversationManager()
        conv_id = manager.create_conversation()

        manager.add_message(conv_id, "user", "What is metformin?")
        manager.add_message(conv_id, "assistant", "Metformin is a medication...")

        messages = manager.get_messages(conv_id)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "What is metformin?"
        assert messages[1]["role"] == "assistant"

    def test_add_message_to_nonexistent_conversation(self):
        """Test that adding a message to nonexistent conversation raises error."""
        manager = ConversationManager()

        with self.assertRaises(ValueError):
            manager.add_message("nonexistent-id", "user", "Hello")

    def test_get_messages_empty_conversation(self):
        """Test getting messages from a conversation with no messages."""
        manager = ConversationManager()
        conv_id = manager.create_conversation()

        messages = manager.get_messages(conv_id)

        assert messages == []

    def test_get_messages_nonexistent_conversation(self):
        """Test getting messages from nonexistent conversation returns empty list."""
        manager = ConversationManager()

        messages = manager.get_messages("nonexistent-id")

        assert messages == []

    def test_get_or_store_citation_new_source(self):
        """Test storing new citation and assigning citation number."""
        manager = ConversationManager()
        conv_id = manager.create_conversation()

        from app.rag.generation import Citation
        citation = Citation(number=0, title="Test", journal="J", source_id="12345")
        citation_num = manager.get_or_store_citation(conv_id, citation)

        assert citation_num == 1

    def test_get_or_store_citation_existing_source(self):
        """Test retrieving existing citation number for same source_id."""
        manager = ConversationManager()
        conv_id = manager.create_conversation()

        from app.rag.generation import Citation
        citation1 = Citation(number=0, title="Test", journal="J", source_id="12345")
        citation2 = Citation(number=0, title="Test", journal="J", source_id="12345")

        first_num = manager.get_or_store_citation(conv_id, citation1)
        second_num = manager.get_or_store_citation(conv_id, citation2)

        assert first_num == second_num == 1

    def test_citation_numbering_sequence(self):
        """Test that citation numbers are assigned sequentially."""
        manager = ConversationManager()
        conv_id = manager.create_conversation()

        from app.rag.generation import Citation
        cit1 = Citation(number=0, title="A", journal="J", source_id="12345")
        cit2 = Citation(number=0, title="B", journal="J", source_id="67890")
        cit3 = Citation(number=0, title="C", journal="J", source_id="11111")

        num1 = manager.get_or_store_citation(conv_id, cit1)
        num2 = manager.get_or_store_citation(conv_id, cit2)
        num3 = manager.get_or_store_citation(conv_id, cit3)

        assert num1 == 1
        assert num2 == 2
        assert num3 == 3

    def test_citation_numbering_across_turns(self):
        """Test that citation numbers persist across multiple turns."""
        manager = ConversationManager()
        conv_id = manager.create_conversation()

        from app.rag.generation import Citation

        # Turn 1: Cite PMC12345 and PMC67890
        cit1 = Citation(number=0, title="A", journal="J", source_id="12345")
        cit2 = Citation(number=0, title="B", journal="J", source_id="67890")
        manager.get_or_store_citation(conv_id, cit1)  # Gets 1
        manager.get_or_store_citation(conv_id, cit2)  # Gets 2

        # Turn 2: Cite PMC12345 again (should still be 1) and new PMC99999
        cit1_again = Citation(number=0, title="A", journal="J", source_id="12345")
        cit3 = Citation(number=0, title="C", journal="J", source_id="99999")
        num_reused = manager.get_or_store_citation(conv_id, cit1_again)
        num_new = manager.get_or_store_citation(conv_id, cit3)

        assert num_reused == 1  # Reused from turn 1
        assert num_new == 3     # New citation gets next number

    def test_get_or_store_citation_nonexistent_conversation(self):
        """Test that storing citation for nonexistent conversation raises error."""
        manager = ConversationManager()

        from app.rag.generation import Citation
        citation = Citation(number=0, title="Test", journal="J", source_id="12345")

        with self.assertRaises(ValueError):
            manager.get_or_store_citation("nonexistent-id", citation)

    def test_get_citation_mapping(self):
        """Test retrieving the full citation mapping."""
        manager = ConversationManager()
        conv_id = manager.create_conversation()

        from app.rag.generation import Citation
        cit1 = Citation(number=0, title="A", journal="J", source_id="12345")
        cit2 = Citation(number=0, title="B", journal="J", source_id="67890")

        manager.get_or_store_citation(conv_id, cit1)
        manager.get_or_store_citation(conv_id, cit2)

        mapping = manager.get_citation_mapping(conv_id)

        assert mapping == {"12345": 1, "67890": 2}

    def test_get_citation_mapping_empty(self):
        """Test getting citation mapping from conversation with no citations."""
        manager = ConversationManager()
        conv_id = manager.create_conversation()

        mapping = manager.get_citation_mapping(conv_id)

        assert mapping == {}

    def test_get_citation_mapping_nonexistent_conversation(self):
        """Test getting mapping from nonexistent conversation returns empty dict."""
        manager = ConversationManager()

        mapping = manager.get_citation_mapping("nonexistent-id")

        assert mapping == {}

    def test_cleanup_old_conversations(self):
        """Test that old conversations are cleaned up."""
        manager = ConversationManager(max_age_seconds=0.1)  # 100ms

        conv_id1 = manager.create_conversation()
        time.sleep(0.15)  # Wait for conversation to become stale
        conv_id2 = manager.create_conversation()

        removed_count = manager.cleanup_old_conversations()

        assert removed_count == 1
        assert conv_id1 not in manager.conversations
        assert conv_id2 in manager.conversations

    def test_cleanup_keeps_recently_accessed_conversations(self):
        """Test that recently accessed conversations are not cleaned up."""
        manager = ConversationManager(max_age_seconds=0.1)

        conv_id = manager.create_conversation()
        time.sleep(0.05)
        manager.get_conversation(conv_id)  # Access to update timestamp
        time.sleep(0.07)

        removed_count = manager.cleanup_old_conversations()

        assert removed_count == 0
        assert conv_id in manager.conversations

    def test_cleanup_no_conversations(self):
        """Test cleanup when there are no conversations."""
        manager = ConversationManager()

        removed_count = manager.cleanup_old_conversations()

        assert removed_count == 0

    def test_lazy_cleanup_trigger(self):
        """Test that lazy cleanup triggers when over 100 conversations."""
        manager = ConversationManager(max_age_seconds=0.001)  # 1ms

        # Create 101 conversations
        for _ in range(101):
            manager.create_conversation()

        time.sleep(0.01)  # All become stale

        # Creating the 102nd conversation should trigger cleanup
        initial_count = len(manager.conversations)
        manager.create_conversation()

        # Cleanup should have run, removing old conversations
        assert len(manager.conversations) < initial_count

    def test_conversation_isolation(self):
        """Test that conversations are isolated from each other."""
        manager = ConversationManager()

        from app.rag.generation import Citation

        conv_id1 = manager.create_conversation()
        conv_id2 = manager.create_conversation()

        manager.add_message(conv_id1, "user", "Message 1")
        cit1 = Citation(number=0, title="A", journal="J", source_id="12345")
        manager.get_or_store_citation(conv_id1, cit1)

        manager.add_message(conv_id2, "user", "Message 2")
        cit2 = Citation(number=0, title="B", journal="J", source_id="67890")
        manager.get_or_store_citation(conv_id2, cit2)

        # Check messages are isolated
        messages1 = manager.get_messages(conv_id1)
        messages2 = manager.get_messages(conv_id2)
        assert len(messages1) == 1
        assert len(messages2) == 1
        assert messages1[0]["content"] == "Message 1"
        assert messages2[0]["content"] == "Message 2"

        # Check citations are isolated
        mapping1 = manager.get_citation_mapping(conv_id1)
        mapping2 = manager.get_citation_mapping(conv_id2)
        assert mapping1 == {"12345": 1}
        assert mapping2 == {"67890": 1}


if __name__ == "__main__":
    unittest.main()
