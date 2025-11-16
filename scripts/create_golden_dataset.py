"""
Create golden evaluation dataset from PubMedQA for papers we have in the database.

Usage:
    python scripts/create_golden_dataset.py --pubmedqa data/ori_pqal.json --mapping data/pubmedqa_pmid_to_pmc_mapping.json --output data/golden_eval_set.csv
"""

import argparse
import json
import csv
from typing import Dict, List

def create_golden_dataset(pubmedqa_file: str, mapping_file: str, output_file: str):
    """
    Filter PubMedQA dataset to only questions for papers we have PMC IDs for.

    Args:
        pubmedqa_file: Path to ori_pqal.json
        mapping_file: Path to pubmedqa_pmid_to_pmc_mapping.json
        output_file: Path to save filtered golden dataset (CSV)
    """
    # Load PubMedQA dataset
    with open(pubmedqa_file, 'r') as f:
        pubmedqa = json.load(f)

    # Load PMID->PMC mapping
    with open(mapping_file, 'r') as f:
        pmid_to_pmc = json.load(f)

    print(f"Total PubMedQA questions: {len(pubmedqa)}")
    print(f"Papers with PMC IDs: {len(pmid_to_pmc)}")

    # Filter to only questions we have papers for
    golden_dataset = []

    for pmid, question_data in pubmedqa.items():
        if pmid in pmid_to_pmc:
            pmc_id = pmid_to_pmc[pmid]

            # Create evaluation record
            eval_record = {
                "question_id": f"pubmedqa_{pmid}",
                "pmid": pmid,
                "pmc_id": pmc_id,
                "question": question_data["QUESTION"],
                "expected_answer": question_data["final_decision"],  # yes/no/maybe
                "long_answer": question_data.get("LONG_ANSWER", ""),
                "year": question_data.get("YEAR", ""),
                "meshes": "|".join(question_data.get("MESHES", [])),  # pipe-separated for CSV
                "num_contexts": len(question_data.get("CONTEXTS", []))
            }

            golden_dataset.append(eval_record)

    # Save golden dataset as CSV
    fieldnames = [
        "question_id",
        "pmid",
        "pmc_id",
        "question",
        "expected_answer",
        "long_answer",
        "year",
        "meshes",
        "num_contexts"
    ]

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(golden_dataset)

    print(f"\nCreated golden dataset with {len(golden_dataset)} questions")
    print(f"Saved to: {output_file}")

    # Print sample
    print("\nSample questions:")
    for i, sample in enumerate(golden_dataset[:3]):
        print(f"\n{i+1}. {sample['question_id']}")
        print(f"   Question: {sample['question'][:80]}...")
        print(f"   Expected: {sample['expected_answer']}")
        print(f"   Year: {sample['year']}")


def main():
    parser = argparse.ArgumentParser(
        description="Create golden evaluation dataset from PubMedQA"
    )
    parser.add_argument(
        "--pubmedqa",
        required=True,
        help="Path to ori_pqal.json"
    )
    parser.add_argument(
        "--mapping",
        required=True,
        help="Path to pubmedqa_pmid_to_pmc_mapping.json"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for golden dataset CSV"
    )

    args = parser.parse_args()
    create_golden_dataset(args.pubmedqa, args.mapping, args.output)


if __name__ == "__main__":
    main()
