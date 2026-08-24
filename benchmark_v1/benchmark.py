# -*- coding: utf-8 -*-
r"""
Local LLM Multi-Agent Benchmark
- Scans C:\AI\Models recursively
- Deduplicates split GGUF shards
- Hard-links models into LM Studio via `lms import`
- Uses `lms load --estimate-only` before loading
- Runs Research/Coding/Data/Writer/PPT/Critic tasks
- Objective auto-scoring + fixed local LLM judge for subjective tasks
- Measures latency, output speed and NVIDIA peak VRAM
- Resumable SQLite storage
- Generates CSV + HTML rankings
"""
from __future__ import annotations

import argparse
import ast
import csv
import html
import json
import math
import os
import re
import shutil
import sqlite3
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import requests
except ImportError:
    print("requests가 없습니다. setup.ps1을 먼저 실행하세요.")
    raise

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
TASKS_PATH = HERE / "tasks.json"

LEVELS = {"quick": 1, "standard": 2, "full": 3}
ROLES = ["Research", "Coding", "Data", "Writer", "PPT", "Critic"]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


CFG = load_json(CONFIG_PATH)
ALL_TASKS = load_json(TASKS_PATH)


def run_cmd(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        timeout=timeout,
        shell=False,
    )


def lms_exe() -> str:
    x = shutil.which("lms")
    if x:
        return x
    # common fallback
    candidates = [
        Path.home() / ".lmstudio" / "bin" / "lms.exe",
        Path.home() / ".lmstudio" / "bin" / "lms.cmd",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    raise RuntimeError("lms 명령을 찾지 못했습니다. LM Studio를 한 번 실행하고 `lms --help`를 확인하세요.")


LMS = None
ACTIVE_INSTANCE_ID = None


def get_lms():
    global LMS
    if LMS is None:
        LMS = lms_exe()
    return LMS


def slugify(s: str) -> str:
    s = re.sub(r"-\d{5}-of-\d{5}(?=\.gguf$)", "", s, flags=re.I)
    s = re.sub(r"\.gguf$", "", s, flags=re.I)
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-._")
    return s[:120] or "model"


@dataclass
class ModelItem:
    slug: str
    display_name: str
    paths: list[Path]
    total_gib: float
    top_folder: str
    model_key: str | None = None
    est_vram_gib: float | None = None
    status: str = "NEW"

    @property
    def is_sharded(self):
        return len(self.paths) > 1


def scan_models() -> list[ModelItem]:
    root = Path(CFG["model_root"])
    if not root.exists():
        raise FileNotFoundError(f"모델 루트가 없습니다: {root}")

    files = list(root.rglob("*.gguf"))
    grouped: dict[str, list[Path]] = {}
    for p in files:
        base = re.sub(r"-\d{5}-of-\d{5}(?=\.gguf$)", "", p.name, flags=re.I)
        key = base.lower()
        grouped.setdefault(key, []).append(p)

    items = []
    for _, paths in grouped.items():
        paths = sorted(paths)
        total = sum(p.stat().st_size for p in paths) / (1024**3)
        first = paths[0]
        rel = first.relative_to(root)
        top = rel.parts[0] if rel.parts else ""
        display = re.sub(r"\.gguf$", "", re.sub(r"-\d{5}-of-\d{5}(?=\.gguf$)", "", first.name, flags=re.I), flags=re.I)
        items.append(ModelItem(
            slug=slugify(first.name),
            display_name=display,
            paths=paths,
            total_gib=round(total, 3),
            top_folder=top,
        ))
    items.sort(key=lambda x: (-x.total_gib, x.display_name.lower()))
    return items


def ensure_dirs(mode: str) -> tuple[Path, Path]:
    result_root = Path(CFG["results_dir"]) / mode
    result_root.mkdir(parents=True, exist_ok=True)
    db = result_root / "benchmark.db"
    return result_root, db


def connect_db(db_path: Path):
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""
    CREATE TABLE IF NOT EXISTS models(
        slug TEXT PRIMARY KEY,
        display_name TEXT,
        paths_json TEXT,
        file_gib REAL,
        top_folder TEXT,
        model_key TEXT,
        est_vram_gib REAL,
        status TEXT,
        note TEXT
    )""")
    con.execute("""
    CREATE TABLE IF NOT EXISTS responses(
        model_slug TEXT,
        task_id TEXT,
        role TEXT,
        response TEXT,
        latency_s REAL,
        output_tokens INTEGER,
        tok_s REAL,
        peak_vram_mib REAL,
        error TEXT,
        PRIMARY KEY(model_slug, task_id)
    )""")
    con.execute("""
    CREATE TABLE IF NOT EXISTS scores(
        model_slug TEXT,
        task_id TEXT,
        role TEXT,
        score REAL,
        method TEXT,
        reason TEXT,
        PRIMARY KEY(model_slug, task_id)
    )""")
    con.execute("""
    CREATE TABLE IF NOT EXISTS tool_scores(
        model_slug TEXT PRIMARY KEY,
        score REAL,
        detail TEXT
    )""")
    con.execute("""
    CREATE TABLE IF NOT EXISTS score_details(
        model_slug TEXT,
        task_id TEXT,
        hard_score REAL,
        judge_score REAL,
        final_cap REAL,
        hard_detail TEXT,
        judge_reason TEXT,
        PRIMARY KEY(model_slug, task_id)
    )""")
    con.commit()
    return con


def upsert_model(con, m: ModelItem, note=""):
    con.execute("""
    INSERT INTO models(slug,display_name,paths_json,file_gib,top_folder,model_key,est_vram_gib,status,note)
    VALUES(?,?,?,?,?,?,?,?,?)
    ON CONFLICT(slug) DO UPDATE SET
      display_name=excluded.display_name,
      paths_json=excluded.paths_json,
      file_gib=excluded.file_gib,
      top_folder=excluded.top_folder,
      model_key=COALESCE(excluded.model_key,models.model_key),
      est_vram_gib=COALESCE(excluded.est_vram_gib,models.est_vram_gib),
      status=excluded.status,
      note=excluded.note
    """, (
        m.slug, m.display_name, json.dumps([str(p) for p in m.paths], ensure_ascii=False),
        m.total_gib, m.top_folder, m.model_key, m.est_vram_gib, m.status, note
    ))
    con.commit()


def start_server():
    print("[LM Studio] 서버 확인...")
    base = CFG["lmstudio_base_url"].rstrip("/")
    try:
        r = requests.get(base + "/v1/models", timeout=3)
        if r.ok:
            print("[LM Studio] 이미 서버 실행 중")
            return
    except Exception:
        pass
    cp = run_cmd([get_lms(), "server", "start"], timeout=60)
    print(cp.stdout.strip())
    for _ in range(30):
        try:
            r = requests.get(base + "/v1/models", timeout=2)
            if r.ok:
                print("[LM Studio] 서버 준비 완료")
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("LM Studio API 서버가 시작되지 않았습니다.")


def auth_headers():
    h = {"Content-Type": "application/json"}
    token = CFG.get("lmstudio_api_token", "").strip()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def desired_model_key(m: ModelItem):
    return f"benchmark/{m.slug}"


def list_lms_models() -> list[dict]:
    """Return LM Studio installed-model entries from `lms ls --llm --json`."""
    try:
        cp = run_cmd([get_lms(), "ls", "--llm", "--json"], timeout=30)
        data = json.loads(cp.stdout.strip())
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("models", "items", "data"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []
    except Exception as e:
        print(f"  [LS ERROR] {e}", flush=True)
        return []


def _norm_model_text(value: str) -> str:
    value = str(value or "").replace("\\", "/").lower()
    value = re.sub(r"\.gguf$", "", value)
    return re.sub(r"[^a-z0-9]+", "", value)


def _entry_identity(item: dict) -> str:
    return json.dumps(item, ensure_ascii=False, sort_keys=True)


def find_lms_model_for_file(source: Path, entries: list[dict] | None = None) -> dict | None:
    entries = list_lms_models() if entries is None else entries
    if not entries:
        return None

    source_name = source.name.lower()
    source_norm = _norm_model_text(source.stem)

    exact, fuzzy = [], []
    for item in entries:
        path_s = str(item.get("path") or "").replace("\\", "/")
        key_s = str(item.get("modelKey") or item.get("model_key") or "")
        id_s = str(item.get("id") or "")
        joined = _norm_model_text(path_s + " " + key_s + " " + id_s)

        if Path(path_s).name.lower() == source_name:
            exact.append(item)
        elif source_norm and source_norm in joined:
            fuzzy.append(item)

    if exact:
        exact.sort(key=lambda x: str(x.get("path") or x.get("modelKey") or ""))
        return exact[0]
    if fuzzy:
        fuzzy.sort(key=lambda x: len(str(x.get("path") or "")))
        return fuzzy[0]
    return None


def estimate_vram(model_key: str, context_length: int) -> tuple[float | None, str]:
    cp = run_cmd([
        get_lms(), "load", "--estimate-only", model_key,
        "--context-length", str(context_length),
        "--gpu", CFG["gpu_mode"],
    ], timeout=min(int(CFG["load_timeout_sec"]), 90))
    txt = cp.stdout

    if cp.returncode != 0:
        return None, txt

    patterns = [
        r"Estimated\s+GPU\s+Memory\s*:\s*([0-9.,]+)\s*(GiB|GB|MiB|MB)",
        r"GPU\s+Memory\s*:\s*([0-9.,]+)\s*(GiB|GB|MiB|MB)",
    ]
    for pat in patterns:
        mm = re.search(pat, txt, flags=re.I)
        if not mm:
            continue
        val = float(mm.group(1).replace(",", ""))
        unit = mm.group(2).lower()
        if unit == "gb":
            val = val * (1000**3) / (1024**3)
        elif unit == "mb":
            val = val * (1000**2) / (1024**3)
        elif unit == "mib":
            val = val / 1024.0
        return round(val, 3), txt
    return None, txt


def ensure_imported(m: ModelItem, context_length: int) -> tuple[bool, str]:
    if m.is_sharded:
        return False, "sharded GGUF는 자동 import 대상에서 제외"

    source = m.paths[0]
    before = list_lms_models()
    found = find_lms_model_for_file(source, before)

    if not found:
        target_repo = desired_model_key(m)
        print(f"  [IMPORT] {source.name}", flush=True)
        try:
            cp = run_cmd([
                get_lms(), "import", str(source),
                "--hard-link",
                "--user-repo", target_repo,
                "-y",
            ], timeout=120)
        except subprocess.TimeoutExpired:
            return False, "LM Studio import timeout (120s)"

        if cp.returncode != 0:
            print("  [IMPORT CLI OUTPUT]", flush=True)
            print(cp.stdout[-4000:], flush=True)
            return False, "import CLI returned non-zero"

        after = list_lms_models()
        found = find_lms_model_for_file(source, after)

        if not found:
            before_ids = {_entry_identity(x) for x in before}
            new_entries = [x for x in after if _entry_identity(x) not in before_ids]

            if len(new_entries) == 1:
                found = new_entries[0]
                print("  [IMPORT RESOLVE] 새 LM Studio 항목 1개로 식별", flush=True)
            elif len(new_entries) > 1:
                src_norm = _norm_model_text(source.stem)

                def rank(item):
                    p = str(item.get("path") or "").replace("\\", "/").lower()
                    k = str(item.get("modelKey") or item.get("model_key") or "").lower()
                    joined = _norm_model_text(p + " " + k)
                    return (
                        0 if "benchmark/" in p or "benchmark/" in k else 1,
                        0 if src_norm and src_norm in joined else 1,
                        len(p),
                    )

                new_entries.sort(key=rank)
                found = new_entries[0]
                print(f"  [IMPORT RESOLVE] 새 항목 {len(new_entries)}개 중 최적 후보 사용", flush=True)

    if not found:
        return False, "import 후 LM Studio 항목을 식별하지 못함"

    model_key = str(
        found.get("modelKey")
        or found.get("model_key")
        or found.get("id")
        or ""
    ).strip()
    load_path = str(found.get("path") or "").strip()

    if not model_key:
        return False, f"LM Studio entry에 modelKey/id 없음: {found}"

    m.model_key = model_key
    m.est_vram_gib = None
    print(f"  [MODEL KEY] {model_key}", flush=True)
    if load_path:
        print(f"  [SOURCE]    {load_path}", flush=True)
    return True, f"modelKey={model_key}; source={load_path}"


def rest_headers():
    return auth_headers()


def list_native_models() -> list[dict]:
    base = CFG["lmstudio_base_url"].rstrip("/")
    r = requests.get(
        base + "/api/v1/models",
        headers=rest_headers(),
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("models", []) if isinstance(data, dict) else []


def unload_instance(instance_id: str) -> bool:
    base = CFG["lmstudio_base_url"].rstrip("/")
    r = requests.post(
        base + "/api/v1/models/unload",
        headers=rest_headers(),
        json={"instance_id": instance_id},
        timeout=60,
    )
    if r.status_code >= 400:
        print(f"  [REST UNLOAD ERROR] {instance_id}: HTTP {r.status_code} {r.text[:1000]}", flush=True)
        return False
    return True


def unload_all():
    global ACTIVE_INSTANCE_ID
    try:
        models = list_native_models()
        ids = []
        for model in models:
            for inst in (model.get("loaded_instances") or []):
                iid = str(inst.get("id") or "").strip()
                if iid:
                    ids.append(iid)

        if ids:
            print(f"  [REST UNLOAD] {len(ids)} loaded instance(s)", flush=True)

        for iid in ids:
            unload_instance(iid)

        ACTIVE_INSTANCE_ID = None
        time.sleep(0.4)
        return
    except Exception as e:
        print(f"  [REST UNLOAD FALLBACK] {e}", flush=True)

    # Last-resort compatibility fallback.
    try:
        run_cmd([get_lms(), "unload", "--all"], timeout=60)
    except Exception:
        pass
    ACTIVE_INSTANCE_ID = None
    time.sleep(0.7)


def load_model(m: ModelItem, identifier="bench-target", context_length=None) -> tuple[bool, str]:
    global ACTIVE_INSTANCE_ID

    context_length = context_length or CFG["context_length"]
    unload_all()

    base = CFG["lmstudio_base_url"].rstrip("/")
    payload = {
        "model": m.model_key,
        "context_length": int(context_length),
        "flash_attention": True,
        "offload_kv_cache_to_gpu": True,
        "echo_load_config": True,
    }

    print(
        f"  [REST LOAD] {m.model_key} | ctx={context_length} | flash_attention=on",
        flush=True,
    )

    try:
        r = requests.post(
            base + "/api/v1/models/load",
            headers=rest_headers(),
            json=payload,
            timeout=CFG["load_timeout_sec"],
        )
    except requests.Timeout:
        return False, f"REST load timeout ({CFG['load_timeout_sec']}s)"
    except Exception as e:
        return False, f"REST load request error: {e}"

    if r.status_code >= 400:
        return False, f"REST load HTTP {r.status_code}: {r.text[:5000]}"

    try:
        data = r.json()
    except Exception:
        return False, f"REST load returned non-JSON: {r.text[:5000]}"

    status = str(data.get("status") or "").lower()
    instance_id = (
        data.get("model_instance_id")
        or data.get("instance_id")
        or data.get("id")
    )

    if status != "loaded" or not instance_id:
        return False, f"REST load unexpected response: {json.dumps(data, ensure_ascii=False)[:5000]}"

    ACTIVE_INSTANCE_ID = str(instance_id)

    load_time = data.get("load_time_seconds")
    load_cfg = data.get("load_config") or {}
    print(f"  [LOAD OK] instance={ACTIVE_INSTANCE_ID} | {load_time}s", flush=True)
    if load_cfg:
        print(
            "  [LOAD CONFIG] "
            f"ctx={load_cfg.get('context_length')} "
            f"parallel={load_cfg.get('parallel')} "
            f"flash={load_cfg.get('flash_attention')} "
            f"kv_gpu={load_cfg.get('offload_kv_cache_to_gpu')}",
            flush=True,
        )

    return True, json.dumps(data, ensure_ascii=False)


def nvidia_memory_mib() -> float | None:
    try:
        cp = run_cmd([
            "nvidia-smi",
            f"--id={CFG['gpu_index']}",
            "--query-gpu=memory.used",
            "--format=csv,noheader,nounits",
        ], timeout=5)
        m = re.search(r"([0-9.]+)", cp.stdout)
        return float(m.group(1)) if m else None
    except Exception:
        return None


class GPUMonitor:
    def __init__(self):
        self.stop_evt = threading.Event()
        self.peak = 0.0
        self.thread = None

    def start(self):
        self.stop_evt.clear()
        self.peak = nvidia_memory_mib() or 0.0
        def worker():
            while not self.stop_evt.is_set():
                v = nvidia_memory_mib()
                if v is not None:
                    self.peak = max(self.peak, v)
                time.sleep(float(CFG["poll_gpu_interval_sec"]))
        self.thread = threading.Thread(target=worker, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_evt.set()
        if self.thread:
            self.thread.join(timeout=2)
        return self.peak


def chat(model_identifier: str, prompt: str, max_tokens=None, temperature=None, tools=None, tool_choice=None):
    global ACTIVE_INSTANCE_ID

    base = CFG["lmstudio_base_url"].rstrip("/")

    actual_model = model_identifier
    if model_identifier in ("bench-target", "bench-judge"):
        if not ACTIVE_INSTANCE_ID:
            raise RuntimeError("활성 LM Studio model instance가 없습니다.")
        actual_model = ACTIVE_INSTANCE_ID

    payload: dict[str, Any] = {
        "model": actual_model,
        "messages": [
            {"role": "system", "content": "지시를 정확히 따르고, 모르는 내용은 만들지 말고, 요구된 형식으로만 답하라."},
            {"role": "user", "content": prompt},
        ],
        "temperature": CFG["temperature"] if temperature is None else temperature,
        "max_tokens": CFG["max_tokens"] if max_tokens is None else max_tokens,
        "stream": False,
    }
    if tools is not None:
        payload["tools"] = tools
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice

    t0 = time.perf_counter()
    r = requests.post(
        base + "/v1/chat/completions",
        headers=auth_headers(),
        json=payload,
        timeout=CFG["request_timeout_sec"],
    )
    latency = time.perf_counter() - t0
    r.raise_for_status()
    data = r.json()
    choice = data.get("choices", [{}])[0]
    msg = choice.get("message", {})
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
    text = content if content.strip() else reasoning
    usage = data.get("usage", {}) or {}
    out_tokens = usage.get("completion_tokens")
    if not out_tokens:
        # rough fallback only
        out_tokens = max(1, int(len(text) / 3.2))
    tok_s = out_tokens / latency if latency > 0 else 0.0
    return {
        "text": text,
        "latency": latency,
        "output_tokens": int(out_tokens),
        "tok_s": tok_s,
        "message": msg,
        "content": content,
        "reasoning": reasoning,
        "raw": data,
    }


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def score_term_groups(text: str, groups: list[list[str]]) -> tuple[float, str]:
    n = normalize(text)
    hits = []
    for group in groups:
        ok = any(normalize(term) in n for term in group)
        hits.append(ok)
    score = 100.0 * sum(hits) / max(1, len(hits))
    return score, f"필수개념 {sum(hits)}/{len(hits)}"


def extract_numbers(text: str) -> list[float]:
    nums = []
    for s in re.findall(r"(?<![\w])[-+]?(?:\d+(?:\.\d+)?|\.\d+)", text.replace(",", "")):
        try:
            nums.append(float(s))
        except Exception:
            pass
    return nums


def score_numeric(text: str, expected: float, tolerance: float) -> tuple[float, str]:
    nums = extract_numbers(text)
    if any(abs(x - expected) <= tolerance for x in nums):
        return 100.0, f"정답 {expected} 발견"
    # percent form support: expected 0.2687 vs 26.87
    if expected < 1 and any(abs(x/100.0 - expected) <= tolerance for x in nums if x > 1):
        return 100.0, f"백분율 정답 {expected*100:.4g}% 발견"
    return 0.0, f"기대값 {expected}, 추출값 {nums[:10]}"


def score_numbers(text: str, expected: list[float], tolerance: float) -> tuple[float, str]:
    nums = extract_numbers(text)
    matched = 0
    used = set()
    for e in expected:
        found = False
        for i, x in enumerate(nums):
            if i in used:
                continue
            if abs(x-e) <= tolerance or (e < 1 and x > 1 and abs(x/100.0-e) <= tolerance):
                used.add(i); found = True; break
        matched += int(found)
    return 100.0 * matched / len(expected), f"수치정답 {matched}/{len(expected)}"



def _extract_python_code(text: str) -> str:
    blocks = re.findall(r"```(?:python|py)?\s*([\s\S]*?)```", text or "", flags=re.I)
    if blocks:
        return "\n".join(blocks)
    return text or ""


def _score_c04(text: str) -> tuple[float, str]:
    """
    Order-preserving deduplication.
    Accepts:
      - dict.fromkeys / OrderedDict.fromkeys
      - the classic seen=set() + append/add loop
    rather than requiring one exact implementation.
    """
    n = normalize(text)
    method = False
    method_name = ""

    if re.search(r"(?:ordereddict|dict)\s*\.\s*fromkeys\s*\(", n, flags=re.I):
        method = True
        method_name = "dict/OrderedDict.fromkeys"
    elif (
        re.search(r"\bset\s*\(", n, flags=re.I)
        and re.search(r"\bseen\b", n, flags=re.I)
        and (re.search(r"\.append\s*\(", n, flags=re.I) or re.search(r"\.add\s*\(", n, flags=re.I))
    ):
        method = True
        method_name = "seen set + append/add"

    complexity = bool(
        re.search(r"\bo\s*\(\s*n\s*\)", text or "", flags=re.I)
        or "선형" in n
        or "linear" in n
    )

    score = (75.0 if method else 0.0) + (25.0 if complexity else 0.0)
    detail = (
        f"유효 알고리즘={'PASS' if method else 'FAIL'}"
        + (f"({method_name})" if method else "")
        + f", 평균 O(n) 설명={'PASS' if complexity else 'FAIL'}"
    )
    return score, detail


def _ast_const_str(node, value: str) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.lower() == value.lower()


def _ast_const_number(node, value: float, tol: float = 1e-9) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and abs(float(node.value) - value) <= tol
    )


def _ast_contains_name_or_string(node, token: str) -> bool:
    token = token.lower()
    for x in ast.walk(node):
        if isinstance(x, ast.Name) and x.id.lower() == token:
            return True
        if isinstance(x, ast.Constant) and isinstance(x.value, str) and token in x.value.lower():
            return True
    return False


def _ast_has_method(node, method: str) -> bool:
    for x in ast.walk(node):
        if (
            isinstance(x, ast.Call)
            and isinstance(x.func, ast.Attribute)
            and x.func.attr.lower() == method.lower()
        ):
            return True
    return False


def _ast_group_mean_expr(node) -> bool:
    return (
        _ast_has_method(node, "groupby")
        and _ast_has_method(node, "mean")
        and _ast_contains_name_or_string(node, "line")
        and _ast_contains_name_or_string(node, "defect_rate")
    )


def _ast_refs_any_name(node, names: set[str]) -> bool:
    return any(isinstance(x, ast.Name) and x.id in names for x in ast.walk(node))


def _ast_has_threshold_003(node, names: set[str]) -> bool:
    for x in ast.walk(node):
        if not isinstance(x, ast.Compare) or len(x.ops) != 1 or len(x.comparators) != 1:
            continue
        left, right, op = x.left, x.comparators[0], x.ops[0]
        if isinstance(op, ast.Gt):
            if (_ast_refs_any_name(left, names) or _ast_group_mean_expr(left)) and _ast_const_number(right, 0.03):
                return True
        if isinstance(op, ast.Lt):
            if _ast_const_number(left, 0.03) and (_ast_refs_any_name(right, names) or _ast_group_mean_expr(right)):
                return True
    return False


def _ast_is_aggregate_filter(node, aggregate_names: set[str]) -> bool:
    """
    Correct shape is an aggregated Series filtered by its own values:
      avg[avg > 0.03]
    not:
      df[avg > 0.03]
    """
    if not isinstance(node, ast.Subscript):
        return False

    base_is_agg = _ast_refs_any_name(node.value, aggregate_names) or _ast_group_mean_expr(node.value)
    if not base_is_agg:
        return False

    return _ast_has_threshold_003(node.slice, aggregate_names)


def _ast_desc_sort(node, filtered_names: set[str], aggregate_names: set[str]) -> bool:
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "sort_values"
    ):
        return False

    # Sorting by line/name rather than aggregated defect-rate values is wrong.
    for arg in node.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            if arg.value.lower() in ("line", "index"):
                return False

    descending = False
    for kw in node.keywords:
        if kw.arg == "ascending" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
            descending = True
    if not descending:
        return False

    receiver = node.func.value
    return (
        _ast_refs_any_name(receiver, filtered_names)
        or _ast_is_aggregate_filter(receiver, aggregate_names)
    )


def _score_d04(text: str) -> tuple[float, str]:
    """
    Static AST validation of the requested pandas pipeline.
    It does not execute untrusted model code.

    Scores the semantic data-flow:
      groupby(line) -> defect_rate mean -> filter aggregated mean > .03
      -> sort aggregated values descending.
    """
    code = _extract_python_code(text)

    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Fall back to lexical evidence, but never allow a full score.
        n = normalize(code)
        hits = [
            "groupby" in n and "line" in n,
            "mean" in n and "defect_rate" in n,
            "0.03" in n,
            "sort_values" in n and "ascending=false" in n.replace(" ", ""),
        ]
        score = min(60.0, 15.0 * sum(hits))
        return score, f"AST 파싱 실패; 제한적 키워드 점수 {sum(hits)}/4"

    aggregate_names: set[str] = set()
    filtered_names: set[str] = set()

    group_mean = False
    filtered = False
    sorted_desc = False

    # First pass: identify aggregate assignments.
    for stmt in tree.body:
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            value = stmt.value
            if value is None:
                continue
            targets = []
            if isinstance(stmt, ast.Assign):
                targets = [x.id for t in stmt.targets for x in ast.walk(t) if isinstance(x, ast.Name)]
            elif isinstance(stmt.target, ast.Name):
                targets = [stmt.target.id]

            if _ast_group_mean_expr(value):
                group_mean = True
                aggregate_names.update(targets)

    # Any direct aggregate expression anywhere also counts.
    if not group_mean:
        group_mean = any(_ast_group_mean_expr(x) for x in ast.walk(tree))

    # Second pass: aggregate-value filtering.
    for stmt in tree.body:
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            value = stmt.value
            if value is None:
                continue
            targets = []
            if isinstance(stmt, ast.Assign):
                targets = [x.id for t in stmt.targets for x in ast.walk(t) if isinstance(x, ast.Name)]
            elif isinstance(stmt.target, ast.Name):
                targets = [stmt.target.id]

            if _ast_is_aggregate_filter(value, aggregate_names):
                filtered = True
                filtered_names.update(targets)

            # A chained expression such as:
            # avg[avg > 0.03].sort_values(ascending=False)
            # contains the aggregate filter below the outer Call node.
            nested_filter = any(
                isinstance(sub, ast.Subscript)
                and _ast_is_aggregate_filter(sub, aggregate_names)
                for sub in ast.walk(value)
            )
            if nested_filter:
                filtered = True
                filtered_names.update(targets)

            # A chained sort can contain the filtering expression directly.
            if _ast_desc_sort(value, filtered_names, aggregate_names):
                sorted_desc = True

    # Third pass after filtered variable names have been collected.
    for stmt in tree.body:
        value = getattr(stmt, "value", None)
        if value is not None and _ast_desc_sort(value, filtered_names, aggregate_names):
            sorted_desc = True

    # Basic grouping target check.
    group_line = False
    defect_mean = False
    for x in ast.walk(tree):
        if (
            isinstance(x, ast.Call)
            and isinstance(x.func, ast.Attribute)
            and x.func.attr == "groupby"
        ):
            if any(_ast_contains_name_or_string(a, "line") for a in x.args):
                group_line = True
        if (
            isinstance(x, ast.Call)
            and isinstance(x.func, ast.Attribute)
            and x.func.attr == "mean"
            and _ast_contains_name_or_string(x, "defect_rate")
        ):
            defect_mean = True

    # Some valid syntax selects defect_rate before .groupby(), so the mean call
    # may not contain the string directly; the aggregate expression check covers it.
    if group_mean:
        defect_mean = True

    score = 0.0
    parts = []
    for label, ok, pts in [
        ("line 기준 groupby", group_line, 20),
        ("defect_rate 평균", defect_mean, 20),
        ("집계 평균 > 0.03 필터", filtered, 30),
        ("집계값 내림차순 정렬", sorted_desc, 30),
    ]:
        if ok:
            score += pts
        parts.append(f"{label}={'PASS' if ok else 'FAIL'}")

    return score, ", ".join(parts)


def _score_r04(text: str, task: dict) -> tuple[float, str]:
    base, reason = score_term_groups(text, task["required_groups"])
    n = normalize(text)
    speculative = []
    for term in ("냉각팬", "전원부"):
        if term in n:
            speculative.append(term)
    penalty = min(40.0, 20.0 * len(speculative))
    return max(0.0, base - penalty), (
        reason + (f", 추측항목 포함 {speculative} → -{penalty:.0f}" if speculative else "")
    )


def objective_score(task: dict, text: str) -> tuple[float | None, str]:
    special = task.get("special_scorer")
    if special == "C04":
        return _score_c04(text)
    if special == "D04":
        return _score_d04(text)
    if special == "R04":
        return _score_r04(text, task)

    typ = task["score_type"]
    if typ in ("keywords", "critic"):
        return score_term_groups(text, task["required_groups"])
    if typ == "research":
        base, reason = score_term_groups(text, task["required_groups"])
        forbidden = task.get("forbidden_terms", [])
        bad = [x for x in forbidden if normalize(x) in normalize(text)]
        penalty = min(40, 20 * len(bad))
        return max(0.0, base - penalty), reason + (f", 금지주장 {len(bad)}개" if bad else "")
    if typ == "numeric":
        return score_numeric(text, float(task["expected_number"]), float(task["tolerance"]))
    if typ == "numbers":
        return score_numbers(text, [float(x) for x in task["expected_numbers"]], float(task["tolerance"]))
    if typ == "judge":
        return None, "judge required"
    raise ValueError(f"unknown score_type: {typ}")


def response_exists(con, model_slug, task_id):
    row = con.execute("SELECT 1 FROM responses WHERE model_slug=? AND task_id=?", (model_slug,task_id)).fetchone()
    return row is not None


def save_response(con, m, task, res=None, peak=None, error=""):
    if res is None:
        con.execute("""
        INSERT OR REPLACE INTO responses(model_slug,task_id,role,response,latency_s,output_tokens,tok_s,peak_vram_mib,error)
        VALUES(?,?,?,?,?,?,?,?,?)""",
        (m.slug,task["id"],task["role"],"",0,0,0,peak or 0,error))
    else:
        con.execute("""
        INSERT OR REPLACE INTO responses(model_slug,task_id,role,response,latency_s,output_tokens,tok_s,peak_vram_mib,error)
        VALUES(?,?,?,?,?,?,?,?,?)""",
        (m.slug,task["id"],task["role"],res["text"],res["latency"],res["output_tokens"],res["tok_s"],peak or 0,error))
    con.commit()


def save_score(con, mslug, task, score, method, reason):
    con.execute("""
    INSERT OR REPLACE INTO scores(model_slug,task_id,role,score,method,reason)
    VALUES(?,?,?,?,?,?)""",
    (mslug, task["id"], task["role"], float(score), method, reason))
    con.commit()


def run_tool_test(con, m: ModelItem):
    if con.execute("SELECT 1 FROM tool_scores WHERE model_slug=?", (m.slug,)).fetchone():
        return
    tools = [{
        "type":"function",
        "function":{
            "name":"add_numbers",
            "description":"두 정수를 더하는 함수",
            "parameters":{
                "type":"object",
                "properties":{"a":{"type":"integer"},"b":{"type":"integer"}},
                "required":["a","b"]
            }
        }
    }]
    try:
        res = chat("bench-target", "17과 25를 더해야 한다. 반드시 제공된 도구 add_numbers를 호출하라.", max_tokens=150, tools=tools, tool_choice="auto")
        msg = res["message"]
        calls = msg.get("tool_calls") or []
        score = 0.0
        detail = json.dumps(calls, ensure_ascii=False)
        for c in calls:
            fn = c.get("function", {})
            if fn.get("name") == "add_numbers":
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try: args = json.loads(args)
                    except: args = {}
                if {args.get("a"), args.get("b")} == {17,25}:
                    score = 100.0
                    break
                score = max(score, 60.0)
        con.execute("INSERT OR REPLACE INTO tool_scores(model_slug,score,detail) VALUES(?,?,?)",(m.slug,score,detail))
        con.commit()
    except Exception as e:
        con.execute("INSERT OR REPLACE INTO tool_scores(model_slug,score,detail) VALUES(?,?,?)",(m.slug,0.0,str(e)))
        con.commit()


def generate_for_model(con, m: ModelItem, tasks: list[dict]):
    pending = [t for t in tasks if not response_exists(con,m.slug,t["id"])]
    tool_done = con.execute("SELECT 1 FROM tool_scores WHERE model_slug=?", (m.slug,)).fetchone()
    if not pending and tool_done:
        print("  이미 완료됨 -> SKIP")
        return

    print(f"\n===== {m.display_name} | file {m.total_gib:.2f} GiB =====")
    mon = GPUMonitor()
    mon.start()
    ok, out = load_model(m, "bench-target", CFG["context_length"])
    load_peak = mon.stop()
    if not ok:
        m.status = "LOAD_FAILED"
        upsert_model(con,m,out[-5000:])
        print("  LOAD FAILED", flush=True)
        if out:
            print(out[-5000:], flush=True)
        return

    m.status = "RUNNING"
    upsert_model(con,m)
    print(f"  로드 완료 / load peak {load_peak/1024:.2f} GiB / instance={ACTIVE_INSTANCE_ID}", flush=True)

    run_tool_test(con,m)

    for idx, task in enumerate(pending,1):
        print(f"  [{idx}/{len(pending)}] {task['id']} {task['role']}")
        mon = GPUMonitor(); mon.start()
        try:
            res = chat("bench-target", task["prompt"])
            peak = mon.stop()
            save_response(con,m,task,res,peak,"")
            score, reason = objective_score(task,res["text"])
            if score is not None:
                save_score(con,m.slug,task,score,"objective",reason)
            print(f"      {res['latency']:.1f}s | {res['tok_s']:.1f} tok/s | peak {peak/1024:.2f} GiB" +
                  (f" | score {score:.1f}" if score is not None else " | judge later"))
        except Exception as e:
            peak = mon.stop()
            save_response(con,m,task,None,peak,str(e))
            if task["score_type"] != "judge":
                save_score(con,m.slug,task,0,"error",str(e))
            print("      ERROR:",e)

    unload_all()
    m.status = "GENERATED"
    upsert_model(con,m)


def select_judge(models: list[ModelItem]) -> ModelItem:
    """
    Pick a fixed local judge from the full disk inventory, not from the smoke-test DB subset.
    """
    needles = [
        CFG.get("judge_model_filename_contains","").lower(),
        "qwen3-30b-a3b-q5",
        "qwen3-32b-q4",
        "gemma-3-27b-it-q5",
        "phi-4-q6",
    ]
    for needle in needles:
        if not needle:
            continue
        matches = [
            m for m in models
            if needle in m.display_name.lower()
            and not m.is_sharded
            and m.total_gib <= float(CFG["hard_file_limit_gib"])
        ]
        if matches:
            matches.sort(key=lambda x:x.total_gib)
            return matches[0]
    raise RuntimeError("사용 가능한 Judge 후보를 디스크 인벤토리에서 찾지 못했습니다.")



def _visible_char_count(text: str) -> int:
    """Korean assignment-style character count: normalize whitespace, count spaces once."""
    s = re.sub(r"\s+", " ", (text or "")).strip()
    return len(s)


def _sentence_count(text: str) -> int:
    """
    Count prose sentences using terminal punctuation.

    Leading list markers such as "1.", "2)", "- " are formatting,
    not sentences.  This avoids counting a three-item numbered answer
    as six or seven sentences.
    """
    s = re.sub(r"```[\s\S]*?```", " ", text or "")

    cleaned_lines = []
    for line in s.splitlines():
        line = re.sub(r"^\s*[-*+]\s+", "", line)
        line = re.sub(r"^\s*\d+\s*[.)]\s*", "", line)
        if line.strip():
            cleaned_lines.append(line.strip())

    s = " ".join(cleaned_lines)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return 0

    parts = [p.strip() for p in re.split(r"[.!?。！？]+", s) if p.strip()]
    return len(parts)


def _body_without_title(text: str) -> str:
    lines = [x.strip() for x in (text or "").splitlines() if x.strip()]
    if not lines:
        return ""
    first = lines[0]
    if (
        re.match(r"^(제목|공지|안내|subject)\s*[:：]", first, flags=re.I)
        or (len(first) <= 60 and not re.search(r"[.!?。！？]$", first))
    ):
        lines = lines[1:]
    return "\n".join(lines)


def _clean_slide_heading(line: str) -> str:
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", line or "")
    cleaned = re.sub(r"^\*{1,2}", "", cleaned)
    cleaned = re.sub(r"\*{1,2}$", "", cleaned)
    return cleaned.strip()


def _slide_header_number(raw: str) -> tuple[str | None, int | None]:
    """
    Return (kind, number) for a slide heading.

    Recognizes:
      표지 / Cover
      Slide 1 / 슬라이드 1
      제1장 / 1장 / PPT 제1장
      1. 제목 / 1) 제목
    """
    line = _clean_slide_heading(raw)

    if re.match(r"^(?:표지|cover)\s*[:：-]?", line, flags=re.I):
        return "cover", 0

    m = re.match(r"^(?:슬라이드|slide)\s*(\d+)\s*[:：.)-]?", line, flags=re.I)
    if m:
        return "explicit", int(m.group(1))

    m = re.match(r"^(?:ppt\s*)?(?:제\s*)?(\d+)\s*장\s*[:：.)-]?", line, flags=re.I)
    if m:
        return "generic", int(m.group(1))

    # Numeric headings must be top-level, not indented nested bullets.
    if raw == raw.lstrip() or re.match(r"^\s*#{1,6}\s*", raw):
        m = re.match(r"^(\d+)\s*[.)]\s+\S+", line)
        if m:
            return "generic", int(m.group(1))

    return None, None


def _slide_count(text: str) -> tuple[int, str]:
    raw_lines = [x.rstrip() for x in (text or "").splitlines() if x.strip()]

    cover = 0
    explicit_nums = set()
    generic_nums = set()

    for raw in raw_lines:
        kind, num = _slide_header_number(raw)
        if kind == "cover":
            cover = 1
        elif kind == "explicit":
            explicit_nums.add(num)
        elif kind == "generic":
            generic_nums.add(num)

    if explicit_nums:
        numbered = explicit_nums
        kind = "explicit"
    else:
        numbered = generic_nums
        kind = "generic"

    total = cover + len(numbered)
    return total, f"표지 {cover} + {kind} 번호 슬라이드 {len(numbered)}"


def _slide_key_point_counts(text: str) -> list[tuple[int, int]]:
    """
    Return [(slide_no, substantive_point_count), ...].

    A substantive point is a bullet or explicit '핵심 1/2' line.
    Labels/metadata such as 제목, 발표자, 회사, 학교, 학부, 핵심 내용:
    are not counted as the two requested talking points.
    """
    segments: list[tuple[int, list[str]]] = []
    current_no = None
    current_lines: list[str] = []

    for raw in (text or "").splitlines():
        if not raw.strip():
            continue
        kind, num = _slide_header_number(raw)

        if kind in ("explicit", "generic"):
            if current_no is not None:
                segments.append((current_no, current_lines))
            current_no = int(num)
            current_lines = []
            continue

        if kind == "cover":
            if current_no is not None:
                segments.append((current_no, current_lines))
                current_no = None
                current_lines = []
            continue

        if current_no is not None:
            current_lines.append(raw)

    if current_no is not None:
        segments.append((current_no, current_lines))

    out = []
    metadata_re = re.compile(
        r"^(?:제목|발표자|회사|학교|학부|소속|핵심(?:\s*내용)?|핵심\s*메시지)\s*[:：]?\s*$",
        flags=re.I,
    )
    metadata_prefix_re = re.compile(
        r"^(?:제목|발표자|회사|학교|학부|소속)\s*[:：]",
        flags=re.I,
    )

    for slide_no, lines in segments:
        count = 0
        for raw in lines:
            stripped = raw.strip()
            # Markdown bullet
            m = re.match(r"^\s*[-*+]\s+(.*)$", raw)
            if m:
                content = re.sub(r"^\*{1,2}|\*{1,2}$", "", m.group(1).strip()).strip()
                if metadata_re.match(content) or metadata_prefix_re.match(content):
                    continue
                if content:
                    count += 1
                continue

            # "핵심 1: ..." / "핵심2 - ..."
            m = re.match(r"^\s*핵심\s*\d+\s*[:：.-]\s*(.+)$", stripped, flags=re.I)
            if m and m.group(1).strip():
                count += 1

        out.append((slide_no, count))

    return out


def _apology_count(text: str) -> int:
    patterns = [
        r"죄송(?:합니다|드립니다)?",
        r"사과(?:드립니다|합니다)?",
        r"양해\s*부탁",
    ]
    return sum(len(re.findall(p, text or "", flags=re.I)) for p in patterns)


def evaluate_hard_checks(task: dict, response: str) -> tuple[float, float | None, list[dict]]:
    """
    Deterministic instruction/fact checks for subjective tasks.
    Returns (hard_score, final_cap, check_results).
    """
    checks = task.get("hard_checks") or []
    if not checks:
        return 100.0, None, []

    score = 100.0
    cap = None
    results = []
    ntext = normalize(response)

    def add_result(ok: bool, label: str, measured: str, penalty: float, fail_cap=None):
        nonlocal score, cap
        if not ok:
            score -= float(penalty)
            if fail_cap is not None:
                cap = float(fail_cap) if cap is None else min(cap, float(fail_cap))
        results.append({
            "ok": bool(ok),
            "label": label,
            "measured": measured,
            "penalty": 0 if ok else float(penalty),
            "cap": None if ok else fail_cap,
        })

    for check in checks:
        typ = check.get("type")
        label = check.get("label", typ)
        penalty = float(check.get("penalty", 0))
        fail_cap = check.get("cap")

        if typ == "char_range":
            c = _visible_char_count(response)
            lo, hi = int(check["min"]), int(check["max"])
            add_result(lo <= c <= hi, label, f"{c}자 (요구 {lo}~{hi})", penalty, fail_cap)

        elif typ == "max_chars":
            c = _visible_char_count(response)
            hi = int(check["max"])
            add_result(c <= hi, label, f"{c}자 (최대 {hi})", penalty, fail_cap)

        elif typ == "sentence_exact":
            c = _sentence_count(response)
            exp = int(check["count"])
            add_result(c == exp, label, f"{c}문장 (요구 {exp})", penalty, fail_cap)

        elif typ == "body_sentence_exact":
            body = _body_without_title(response)
            c = _sentence_count(body)
            exp = int(check["count"])
            add_result(c == exp, label, f"본문 {c}문장 (요구 {exp})", penalty, fail_cap)

        elif typ == "slide_exact":
            c, desc = _slide_count(response)
            exp = int(check["count"])
            add_result(c == exp, label, f"{c}장 ({desc}, 요구 {exp})", penalty, fail_cap)

        elif typ == "slide_points_exact":
            expected_slides = int(check.get("slides", 0))
            expected_points = int(check["points"])
            p_each = float(check.get("penalty_each", penalty))
            counts = _slide_key_point_counts(response)

            # If slide parsing itself failed, record one clear failure here.
            if expected_slides and len(counts) != expected_slides:
                add_result(
                    False,
                    label,
                    f"인식 슬라이드 {len(counts)}개 (요구 {expected_slides}), 핵심 {expected_points}개/장",
                    p_each,
                    fail_cap,
                )
            else:
                for slide_no, cnt in counts:
                    add_result(
                        cnt == expected_points,
                        f"{label} Slide {slide_no}",
                        f"실질 핵심 {cnt}개 (요구 {expected_points})",
                        p_each,
                        fail_cap,
                    )

        elif typ == "title_present":
            lines = [x.strip() for x in (response or "").splitlines() if x.strip()]
            ok = bool(lines) and (
                bool(re.match(r"^(제목|공지|안내|subject)\s*[:：]", lines[0], flags=re.I))
                or (len(lines[0]) <= 60 and not re.search(r"[.!?。！？]$", lines[0]))
            )
            add_result(ok, label, lines[0] if lines else "없음", penalty, fail_cap)

        elif typ == "apology_exact":
            c = _apology_count(response)
            exp = int(check["count"])
            add_result(c == exp, label, f"{c}회 (요구 {exp})", penalty, fail_cap)

        elif typ == "required_groups":
            groups = check.get("groups", [])
            p_each = float(check.get("penalty_each", penalty))
            for idx, group in enumerate(groups, 1):
                ok = any(normalize(term) in ntext for term in group)
                add_result(
                    ok,
                    f"{label} #{idx}",
                    "충족" if ok else "누락: " + " | ".join(group),
                    p_each,
                    fail_cap,
                )

        elif typ == "required_regex":
            patterns = check.get("patterns", [])
            ok = any(re.search(p, response or "", flags=re.I | re.S) for p in patterns)
            add_result(
                ok,
                label,
                "충족" if ok else "요구 의미 패턴 미검출",
                penalty,
                fail_cap,
            )

        elif typ == "forbidden_regex":
            patterns = check.get("patterns", [])
            matched = [p for p in patterns if re.search(p, response or "", flags=re.I | re.S)]
            ok = not matched
            add_result(
                ok,
                label,
                "없음" if ok else f"금지 주장 검출 {len(matched)}개",
                penalty,
                fail_cap,
            )

    return max(0.0, score), cap, results


def hard_check_summary(results: list[dict]) -> str:
    if not results:
        return "자동 검증 항목 없음"
    lines = []
    for r in results:
        mark = "PASS" if r["ok"] else "FAIL"
        tail = ""
        if not r["ok"]:
            tail = f" / 감점 {r['penalty']}"
            if r.get("cap") is not None:
                tail += f" / 최종상한 {r['cap']}"
        lines.append(f"- {mark}: {r['label']} → {r['measured']}{tail}")
    return "\n".join(lines)


def save_score_detail(con, model_slug, task_id, hard_score, judge_score, final_cap, hard_detail, judge_reason):
    con.execute("""
    INSERT OR REPLACE INTO score_details(
        model_slug,task_id,hard_score,judge_score,final_cap,hard_detail,judge_reason
    ) VALUES(?,?,?,?,?,?,?)
    """, (
        model_slug,task_id,
        float(hard_score) if hard_score is not None else None,
        float(judge_score) if judge_score is not None else None,
        float(final_cap) if final_cap is not None else None,
        hard_detail,judge_reason
    ))
    con.commit()


def parse_judge_json(text: str):
    raw = (text or "").strip()
    if not raw:
        return None, "Judge 응답이 비어 있음"

    cleaned = re.sub(r"```(?:json)?", "", raw, flags=re.I).replace("```", "").strip()

    # Prefer JSON near the end of the answer.
    starts = [m.start() for m in re.finditer(r"\{", cleaned)]
    for pos in reversed(starts):
        candidate = cleaned[pos:].strip()
        try:
            d = json.loads(candidate)
            if isinstance(d, dict) and "score" in d:
                score = float(d["score"])
                return max(0.0, min(100.0, score)), str(d.get("reason", ""))
        except Exception:
            pass

    # tolerate: score: 82 / 점수: 82
    m = re.search(r'(?i)(?:"?score"?|점수)\s*[:=]\s*([0-9]{1,3}(?:\.\d+)?)', cleaned)
    if m:
        score = float(m.group(1))
        return max(0.0, min(100.0, score)), "JSON 형식이 아니어서 score 필드에서 복구"

    return None, "Judge 응답 파싱 실패"


def judge_subjective(con, judge: ModelItem, tasks_by_id: dict[str,dict]):
    rows = con.execute("""
      SELECT r.model_slug,r.task_id,r.response
      FROM responses r
      LEFT JOIN scores s ON s.model_slug=r.model_slug AND s.task_id=r.task_id
      WHERE s.task_id IS NULL AND r.error=''
    """).fetchall()
    rows = [r for r in rows if tasks_by_id.get(r[1],{}).get("score_type")=="judge"]
    if not rows:
        print("[JUDGE] 채점할 주관형 응답 없음")
        return

    print(f"\n[JUDGE] {judge.display_name} 로드")
    ok,out = load_model(judge,"bench-judge",CFG["judge_context_length"])
    if not ok:
        raise RuntimeError("Judge 모델 로드 실패:\n"+out)

    for i,(model_slug,task_id,response) in enumerate(rows,1):
        task = tasks_by_id[task_id]
        rubric = "\n".join(f"- {x}" for x in task["rubric"])

        hard_score, final_cap, hard_results = evaluate_hard_checks(task, response)
        hard_text = hard_check_summary(hard_results)
        hard_weight = float(
            task.get(
                "hard_weight",
                CFG.get("hybrid_default_hard_weight", 0.40) if hard_results else 0.0
            )
        )

        prompt = f"""/no_think
