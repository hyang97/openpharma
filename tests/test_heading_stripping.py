"""
Tests for heading stripping regex patterns in prepare_messages_for_display.

Tests various edge cases for stripping "## Answer" and "## References" headings.
"""
import re


def strip_headings(content: str) -> str:
    """
    Test version of heading stripping logic from app/main.py.

    Strips "## Answer" heading and "## References" section from LLM responses.
    """
    # Strip "## Answer" heading if present (case-insensitive)
    content = re.sub(r'^##\s*Answer\s*:?\s*\n?', '', content.strip(), flags=re.IGNORECASE | re.MULTILINE)

    # Strip leading colons and whitespace (artifact from heading removal)
    content = content.lstrip(': \t\n')

    # Strip "## References" section and everything after it
    content = re.sub(
        r'(?:^|\n)\s*(?:##\s*References|References\s*:|[\*]{2}References[\*]{2})\s*:?\s*.*$',
        '',
        content,
        flags=re.IGNORECASE | re.DOTALL | re.MULTILINE
    )

    # Strip trailing whitespace
    content = content.rstrip()

    return content


def test_standard_format():
    """Test standard LLM response format."""
    text = """## Answer
GLP-1 agonists improve glycemic control [PMC12345678].
## References
[PMC12345678] Title: Study on GLP-1"""

    result = strip_headings(text)
    assert result == "GLP-1 agonists improve glycemic control [PMC12345678]."
    assert "## Answer" not in result
    assert "## References" not in result


def test_answer_with_colon():
    """Test "## Answer:" format with colon."""
    text = """## Answer:
GLP-1 agonists improve glycemic control [PMC12345678].
## References:
[PMC12345678] Title: Study on GLP-1"""

    result = strip_headings(text)
    assert result == "GLP-1 agonists improve glycemic control [PMC12345678]."


def test_answer_no_space_after_hash():
    """Test "##Answer" format without space."""
    text = """##Answer
GLP-1 agonists improve glycemic control [PMC12345678].
##References
[PMC12345678] Title: Study on GLP-1"""

    result = strip_headings(text)
    assert result == "GLP-1 agonists improve glycemic control [PMC12345678]."


def test_references_with_bold_markdown():
    """Test "**References**" format (bold markdown)."""
    text = """## Answer
GLP-1 agonists improve glycemic control [PMC12345678].
**References**
[PMC12345678] Title: Study on GLP-1"""

    result = strip_headings(text)
    assert result == "GLP-1 agonists improve glycemic control [PMC12345678]."


def test_case_insensitive():
    """Test case-insensitive matching."""
    text = """## ANSWER
GLP-1 agonists improve glycemic control [PMC12345678].
## REFERENCES
[PMC12345678] Title: Study on GLP-1"""

    result = strip_headings(text)
    assert result == "GLP-1 agonists improve glycemic control [PMC12345678]."


def test_mixed_case():
    """Test mixed case variations."""
    text = """## aNsWeR:
GLP-1 agonists improve glycemic control [PMC12345678].
## ReFeReNcEs:
[PMC12345678] Title: Study on GLP-1"""

    result = strip_headings(text)
    assert result == "GLP-1 agonists improve glycemic control [PMC12345678]."


def test_extra_whitespace():
    """Test extra whitespace in headings."""
    text = """##   Answer  :
GLP-1 agonists improve glycemic control [PMC12345678].
##   References  :
[PMC12345678] Title: Study on GLP-1"""

    result = strip_headings(text)
    assert result == "GLP-1 agonists improve glycemic control [PMC12345678]."


def test_multiline_references():
    """Test that entire References section is removed."""
    text = """## Answer
GLP-1 agonists improve glycemic control [PMC12345678].
## References
[PMC12345678] Title: Study on GLP-1
[PMC87654321] Title: Another Study
[PMC11111111] Title: Third Study"""

    result = strip_headings(text)
    assert result == "GLP-1 agonists improve glycemic control [PMC12345678]."
    assert "[PMC12345678] Title:" not in result


def test_no_headings():
    """Test text without headings passes through."""
    text = "GLP-1 agonists improve glycemic control [PMC12345678]."

    result = strip_headings(text)
    assert result == text


def test_only_answer_heading():
    """Test text with only Answer heading, no References."""
    text = """## Answer
GLP-1 agonists improve glycemic control [PMC12345678]."""

    result = strip_headings(text)
    assert result == "GLP-1 agonists improve glycemic control [PMC12345678]."


def test_references_colon_format():
    """Test "References:" format without markdown heading."""
    text = """## Answer
GLP-1 agonists improve glycemic control [PMC12345678].
References:
[PMC12345678] Title: Study on GLP-1"""

    result = strip_headings(text)
    assert result == "GLP-1 agonists improve glycemic control [PMC12345678]."


