import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.dataset import EvalSample, load_eval_samples


def test_load_eval_samples_from_jsonl(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(
        """{"id":"a1","query":"q1","expected_chunk_ids":["c1"],"expected_refusal":true,"required_citations":true,"forbidden_chunk_ids":["x"],"allowed_doc_prefixes":["doc-a"]}\n{"id":"a2","question":"q2","reference_answer":"ans"}\n""",
        encoding="utf-8",
    )

    samples = load_eval_samples(str(dataset))

    assert len(samples) == 2
    assert samples[0].sample_id == "a1"
    assert samples[0].query == "q1"
    assert samples[0].expected_chunk_ids == ["c1"]
    assert samples[0].expected_refusal is True
    assert samples[0].required_citations is True
    assert samples[0].forbidden_chunk_ids == ["x"]
    assert samples[0].allowed_doc_prefixes == ["doc-a"]
    assert samples[1].query == "q2"
    assert samples[1].reference_answer == "ans"


def test_load_eval_samples_from_jsonl_with_bom(tmp_path):
    dataset = tmp_path / "dataset_bom.jsonl"
    dataset.write_text(
        "\ufeff{\"id\":\"a1\",\"query\":\"q1\"}\n",
        encoding="utf-8",
    )

    samples = load_eval_samples(str(dataset))

    assert len(samples) == 1
    assert samples[0].sample_id == "a1"
    assert samples[0].query == "q1"


def test_load_eval_samples_from_json(tmp_path):
    dataset = tmp_path / "dataset.json"
    dataset.write_text(
        json.dumps(
            {
                "samples": [
                    {"sample_id": "s1", "user_input": "what is rag", "ground_truth": "answer"}
                ]
            }
        ),
        encoding="utf-8",
    )

    samples = load_eval_samples(str(dataset))

    assert samples == [
        EvalSample(
            sample_id="s1",
            query="what is rag",
            reference_answer="answer",
            reference_contexts=[],
            expected_chunk_ids=[],
            expected_refusal=None,
            required_citations=None,
            forbidden_chunk_ids=[],
            allowed_doc_prefixes=[],
        )
    ]
