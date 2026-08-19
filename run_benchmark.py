#!/usr/bin/env python3
"""
로컬 LLM 벤치마크 러너
- Ollama (http://localhost:11434) 기준. vLLM/LM Studio 등 OpenAI 호환 서버를 쓰면
  OPENAI_COMPATIBLE=True 로 바꾸고 BASE_URL만 맞춰주면 됨.

사용법:
  python run_benchmark.py --models qwen3.6:27b qwen3-coder:30b --stage stage1
  python run_benchmark.py --models qwen3.6:27b --stage stage2 --role main
  python run_benchmark.py --models deepseek-r1:14b --stage stage2 --role reviewer

결과:
  results/<model>_<timestamp>.jsonl   -> 케이스별 원문 응답 + 지표
  results/summary_<timestamp>.csv     -> 모델별 요약 (속도, JSON 성공률 등 자동채점 가능한 것만)

수동 채점이 필요한 항목(자연스러움, 요약 품질 등)은 jsonl을 열어 rubric 보고 직접 점수 매길 것.
"""

import argparse
import csv
import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

import requests

BASE_URL = "http://localhost:11434"
TEST_CASES_FILE = "benchmark_test_cases.json"
RESULTS_DIR = Path("results")
REPEAT_DEFAULT = 3  # 원본 정의는 5회지만 시간 절약 위해 기본 3회, --repeat로 조절 가능


def get_vram_snapshot():
    """nvidia-smi로 현재 VRAM 사용량 스냅샷 (GPU별)"""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=index,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            text=True,
        )
        snaps = []
        for line in out.strip().splitlines():
            idx, used, total = [x.strip() for x in line.split(",")]
            snaps.append({"gpu": int(idx), "used_mb": int(used), "total_mb": int(total)})
        return snaps
    except Exception as e:
        return {"error": str(e)}


def call_ollama(model: str, prompt: str, timeout=180):
    """Ollama /api/generate 호출, 지연시간/토큰속도 함께 반환"""
    t0 = time.time()
    resp = requests.post(
        f"{BASE_URL}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=timeout,
    )
    t1 = time.time()
    resp.raise_for_status()
    data = resp.json()

    eval_count = data.get("eval_count")
    eval_duration_ns = data.get("eval_duration")
    tokens_per_sec = None
    if eval_count and eval_duration_ns:
        tokens_per_sec = eval_count / (eval_duration_ns / 1e9)

    load_duration_ns = data.get("load_duration", 0)
    prompt_eval_duration_ns = data.get("prompt_eval_duration", 0)
    ttft_sec = (load_duration_ns + prompt_eval_duration_ns) / 1e9

    return {
        "response": data.get("response", ""),
        "wall_clock_sec": round(t1 - t0, 3),
        "ttft_sec": round(ttft_sec, 3) if ttft_sec else None,
        "tokens_per_sec": round(tokens_per_sec, 2) if tokens_per_sec else None,
        "eval_count": eval_count,
    }


def is_valid_json_array(text: str) -> bool:
    """tool_calling 카테고리 자동 채점용: 응답에서 JSON 배열 추출 후 파싱 시도"""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return False
    try:
        json.loads(match.group(0))
        return True
    except json.JSONDecodeError:
        return False


def auto_score(case: dict, response_text: str):
    """자동 채점 가능한 항목만 처리 (JSON 유효성). 나머지는 수동 채점 필요 표시."""
    if case["category"] == "tool_calling":
        return {"auto_metric": "json_valid", "value": is_valid_json_array(response_text)}
    return {"auto_metric": None, "value": None, "note": "수동 채점 필요 (rubric 참고)"}


def load_cases(stage: str, role: str | None):
    with open(TEST_CASES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    cases = []
    for c in data["cases"]:
        if stage not in c.get("stage", []):
            continue
        if role and "role" in c and role not in c["role"]:
            continue
        cases.append(c)
    return cases


def run_for_model(model: str, cases: list, repeat: int):
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = model.replace(":", "_").replace("/", "_")
    out_path = RESULTS_DIR / f"{safe_name}_{timestamp}.jsonl"

    vram_before = get_vram_snapshot()
    all_records = []

    for case in cases:
        for attempt in range(repeat):
            try:
                result = call_ollama(model, case["prompt"])
            except Exception as e:
                result = {"error": str(e)}
            record = {
                "model": model,
                "case_id": case["id"],
                "category": case["category"],
                "attempt": attempt + 1,
                **result,
            }
            if "response" in result:
                record["auto_score"] = auto_score(case, result["response"])
            all_records.append(record)
            print(f"[{model}] {case['id']} attempt {attempt+1}/{repeat} "
                  f"-> {result.get('tokens_per_sec', 'ERR')} tok/s")

    vram_after = get_vram_snapshot()

    with open(out_path, "w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.write(json.dumps({"vram_before": vram_before, "vram_after": vram_after},
                            ensure_ascii=False) + "\n")

    return all_records, out_path


def summarize(all_results: dict, timestamp: str):
    summary_path = RESULTS_DIR / f"summary_{timestamp}.csv"
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["model", "avg_tokens_per_sec", "avg_ttft_sec",
                          "n_success", "n_error", "tool_json_valid_rate"])
        for model, records in all_results.items():
            speeds = [r["tokens_per_sec"] for r in records if r.get("tokens_per_sec")]
            ttfts = [r["ttft_sec"] for r in records if r.get("ttft_sec")]
            n_error = sum(1 for r in records if "error" in r)
            n_success = len(records) - n_error
            tool_records = [r for r in records if r.get("category") == "tool_calling"]
            tool_valid = [r for r in tool_records
                          if r.get("auto_score", {}).get("value") is True]
            tool_rate = (len(tool_valid) / len(tool_records) * 100) if tool_records else None

            writer.writerow([
                model,
                round(sum(speeds) / len(speeds), 2) if speeds else "N/A",
                round(sum(ttfts) / len(ttfts), 2) if ttfts else "N/A",
                n_success,
                n_error,
                f"{tool_rate:.0f}%" if tool_rate is not None else "N/A",
            ])
    print(f"\n요약 저장됨: {summary_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", required=True,
                         help="Ollama 모델 태그 목록 (예: qwen3.6:27b qwen3-coder:30b)")
    parser.add_argument("--stage", choices=["stage1", "stage2"], required=True)
    parser.add_argument("--role", default=None,
                         help="stage2에서만 사용: main/coder/reviewer/tester/researcher/planner")
    parser.add_argument("--repeat", type=int, default=REPEAT_DEFAULT)
    args = parser.parse_args()

    cases = load_cases(args.stage, args.role)
    if not cases:
        print("해당 stage/role 조합에 맞는 테스트 케이스가 없습니다.")
        return

    print(f"{len(cases)}개 케이스 x {args.repeat}회 반복 x {len(args.models)}개 모델")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    all_results = {}
    for model in args.models:
        records, _ = run_for_model(model, cases, args.repeat)
        all_results[model] = records

    summarize(all_results, timestamp)


if __name__ == "__main__":
    main()
