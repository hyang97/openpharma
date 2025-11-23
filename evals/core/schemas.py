"""Data structures for evaluation results and configurations."""
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass
class EvaluationResult:
    """Single question evaluation result."""
    question_id: str
    pmid: str
    pmc_id: str
    question: str
    expected_answer: str
    long_answer: str

    # RAG outputs
    rag_answer: str
    raw_llm_response: str
    citations: List[Dict]
    retrieved_chunk_ids: List[int]

    # Automated metrics
    correct_article_retrieved: bool
    citation_validity_rate: float
    response_time_ms: float

    # Error tracking
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dict for JSON."""
        return asdict(self)


@dataclass
class EvaluationConfig:
    """Evaluation run configuration."""
    experiment_name: str
    run_id: str
    dataset_path: str = "data/golden_eval_set.csv"
    rag_endpoint: str = "http://localhost:8000/chat"
    limit: Optional[int] = None

    def get_output_dir(self) -> str:
        """Output directory path."""
        return f"logs/eval_results/{self.experiment_name}"

    def get_auto_results_path(self) -> str:
        """Path for automated results JSON."""
        return f"{self.get_output_dir()}/{self.run_id}_auto_results.json"

    def get_llm_judge_prompt_path(self) -> str:
        """Path for LLM-as-judge prompt markdown."""
        return f"{self.get_output_dir()}/{self.run_id}_llm_judge_prompt.md"

    def get_llm_judge_results_path(self) -> str:
        """Path for LLM-as-judge results JSON."""
        return f"{self.get_output_dir()}/{self.run_id}_llm_judge_results.json"

    def get_complete_results_path(self) -> str:
        """Path for complete merged results JSON."""
        return f"{self.get_output_dir()}/{self.run_id}_complete_results.json"

    def get_metrics_csv_path(self) -> str:
        """Path for metrics-only CSV."""
        return f"{self.get_output_dir()}/{self.run_id}_metrics.csv"
