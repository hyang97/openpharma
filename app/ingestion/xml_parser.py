"""
XML parser for PubMed Central articles.
Extracts title, abstract, and full text from JATS XML format.
"""
from typing import Dict, Optional
from lxml import etree
import logging

logger = logging.getLogger(__name__)


class PMCXMLParser:
    """Parses PMC XML articles in JATS format."""

    def parse_article(self, xml_content: bytes) -> Optional[Dict]:
        """
        Parse PMC XML and extract article content.

        Args:
            xml_content: Raw XML bytes from Entrez.efetch

        Returns:
            Dict with keys: title, abstract, full_text, sections, section_offsets
            - sections: dict mapping section names to text (for chunking)
            - section_offsets: list of dicts with section name, char_start, char_end
              (character positions within full_text, for metadata storage)
        """
        try:
            # Parse XML
            root = etree.fromstring(xml_content)

            # Extract components
            title = self._extract_title(root)
            abstract = self._extract_abstract(root)
            sections = self._extract_body_sections(root)

            # Build full_text with ALL content (title + abstract + body sections)
            # and track character positions for each section
            full_text_parts = []
            section_offsets = []
            current_pos = 0

            # Add title
            if title:
                title_header = "TITLE\n"
                full_text_parts.append(title_header)
                content_start = current_pos + len(title_header)
                full_text_parts.append(title)
                content_end = content_start + len(title)

                section_offsets.append({
                    "section": "title",
                    "char_start": content_start,
                    "char_end": content_end
                })

                full_text_parts.append("\n\n")
                current_pos = content_end + 2

            # Add abstract
            if abstract:
                abstract_header = "ABSTRACT\n"
                full_text_parts.append(abstract_header)
                content_start = current_pos + len(abstract_header)
                full_text_parts.append(abstract)
                content_end = content_start + len(abstract)

                section_offsets.append({
                    "section": "abstract",
                    "char_start": content_start,
                    "char_end": content_end
                })

                full_text_parts.append("\n\n")
                current_pos = content_end + 2

            # Add body sections
            for section_name, text in sections.items():
                # Add section header (uppercase)
                header = f"{section_name.upper()}\n"
                full_text_parts.append(header)

                # Content starts after header
                content_start = current_pos + len(header)
                full_text_parts.append(text)
                content_end = content_start + len(text)

                # Record section boundaries (relative to full_text column)
                section_offsets.append({
                    "section": section_name,
                    "char_start": content_start,
                    "char_end": content_end
                })

                # Add spacing between sections
                full_text_parts.append("\n\n")
                current_pos = content_end + 2  # +2 for "\n\n"

            full_text = "".join(full_text_parts).rstrip()  # Remove trailing newlines

            return {
                "title": title,
                "abstract": abstract,
                "full_text": full_text,  # Now includes title + abstract + body sections
                "sections": sections,  # Keep body sections for chunking during ingestion
                "section_offsets": section_offsets  # Now includes title, abstract, and body sections
            }

        except Exception as e:
            logger.error(f"Error parsing XML: {e}")
            return None

    def _extract_title(self, root) -> str:
        """Extract article title from XML."""
        # Try multiple possible paths for title
        title_paths = [
            ".//article-title",
            ".//front//title-group//article-title",
        ]

        for path in title_paths:
            title_elem = root.find(path)
            if title_elem is not None:
                # Get text including any nested elements
                return self._get_text_content(title_elem)

        return ""

    def _extract_abstract(self, root) -> str:
        """Extract abstract text from XML."""
        abstract_elem = root.find(".//abstract")
        if abstract_elem is None:
            return ""

        # Get all paragraph text from abstract
        paragraphs = []
        for p in abstract_elem.findall(".//p"):
            text = self._get_text_content(p)
            if text:
                paragraphs.append(text)

        return "\n\n".join(paragraphs)

    def _extract_body_sections(self, root) -> Dict[str, str]:
        """
        Extract body sections with their titles.

        Returns:
            Dict mapping section names to content
            e.g., {"introduction": "...", "methods": "..."}
        """
        sections = {}
        body = root.find(".//body")

        if body is None:
            return sections

        # Find all <sec> (section) elements
        for sec in body.findall(".//sec"):
            # Get section title
            title_elem = sec.find("./title")
            section_name = (
                self._get_text_content(title_elem).lower()
                if title_elem is not None
                else "body"
            )

            # Get all paragraph text in this section
            paragraphs = []
            for p in sec.findall(".//p"):
                text = self._get_text_content(p)
                if text:
                    paragraphs.append(text)

            if paragraphs:
                # If section name already exists, append with number
                base_name = section_name
                counter = 1
                while section_name in sections:
                    section_name = f"{base_name}_{counter}"
                    counter += 1

                sections[section_name] = "\n\n".join(paragraphs)

        return sections

    def _get_text_content(self, element) -> str:
        """
        Extract all text from an element, including nested elements.
        This handles cases where text is split by inline tags like <italic>.
        """
        if element is None:
            return ""

        # Use itertext() to get all text, including from child elements
        text = "".join(element.itertext())

        # Clean up whitespace
        return " ".join(text.split())
