"""
Convert PMIDs to PMC IDs using NCBI ID Converter API.

Usage:
    python scripts/convert_pmids_to_pmc.py --input data/pubmedqa_pmids.txt --output data/pubmedqa_pmc_ids.txt
"""

import argparse
import requests
import time
import json
from typing import List, Dict

def convert_pmids_to_pmc(pmids: List[str], batch_size: int = 200) -> Dict[str, str]:
    """
    Convert PMIDs to PMC IDs using NCBI ID Converter API.

    Args:
        pmids: List of PMID strings
        batch_size: Number of PMIDs to convert per request (max 200)

    Returns:
        Dictionary mapping PMID -> PMC ID
    """
    pmid_to_pmc = {}

    # Split into batches
    for i in range(0, len(pmids), batch_size):
        batch = pmids[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(pmids) - 1) // batch_size + 1

        print(f"Converting batch {batch_num}/{total_batches} ({len(batch)} PMIDs)...", end=" ")

        # NCBI ID Converter API
        url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
        params = {
            'ids': ','.join(batch),
            'format': 'json'
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            records = data.get('records', [])

            converted = 0
            for record in records:
                pmid = record.get('pmid')
                pmcid = record.get('pmcid')

                if pmid and pmcid:
                    # Strip "PMC" prefix to get just the numeric ID
                    pmc_numeric = pmcid.replace('PMC', '')
                    pmid_to_pmc[pmid] = pmc_numeric
                    converted += 1

            print(f"Converted {converted}/{len(batch)}")

        except Exception as e:
            print(f"Error: {e}")

        # Rate limit: NCBI allows 3 requests/second
        time.sleep(0.4)

    return pmid_to_pmc


def main():
    parser = argparse.ArgumentParser(
        description="Convert PMIDs to PMC IDs using NCBI API"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input file with PMIDs (one per line)"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output file for PMC IDs (one per line)"
    )
    parser.add_argument(
        "--mapping-output",
        help="Optional: Save PMID->PMC mapping as JSON"
    )

    args = parser.parse_args()

    # Read PMIDs
    print(f"Reading PMIDs from {args.input}...")
    with open(args.input, 'r') as f:
        pmids = [line.strip() for line in f if line.strip()]

    print(f"Total PMIDs: {len(pmids)}\n")

    # Convert
    pmid_to_pmc = convert_pmids_to_pmc(pmids)

    # Report
    print(f"\nConversion complete:")
    print(f"  Successfully converted: {len(pmid_to_pmc)}")
    print(f"  No PMC ID found: {len(pmids) - len(pmid_to_pmc)}")

    # Save PMC IDs
    pmc_ids = list(pmid_to_pmc.values())
    with open(args.output, 'w') as f:
        for pmc_id in pmc_ids:
            f.write(f"{pmc_id}\n")

    print(f"\nSaved {len(pmc_ids)} PMC IDs to {args.output}")

    # Optionally save mapping
    if args.mapping_output:
        with open(args.mapping_output, 'w') as f:
            json.dump(pmid_to_pmc, f, indent=2)
        print(f"Saved PMID->PMC mapping to {args.mapping_output}")

    # Report PMIDs without PMC IDs
    missing = [pmid for pmid in pmids if pmid not in pmid_to_pmc]
    if missing:
        print(f"\nPMIDs without PMC IDs ({len(missing)}):")
        for pmid in missing[:10]:
            print(f"  {pmid}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")


if __name__ == "__main__":
    main()
