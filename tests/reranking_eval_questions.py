"""
Test questions for manual reranking evaluation.

This file contains diverse questions for testing reranking impact on answer quality.
Questions span different query types: specific facts, comparisons, mechanisms, etc.

Usage:
    python -m tests.reranking_eval_questions

Evaluation criteria for each answer:
    1. Relevance: Does it answer the question directly?
    2. Citation Quality: Are cited papers actually relevant to the question?
    3. Specificity: Is the answer detailed and specific vs. vague?
    4. Accuracy: Is the information factually correct?

For each question, run twice:
    - Without reranking (baseline)
    - With reranking (experimental)

Then compare side-by-side and score on 1-5 scale for each criterion.
"""

# Test questions organized by query type
TEST_QUESTIONS = {
    "specific_fact": [
        {
            "id": 1,
            "question": "What is the mechanism of action of GLP-1 receptor agonists in diabetes treatment?",
            "category": "specific_fact",
            "why": "Tests if reranking finds papers specifically about GLP-1 mechanisms vs. general diabetes papers"
        },
        {
            "id": 2,
            "question": "What is the typical HbA1c reduction achieved with metformin monotherapy?",
            "category": "specific_fact",
            "why": "Tests if reranking surfaces papers with specific efficacy data vs. general metformin papers"
        },
    ],

    "comparison": [
        {
            "id": 3,
            "question": "How does the efficacy of SGLT2 inhibitors compare to DPP-4 inhibitors for type 2 diabetes?",
            "category": "comparison",
            "why": "Tests if reranking finds comparative studies vs. papers about each drug separately"
        },
        {
            "id": 4,
            "question": "What are the differences in cardiovascular outcomes between GLP-1 agonists and insulin therapy?",
            "category": "comparison",
            "why": "Tests if reranking prioritizes cardiovascular outcome trials vs. general treatment papers"
        },
    ],

    "adverse_events": [
        {
            "id": 5,
            "question": "What are the most common adverse events associated with SGLT2 inhibitors?",
            "category": "adverse_events",
            "why": "Tests if reranking finds safety-focused papers vs. efficacy-focused papers"
        },
        {
            "id": 6,
            "question": "What is the risk of hypoglycemia with sulfonylureas versus metformin?",
            "category": "adverse_events",
            "why": "Tests if reranking finds papers comparing safety profiles"
        },
    ],

    "mechanism": [
        {
            "id": 7,
            "question": "How does insulin resistance develop in type 2 diabetes at the cellular level?",
            "category": "mechanism",
            "why": "Tests if reranking prioritizes mechanistic/biological papers vs. clinical papers"
        },
        {
            "id": 8,
            "question": "What role do beta cells play in the progression of type 2 diabetes?",
            "category": "mechanism",
            "why": "Tests if reranking finds beta cell biology papers vs. general diabetes pathophysiology"
        },
    ],

    "treatment_guidelines": [
        {
            "id": 9,
            "question": "What are the current first-line treatment recommendations for newly diagnosed type 2 diabetes?",
            "category": "treatment_guidelines",
            "why": "Tests if reranking finds guidelines and consensus papers vs. individual drug trials"
        },
        {
            "id": 10,
            "question": "When should insulin therapy be initiated in type 2 diabetes patients?",
            "category": "treatment_guidelines",
            "why": "Tests if reranking finds clinical decision-making papers vs. insulin mechanism papers"
        },
    ],

    "population_specific": [
        {
            "id": 11,
            "question": "How should diabetes be managed differently in elderly patients compared to younger adults?",
            "category": "population_specific",
            "why": "Tests if reranking finds geriatric-specific papers vs. general diabetes management"
        },
        {
            "id": 12,
            "question": "What are the special considerations for diabetes management during pregnancy?",
            "category": "population_specific",
            "why": "Tests if reranking finds gestational diabetes and pregnancy-specific papers"
        },
    ],
}


def print_all_questions():
    """Print all test questions in a readable format."""
    print("=" * 80)
    print("RERANKING EVALUATION TEST QUESTIONS")
    print("=" * 80)
    print()

    all_questions = []
    for category, questions in TEST_QUESTIONS.items():
        all_questions.extend(questions)

    # Sort by ID
    all_questions.sort(key=lambda q: q["id"])

    for q in all_questions:
        print(f"Q{q['id']}: {q['question']}")
        print(f"    Category: {q['category']}")
        print(f"    Why: {q['why']}")
        print()

    print("=" * 80)
    print(f"TOTAL: {len(all_questions)} questions across {len(TEST_QUESTIONS)} categories")
    print("=" * 80)


def get_questions_for_quick_eval(num_questions=5):
    """
    Get a subset of questions for quick evaluation.

    Selects one question from each category for diverse coverage.

    Args:
        num_questions: Number of questions to return (default: 5)

    Returns:
        List of question dicts
    """
    # Get one question from each category
    selected = []
    for category, questions in TEST_QUESTIONS.items():
        if len(selected) < num_questions:
            selected.append(questions[0])

    return selected


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Print test questions for reranking evaluation")
    parser.add_argument("--quick", action="store_true", help="Show only 5 questions for quick evaluation")
    args = parser.parse_args()

    if args.quick:
        print("=" * 80)
        print("QUICK EVALUATION - 5 QUESTIONS")
        print("=" * 80)
        print()

        questions = get_questions_for_quick_eval(5)
        for q in questions:
            print(f"Q{q['id']}: {q['question']}")
            print(f"    Category: {q['category']}")
            print()

        print("=" * 80)
        print("Run each question with and without reranking, then compare answers.")
        print("=" * 80)
    else:
        print_all_questions()