너는 엄격한 벤치마크 채점자다.
아래 응답을 문제와 평가기준으로 0~100점 채점하라.

중요:
- [자동 검증 결과]는 프로그램이 직접 계산한 사실이다.
- 글자 수, 문장 수, 슬라이드 수, 필수 문자열/의미 패턴 여부 등 자동 검증 결과를 절대로 뒤집지 마라.
- 자동검증이 PASS라고 표시한 동일 항목을 "누락/미준수"라고 다시 감점하면 채점 오류다.
- 자동검증이 FAIL이라고 표시한 동일 항목을 "충족"이라고 복구하지 마라.
- 평가할 응답에 실제로 적혀 있지 않은 설명이나 근거를 추론해서 채워 넣지 마라.
- 제목/목차/발표자 역할만 있고 실질 설명이 없으면 해당 내용을 설명한 것으로 인정하지 마라.
- 자동검증에서 PASS한 항목을 reason에서 다시 "누락", "불명확", "미준수"라고 비판하지 마라.
- 모델 이름이나 문체 취향으로 보너스를 주지 마라.
- 사실오류, 과장, 논리오류, 요구 불이행을 구체적으로 감점하라.
- 자동 검증은 최종 점수 계산에서 별도로 반영되므로, 너는 내용 품질/논리/표현의 주관적 품질을 중심으로 judge_score를 매겨라.