def test_whitespace_before_references():
    """Test whitespace before References heading."""
    text = """## Answer
GLP-1 agonists improve glycemic control [PMC12345678].

## References
[PMC12345678] Title: Study on GLP-1"""

    result = strip_headings(text)
    assert result == "GLP-1 agonists improve glycemic control [PMC12345678]."


def test_multiple_paragraphs_in_answer():
    """Test answer with multiple paragraphs."""
    text = """## Answer
GLP-1 agonists improve glycemic control [PMC12345678].

They also reduce cardiovascular risk [PMC87654321].

This is a third paragraph with more details.
## References
[PMC12345678] Title: Study on GLP-1
[PMC87654321] Title: CV Study"""

    result = strip_headings(text)
    expected = """GLP-1 agonists improve glycemic control [PMC12345678].

They also reduce cardiovascular risk [PMC87654321].

This is a third paragraph with more details."""
    assert result == expected


def replace_pmc_citations(content: str, pmc_to_number: dict) -> str:
    """
    Test version of PMC citation replacement logic from app/main.py.

    Replaces [PMCxxxx] with [number] for both single and comma-separated citations.
    """
    for source_id, number in pmc_to_number.items():
        pattern = r'PMC' + source_id + r'(?=\s*[,\]])'
        content = re.sub(pattern, str(number), content)
    return content


def test_single_pmc_citation_replacement():
    """Test single PMC citation replacement."""
    text = "GLP-1 agonists improve glycemic control [PMC12345678]."
    pmc_to_number = {"12345678": 1}

    result = replace_pmc_citations(text, pmc_to_number)
    assert result == "GLP-1 agonists improve glycemic control [1]."


def test_comma_separated_pmc_citations():
    """Test comma-separated PMC citations in same bracket."""
    text = "Studies show benefits [PMC12345678, PMC87654321] in patients."
    pmc_to_number = {"12345678": 1, "87654321": 2}

    result = replace_pmc_citations(text, pmc_to_number)
    assert result == "Studies show benefits [1, 2] in patients."


def test_comma_separated_no_space():
    """Test comma-separated PMC citations without space after comma."""
    text = "Studies show benefits [PMC12345678,PMC87654321] in patients."
    pmc_to_number = {"12345678": 1, "87654321": 2}

    result = replace_pmc_citations(text, pmc_to_number)
    assert result == "Studies show benefits [1,2] in patients."


def test_three_comma_separated_citations():
    """Test three comma-separated PMC citations."""
    text = "Multiple studies [PMC11111111, PMC22222222, PMC33333333] support this."
    pmc_to_number = {"11111111": 1, "22222222": 2, "33333333": 3}

    result = replace_pmc_citations(text, pmc_to_number)
    assert result == "Multiple studies [1, 2, 3] support this."


def test_mixed_single_and_comma_separated():
    """Test mix of single and comma-separated citations."""
    text = "First study [PMC11111111] and later studies [PMC22222222, PMC33333333] confirm."
    pmc_to_number = {"11111111": 1, "22222222": 2, "33333333": 3}

    result = replace_pmc_citations(text, pmc_to_number)
    assert result == "First study [1] and later studies [2, 3] confirm."


def test_whitespace_around_pmc():
    """Test PMC citations with whitespace variations."""
    text = "Studies show [ PMC12345678 , PMC87654321 ] benefits."
    pmc_to_number = {"12345678": 1, "87654321": 2}

    result = replace_pmc_citations(text, pmc_to_number)
    assert result == "Studies show [ 1 , 2 ] benefits."


def test_duplicate_pmc_in_comma_list():
    """Test duplicate PMC ID in same bracket."""
    text = "Studies [PMC12345678, PMC12345678] show this."
    pmc_to_number = {"12345678": 1}

    result = replace_pmc_citations(text, pmc_to_number)
    assert result == "Studies [1, 1] show this."


if __name__ == "__main__":
    # Run all test functions
    import sys

    test_functions = [
        # Heading stripping tests
        test_standard_format,
        test_answer_with_colon,
        test_answer_no_space_after_hash,
        test_references_with_bold_markdown,
        test_case_insensitive,
        test_mixed_case,
        test_extra_whitespace,
        test_multiline_references,
        test_no_headings,
        test_only_answer_heading,
        test_references_colon_format,
        test_whitespace_before_references,
        test_multiple_paragraphs_in_answer,
        # Citation replacement tests
        test_single_pmc_citation_replacement,
        test_comma_separated_pmc_citations,
        test_comma_separated_no_space,
        test_three_comma_separated_citations,
        test_mixed_single_and_comma_separated,
        test_whitespace_around_pmc,
        test_duplicate_pmc_in_comma_list,
    ]

    passed = 0
    failed = 0

    for test_func in test_functions:
        try:
            test_func()
            print(f"✓ {test_func.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {test_func.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test_func.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
