"""Measure retrieval quality: does the right chunk show up in the top k?

Write questions you know the answer to into eval/questions.jsonl, one per line:
  {"question": "What is the refund window?", "filename": "policy.pdf", "page": 4}

Then run from the backend folder:
  python -m eval.retrieval_eval --k 6

It reports hit rate (the expected page appears in the top k) and MRR (how high it
ranks). Re-run it after changing chunk size, overlap, embedding model or top_k to
see whether the change actually helped. Costs nothing: no LLM calls.
"""

import argparse
import json
from pathlib import Path

from app.retrieval import search


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default=str(Path(__file__).with_name("questions.jsonl")))
    parser.add_argument("--k", type=int, default=6)
    args = parser.parse_args()

    cases = [json.loads(line) for line in Path(args.file).read_text().splitlines() if line.strip()]
    hits, reciprocal_ranks = 0, []

    for case in cases:
        results = search(case["question"], top_k=args.k)
        rank = next(
            (
                i
                for i, r in enumerate(results, start=1)
                if r["filename"] == case["filename"] and r["page"] == case.get("page")
            ),
            None,
        )
        hits += rank is not None
        reciprocal_ranks.append(1 / rank if rank else 0)
        print(f"{'HIT ' if rank else 'MISS'}  rank={rank or '-':<3} {case['question']}")

    n = len(cases)
    print(f"\nhit@{args.k}: {hits}/{n} = {hits / n:.0%}   MRR: {sum(reciprocal_ranks) / n:.3f}")


if __name__ == "__main__":
    main()