[문제]
{task['prompt']}

[평가기준]
{rubric}

[자동 검증 결과]
{hard_text}

[평가할 응답]
{response}

반드시 JSON 하나만 출력:
{{"score": 0부터100사이 숫자, "reason": "핵심 채점근거 1~2문장"}}"""

        try:
            res = chat(
                "bench-judge",
                prompt,
                max_tokens=CFG["judge_max_tokens"],
                temperature=0.0
            )
            judge_score,judge_reason = parse_judge_json(res["text"])

            if judge_score is None:
                print(f"  [{i}/{len(rows)}] {model_slug} {task_id}: JUDGE PARSE FAILED", flush=True)
                print(f"      {judge_reason}", flush=True)
                tail=(res.get("text") or "")[-1200:]
                if tail:
                    print("      Judge tail:", tail, flush=True)
                continue

            final_score = judge_score
            if hard_results:
                final_score = (hard_score * hard_weight) + (judge_score * (1.0-hard_weight))
            if final_cap is not None:
                final_score = min(final_score, final_cap)
            final_score = max(0.0, min(100.0, final_score))

            reason = (
                f"Hybrid: 자동검증 {hard_score:.1f}점 × {hard_weight:.0%} + "
                f"Judge {judge_score:.1f}점 × {(1-hard_weight):.0%}"
            )
            if final_cap is not None:
                reason += f", 실패한 핵심조건 상한 {final_cap:.1f}점"
            reason += f". Judge: {judge_reason}"

            save_score(con,model_slug,task,final_score,"hybrid",reason)
            save_score_detail(
                con,model_slug,task_id,
                hard_score,judge_score,final_cap,
                hard_text,judge_reason
            )
            print(
                f"  [{i}/{len(rows)}] {model_slug} {task_id}: "
                f"FINAL {final_score:.1f} | hard {hard_score:.1f} | judge {judge_score:.1f}"
                + (f" | cap {final_cap:.0f}" if final_cap is not None else ""),
                flush=True
            )
        except Exception as e:
            print(f"  [{i}/{len(rows)}] ERROR {model_slug} {task_id}: {e}")
    unload_all()



def prepare_models(con, models: list[ModelItem]) -> list[ModelItem]:
    """Import/resolve benchmark candidates and return READY models."""
    hard_limit = float(CFG["hard_file_limit_gib"])
    ready = []

    print(f"[PREPARE] 발견 {len(models)} model/quant", flush=True)

    for i, m in enumerate(models, 1):
        print(
            f"[{i}/{len(models)}] {m.display_name} ({m.total_gib:.2f} GiB)",
            flush=True,
        )

        if m.total_gib > hard_limit:
            m.status = "SKIP_FILE_TOO_LARGE"
            note = f"GGUF total > {hard_limit} GiB safety limit"
            upsert_model(con, m, note)
            print(
                f"  -> FILE SIZE {m.total_gib:.2f} GiB > "
                f"{hard_limit:.2f} GiB : SKIP",
                flush=True,
            )
            continue

        ok, note = ensure_imported(m, CFG["context_length"])
        if not ok:
            m.status = "IMPORT_FAILED"
            upsert_model(con, m, note)
            print(f"  -> IMPORT FAILED: {note}", flush=True)
            continue

        m.status = "READY"
        upsert_model(con, m, note)
        print("  -> READY (actual load test will follow)", flush=True)
        ready.append(m)

    return ready

def load_db_models(con) -> list[ModelItem]:
    rows=con.execute("SELECT slug,display_name,paths_json,file_gib,top_folder,model_key,est_vram_gib,status FROM models").fetchall()
    out=[]
    for r in rows:
        out.append(ModelItem(r[0],r[1],[Path(x) for x in json.loads(r[2])],r[3],r[4],r[5],r[6],r[7]))
    return out


def percentile_scores(values: dict[str,float], higher_better=True):
    if not values: return {}
    sorted_vals=sorted(values.values(), reverse=not higher_better)
    # simple min-max percentile-like score
    lo=min(values.values()); hi=max(values.values())
    if hi==lo: return {k:100.0 for k in values}
    if higher_better:
        return {k:100*(v-lo)/(hi-lo) for k,v in values.items()}
    return {k:100*(hi-v)/(hi-lo) for k,v in values.items()}


def build_summary(con):
    models = con.execute("SELECT slug,display_name,file_gib,top_folder,est_vram_gib,status FROM models").fetchall()
    rows=[]
    for slug,name,file_gib,folder,est,status in models:
        role_scores={}
        for role in ROLES:
            vals=[r[0] for r in con.execute("SELECT score FROM scores WHERE model_slug=? AND role=?",(slug,role)).fetchall()]
            role_scores[role]=statistics.mean(vals) if vals else None
        resp=con.execute("SELECT latency_s,tok_s,peak_vram_mib,error FROM responses WHERE model_slug=?",(slug,)).fetchall()
        toks=[x[1] for x in resp if x[1] and not x[3]]
        lats=[x[0] for x in resp if x[0] and not x[3]]
        peaks=[x[2] for x in resp if x[2]]
        tool=con.execute("SELECT score FROM tool_scores WHERE model_slug=?",(slug,)).fetchone()
        hard_vals=[
            r[0] for r in con.execute(
                "SELECT hard_score FROM score_details WHERE model_slug=? AND hard_score IS NOT NULL",
                (slug,)
            ).fetchall()
        ]
        instruction_score=statistics.mean(hard_vals) if hard_vals else None
        valid_roles=[v for v in role_scores.values() if v is not None]
        overall=sum(role_scores[r]*CFG["role_weights"].get(r,1.0) for r in ROLES if role_scores[r] is not None)
        denom=sum(CFG["role_weights"].get(r,1.0) for r in ROLES if role_scores[r] is not None)
        overall=overall/denom if denom else None
        peak_gib=max(peaks)/1024 if peaks else None
        rows.append({
            "slug":slug,"model":name,"source_folder":folder,"file_gib":file_gib,
            "estimated_vram_gib":est,"peak_vram_gib":peak_gib,
            **{r:role_scores[r] for r in ROLES},
            "tool_score":tool[0] if tool else None,
            "instruction_score":instruction_score,
            "overall_score":overall,
            "median_tok_s":statistics.median(toks) if toks else None,
            "median_latency_s":statistics.median(lats) if lats else None,
            "status":status,
        })
    return rows


def fmt(v,n=1):
    return "" if v is None else f"{v:.{n}f}"


def write_reports(con, result_root: Path):
    rows=build_summary(con)
    cols=["model","source_folder","file_gib","estimated_vram_gib","peak_vram_gib"]+ROLES+["instruction_score","tool_score","overall_score","median_tok_s","median_latency_s","status"]
    csv_path=result_root/"model_scores.csv"

    with csv_path.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=cols)
        w.writeheader()
        for r in sorted(rows,key=lambda x:(x["overall_score"] is None,-(x["overall_score"] or 0))):
            w.writerow({c:r.get(c) for c in cols})

    score_rows=[r for r in rows if r["overall_score"] is not None]
    score_rows.sort(key=lambda x:x["overall_score"],reverse=True)

    task_map={t["id"]:t for t in ALL_TASKS}

    def task_criteria_text(task: dict) -> str:
        typ=task.get("score_type","")
        if typ=="judge":
            return " / ".join(task.get("rubric",[]))
        if typ in ("keywords","critic","research"):
            groups=task.get("required_groups",[])
            required=["("+" | ".join(g)+")" for g in groups]
            txt="필수 요소: "+" ; ".join(required)
            forbidden=task.get("forbidden_terms",[])
            if forbidden:
                txt += " / 금지 주장: " + " ; ".join(forbidden)
            return txt
        if typ=="numeric":
            return f"기대값: {task.get('expected_number')} / 허용오차: {task.get('tolerance')}"
        if typ=="numbers":
            return f"기대값들: {task.get('expected_numbers')} / 허용오차: {task.get('tolerance')}"
        return typ

    def table(data, columns):
        out=["<table><thead><tr>"]
        labels={
            "model":"Model","file_gib":"File GiB","estimated_vram_gib":"Est VRAM",
            "peak_vram_gib":"Peak VRAM","overall_score":"Overall",
            "median_tok_s":"tok/s","tool_score":"Tool","instruction_score":"Instruction"
        }
        for c in columns:
            out.append(f"<th>{html.escape(labels.get(c,c))}</th>")
        out.append("</tr></thead><tbody>")
        for r in data:
            out.append("<tr>")
            for c in columns:
                v=r.get(c)
                if isinstance(v,float):
                    v=fmt(v,2 if c in ("file_gib","estimated_vram_gib","peak_vram_gib","median_tok_s") else 1)
                out.append(f"<td>{html.escape(str(v if v is not None else ''))}</td>")
            out.append("</tr>")
        out.append("</tbody></table>")
        return "".join(out)

    sections=[]
    maincols=["model","file_gib","estimated_vram_gib","peak_vram_gib"]+ROLES+["instruction_score","tool_score","overall_score","median_tok_s"]
    sections.append("<h2>전체 순위</h2>"+table(score_rows,maincols))

    for role in ROLES:
        rr=[r for r in score_rows if r.get(role) is not None]
        rr.sort(key=lambda x:x[role],reverse=True)
        sections.append(
            f"<h2>{html.escape(role)} TOP 15</h2>"+
            table(rr[:15],["model","peak_vram_gib",role,"overall_score","median_tok_s"])
        )

    for budget in [3,4,6,8,12,16,24]:
        rr=[]
        for r in score_rows:
            mem=r["peak_vram_gib"] or r["estimated_vram_gib"]
            if mem is not None and mem <= budget:
                rr.append(r)
        rr.sort(key=lambda x:x["overall_score"],reverse=True)
        sections.append(
            f"<h2>실측/추정 VRAM ≤ {budget} GiB TOP 15</h2>"+
            table(rr[:15],["model","peak_vram_gib","estimated_vram_gib","overall_score","median_tok_s"])
        )

    # ------------------------------------------------------------
    # Exact questions + raw model answers + scoring detail
    # ------------------------------------------------------------
    response_rows=con.execute("""
      SELECT
        m.display_name,
        r.model_slug,
        r.task_id,
        r.role,
        r.response,
        r.latency_s,
        r.output_tokens,
        r.tok_s,
        r.peak_vram_mib,
        r.error,
        s.score,
        s.method,
        s.reason,
        d.hard_score,
        d.judge_score,
        d.final_cap,
        d.hard_detail,
        d.judge_reason
      FROM responses r
      JOIN models m ON m.slug=r.model_slug
      LEFT JOIN scores s
        ON s.model_slug=r.model_slug AND s.task_id=r.task_id
      LEFT JOIN score_details d
        ON d.model_slug=r.model_slug AND d.task_id=r.task_id
      ORDER BY m.display_name,r.role,r.task_id
    """).fetchall()

    # CSV containing every exact question and answer.
    detailed_csv=result_root/"detailed_responses.csv"
    with detailed_csv.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f)
        w.writerow([
            "model","task_id","role","level","score_type",
            "question","scoring_criteria","model_answer",
            "score","score_method","score_reason",
            "hard_score","judge_score","final_cap","hard_detail","judge_reason",
            "latency_s","output_tokens","tok_s","peak_vram_gib","error"
        ])
        for row in response_rows:
            (
                model_name,model_slug,task_id,role,response,latency_s,
                output_tokens,tok_s,peak_vram_mib,error,score,method,reason,
                hard_score,judge_score,final_cap,hard_detail,judge_reason
            )=row
            task=task_map.get(task_id,{})
            w.writerow([
                model_name,task_id,role,task.get("level",""),task.get("score_type",""),
                task.get("prompt",""),task_criteria_text(task),response,
                score,method,reason,
                hard_score,judge_score,final_cap,hard_detail,judge_reason,
                latency_s,output_tokens,tok_s,
                (peak_vram_mib/1024 if peak_vram_mib else None),error
            ])

    # Human-readable HTML detail grouped by model.
    by_model={}
    for row in response_rows:
        by_model.setdefault(row[0],[]).append(row)

    detail_sections=[
        "<h2 id='answers'>테스트 문제 · 모델 답변 · 채점 근거</h2>",
        "<p class='muted'>각 항목을 펼치면 실제 테스트 문제, 모델의 원문 답변, 채점 기준과 점수를 확인할 수 있습니다.</p>"
    ]

    for model_name in sorted(by_model):
        model_rows=by_model[model_name]
        detail_sections.append(
            f"<details class='model-block'><summary><strong>{html.escape(model_name)}</strong> "
            f"— {len(model_rows)}개 응답</summary>"
        )

        for row in model_rows:
            (
                _model_name,model_slug,task_id,role,response,latency_s,
                output_tokens,tok_s,peak_vram_mib,error,score,method,reason,
                hard_score,judge_score,final_cap,hard_detail,judge_reason
            )=row
            task=task_map.get(task_id,{})
            score_txt="미채점" if score is None else f"{float(score):.1f}점"
            metrics=[]
            if latency_s:
                metrics.append(f"latency {latency_s:.2f}s")
            if tok_s:
                metrics.append(f"{tok_s:.2f} tok/s")
            if peak_vram_mib:
                metrics.append(f"peak VRAM {peak_vram_mib/1024:.2f} GiB")
            metric_txt=" · ".join(metrics)

            detail_sections.append(
                f"<details class='task-block'>"
                f"<summary><span class='role'>{html.escape(role)}</span> "
                f"{html.escape(task_id)} — <strong>{html.escape(score_txt)}</strong>"
                f"{(' · '+html.escape(metric_txt)) if metric_txt else ''}</summary>"
            )

            detail_sections.append("<h4>문제</h4>")
            detail_sections.append(
                f"<pre class='prompt'>{html.escape(task.get('prompt','(문제 정보를 찾지 못함)'))}</pre>"
            )

            detail_sections.append("<h4>채점 기준</h4>")
            detail_sections.append(
                f"<div class='criteria'>{html.escape(task_criteria_text(task))}</div>"
            )

            detail_sections.append("<h4>모델 답변</h4>")
            if error:
                detail_sections.append(
                    f"<pre class='error'>ERROR: {html.escape(error)}</pre>"
                )
            else:
                detail_sections.append(
                    f"<pre class='answer'>{html.escape(response or '(빈 응답)')}</pre>"
                )

            detail_sections.append("<h4>채점 결과</h4>")
            hybrid_extra=""
            if hard_score is not None or judge_score is not None:
                hybrid_extra += "<br><b>자동검증:</b> " + html.escape(
                    "" if hard_score is None else f"{float(hard_score):.1f}점"
                )
                hybrid_extra += " · <b>Judge:</b> " + html.escape(
                    "" if judge_score is None else f"{float(judge_score):.1f}점"
                )
                if final_cap is not None:
                    hybrid_extra += " · <b>상한:</b> " + html.escape(f"{float(final_cap):.1f}점")
                if hard_detail:
                    hybrid_extra += "<br><b>자동검증 상세:</b><pre class='harddetail'>" + html.escape(str(hard_detail)) + "</pre>"

            detail_sections.append(
                "<div class='scorebox'>"
                f"<b>{html.escape(score_txt)}</b>"
                f" · 방식: {html.escape(str(method or '미채점'))}"
                f"<br>근거: {html.escape(str(reason or ''))}"
                f"{hybrid_extra}"
                "</div>"
            )
            detail_sections.append("</details>")

        detail_sections.append("</details>")

    sections.extend(detail_sections)

    css="""body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#fafafa;color:#111;line-height:1.5}
    h1{margin-bottom:4px} h2{margin-top:34px}.muted{color:#666}
    table{border-collapse:collapse;width:100%;background:#fff;font-size:13px}
    th,td{border:1px solid #ddd;padding:7px 8px;text-align:right}
    th:first-child,td:first-child{text-align:left}th{background:#f0f2f5;position:sticky;top:0}
    tr:nth-child(even){background:#fafafa}
    details{background:#fff;border:1px solid #ddd;border-radius:8px;margin:10px 0}
    details>summary{cursor:pointer;padding:12px 14px}
    .model-block{margin:18px 0;border-color:#bbb}
    .model-block>summary{font-size:16px;background:#f3f4f6}
    .task-block{margin:10px 14px 14px 14px}
    .task-block>summary{background:#fafafa}
    .role{display:inline-block;min-width:72px;font-weight:600}
    h4{margin:16px 18px 6px 18px}
    pre{white-space:pre-wrap;word-break:break-word;margin:0 18px 12px 18px;padding:12px;border-radius:6px;
        font-family:Consolas,'Malgun Gothic',monospace;font-size:13px}
    .prompt{background:#f6f8fa}.answer{background:#f8fff8}.error{background:#fff3f3}
    .criteria,.scorebox{margin:0 18px 14px 18px;padding:10px 12px;border-left:4px solid #bbb;background:#fafafa}
    .scorebox{background:#fffdf3}.harddetail{margin:8px 0 0 0;background:#fff;padding:8px;border:1px solid #eee}
    """

    page=f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
    <title>Local LLM Benchmark</title><style>{css}</style></head><body>
    <h1>Local LLM Multi-Agent Benchmark</h1>
    <p class="muted">Research / Coding / Data / Writer / PPT / Critic + Tool Calling. 점수뿐 아니라 실제 문제와 모델 원문 답변을 함께 표시합니다.</p>
    {''.join(sections)}
    </body></html>"""

    (result_root/"report.html").write_text(page,encoding="utf-8")

    # Existing compact task-score export.
    details=con.execute("""
      SELECT m.display_name,s.task_id,s.role,s.score,s.method,s.reason
      FROM scores s JOIN models m ON m.slug=s.model_slug
      ORDER BY m.display_name,s.role,s.task_id
    """).fetchall()

    with (result_root/"task_scores.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f)
        w.writerow(["model","task_id","role","score","method","reason"])
        w.writerows(details)

    print(f"\n[REPORT] {csv_path}")
    print(f"[REPORT] {result_root/'task_scores.csv'}")
    print(f"[REPORT] {detailed_csv}")
    print(f"[REPORT] {result_root/'report.html'}")


def cmd_inventory(args):
    models=scan_models()
    result_root,db_path=ensure_dirs(args.mode)
    con=connect_db(db_path)
    for m in models: upsert_model(con,m)
    out=result_root/"inventory.csv"
    with out.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["model","gguf_files","total_gib","top_folder","paths"])
        for m in models: w.writerow([m.display_name,len(m.paths),m.total_gib,m.top_folder," | ".join(map(str,m.paths))])
    print(f"model/quant: {len(models)}")
    print(f"inventory: {out}")


def cmd_run(args):
    level=LEVELS[args.mode]
    tasks=[t for t in ALL_TASKS if t["level"]<=level]
    result_root,db_path=ensure_dirs(args.mode)
    con=connect_db(db_path)
    start_server()

    models=scan_models()

    # IMPORTANT: smoke-test limits must be applied BEFORE import/estimate preparation.
    # Otherwise --max-models 1 still prepares every model on disk.
    if args.buckets:
        wanted={x.strip() for x in args.buckets.split(",") if x.strip()}
        models=[m for m in models if m.top_folder in wanted]

    if getattr(args, "model_contains", ""):
        needle=args.model_contains.lower()
        models=[m for m in models if needle in m.display_name.lower()]
        print(f"[FILTER] model contains '{args.model_contains}' -> {len(models)}개", flush=True)

    if args.max_models:
        # For smoke tests, prefer small models so the plumbing is validated quickly.
        eligible=[m for m in models if m.total_gib <= float(CFG["hard_file_limit_gib"])]
        eligible.sort(key=lambda m:(m.total_gib,m.display_name.lower()))
        models=eligible[:args.max_models]
        print(f"[SMOKE] 사전검사 대상도 {len(models)}개로 제한", flush=True)

    ready=prepare_models(con,models)

    print(f"\n[RUN] READY {len(ready)} models / {len(tasks)} tasks per model")
    for i,m in enumerate(ready,1):
        print(f"\n######## MODEL {i}/{len(ready)} ########")
        generate_for_model(con,m,tasks)

    # Subjective judge phase.
    # Only start the judge if there are successful subjective responses to score.
    subjective_ids = [t["id"] for t in tasks if t["score_type"] == "judge"]
    placeholders = ",".join("?" for _ in subjective_ids)
    pending_subjective = 0
    if subjective_ids:
        q = f"""
        SELECT COUNT(*)
        FROM responses r
        LEFT JOIN scores s
          ON s.model_slug=r.model_slug AND s.task_id=r.task_id
        WHERE r.task_id IN ({placeholders})
          AND r.error=''
          AND s.task_id IS NULL
        """
        pending_subjective = con.execute(q, subjective_ids).fetchone()[0]

    if pending_subjective:
        print(f"\n[JUDGE] 주관형 미채점 응답 {pending_subjective}개", flush=True)
        try:
            judge = select_judge(scan_models())
            ok,note = ensure_imported(judge,CFG["judge_context_length"])
            if not ok:
                raise RuntimeError("Judge import 실패: "+note)
            print(f"[JUDGE] 선택: {judge.display_name}", flush=True)
            judge_subjective(con,judge,{t["id"]:t for t in tasks})
        except Exception as e:
            print(f"[JUDGE] SKIP: {e}", flush=True)
            print("[JUDGE] 객관식/정답형 결과는 그대로 보존됩니다.", flush=True)
    else:
        print("\n[JUDGE] 채점할 주관형 응답 없음 -> SKIP", flush=True)

    write_reports(con,result_root)



def cmd_rescore(args):
    """
    Recalculate all objective/non-Judge task scores from already-saved responses.
    No model inference is performed.
    This is useful after tasks.json scoring criteria are updated.
    """
    result_root,db_path=ensure_dirs(args.mode)
    con=connect_db(db_path)

    level=LEVELS[args.mode]
    tasks=[t for t in ALL_TASKS if t["level"]<=level]
    task_map={t["id"]:t for t in tasks}

    objective_ids=[
        t["id"] for t in tasks
        if t["score_type"]!="judge"
    ]

    if not objective_ids:
        print("[RESCORE] 재채점할 객관형 문제가 없습니다.")
        write_reports(con,result_root)
        return

    placeholders=",".join("?" for _ in objective_ids)
    rows=con.execute(
        f"""
        SELECT model_slug,task_id,response,error
        FROM responses
        WHERE task_id IN ({placeholders})
        ORDER BY model_slug,task_id
        """,
        objective_ids,
    ).fetchall()

    updated=0
    skipped=0
    errors=0

    print(
        f"[RESCORE] 저장된 객관형 응답 {len(rows)}개를 현재 tasks.json 기준으로 다시 채점합니다.",
        flush=True
    )

    for model_slug,task_id,response,error in rows:
        task=task_map.get(task_id)
        if not task:
            skipped += 1
            continue

        if error or not (response or "").strip():
            # Preserve inference errors as errors rather than inventing a score.
            if error:
                save_score(con,model_slug,task,0.0,"error",error)
                errors += 1
            else:
                skipped += 1
            continue

        try:
            score,reason=objective_score(task,response)
            if score is None:
                skipped += 1
                continue

            save_score(con,model_slug,task,score,"objective",reason)
            updated += 1
            print(
                f"  {model_slug} {task_id}: {score:.1f} | {reason}",
                flush=True
            )
        except Exception as e:
            errors += 1
            print(
                f"  ERROR {model_slug} {task_id}: {e}",
                flush=True
            )

    print(
        f"[RESCORE] 완료: updated={updated}, skipped={skipped}, errors={errors}",
        flush=True
    )
    write_reports(con,result_root)


def cmd_rejudge(args):
    result_root,db_path=ensure_dirs(args.mode)
    con=connect_db(db_path)
    start_server()

    level=LEVELS[args.mode]
    tasks=[t for t in ALL_TASKS if t["level"]<=level]
    task_map={t["id"]:t for t in tasks}
    subjective_ids=[t["id"] for t in tasks if t["score_type"]=="judge"]

    if not subjective_ids:
        print("[REJUDGE] 주관형 문제가 없습니다.")
        write_reports(con,result_root)
        return

    placeholders=",".join("?" for _ in subjective_ids)

    # Remove only previous judge scores, including bad zeroes from older versions.
    # Delete ALL prior scores for tasks that are subjective in the CURRENT tasks.json.
    # This also migrates tasks that changed from objective -> judge in a newer version.
    con.execute(
        f"DELETE FROM scores WHERE task_id IN ({placeholders})",
        subjective_ids,
    )
    con.execute(
        f"DELETE FROM score_details WHERE task_id IN ({placeholders})",
        subjective_ids,
    )
    con.commit()

    count=con.execute(
        f"""
        SELECT COUNT(*)
        FROM responses
        WHERE task_id IN ({placeholders})
          AND error=''
          AND TRIM(response)<>''
        """,
        subjective_ids,
    ).fetchone()[0]

    print(f"[REJUDGE] 저장된 주관형 응답 {count}개를 다시 채점합니다.", flush=True)

    if count == 0:
        write_reports(con,result_root)
        return

    judge=select_judge(scan_models())
    ok,note=ensure_imported(judge,CFG["judge_context_length"])
    if not ok:
        raise RuntimeError("Judge import 실패: "+note)

    print(f"[REJUDGE] Judge 선택: {judge.display_name}", flush=True)
    judge_subjective(con,judge,task_map)
    write_reports(con,result_root)

def cmd_report(args):
    result_root,db_path=ensure_dirs(args.mode)
    con=connect_db(db_path)
    write_reports(con,result_root)



def self_integrity_check():
    required = [
        "scan_models",
        "connect_db",
        "start_server",
        "ensure_imported",
        "prepare_models",
        "generate_for_model",
        "judge_subjective",
        "write_reports",
    ]
    missing = [name for name in required if not callable(globals().get(name))]
    if missing:
        raise RuntimeError(
            "benchmark.py 필수 함수 누락: " + ", ".join(missing)
        )

def main():
    self_integrity_check()
    ap=argparse.ArgumentParser(description="Local LLM multi-agent benchmark")
    sub=ap.add_subparsers(dest="cmd",required=True)

    p=sub.add_parser("inventory")
    p.add_argument("--mode",choices=LEVELS,default="standard")
    p.set_defaults(func=cmd_inventory)

    p=sub.add_parser("run")
    p.add_argument("--mode",choices=LEVELS,default="standard")
    p.add_argument("--max-models",type=int,default=0,help="테스트용 모델 수 제한, 0=전체")
    p.add_argument("--buckets",default="",help='예: "3GB,4GB" (현재 top folder 기준)')
    p.add_argument("--model-contains",default="",help="모델명 일부를 지정해 해당 모델만 평가")
    p.set_defaults(func=cmd_run)

    p=sub.add_parser("rescore")
    p.add_argument("--mode",choices=LEVELS,default="standard")
    p.set_defaults(func=cmd_rescore)

    p=sub.add_parser("rejudge")
    p.add_argument("--mode",choices=LEVELS,default="standard")
    p.set_defaults(func=cmd_rejudge)

    p=sub.add_parser("report")
    p.add_argument("--mode",choices=LEVELS,default="standard")
    p.set_defaults(func=cmd_report)

    args=ap.parse_args()
    args.func(args)


if __name__=="__main__":
    main()
