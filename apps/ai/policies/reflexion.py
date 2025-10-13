# ai/policies/reflexion.py
from __future__ import annotations
import json, os, re, time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple

_STOPWORDS = {
    "the","a","an","of","to","and","in","for","on","at","by","with","is","are","was","were",
    "be","can","could","should","would","how","what","when","where","why","which","who","whom",
    "do","does","did","from","about","as","into","over","under","vs","vs.","between","me","my",
    "mine","your","you","we","our","us"
}

def _norm(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"[_\-:;,.!?()\[\]{}<>\"'`~@#$%^&*+=/\\|]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def _keywords(text: str, k: int = 5) -> List[str]:
    words = [w for w in _norm(text).split() if w not in _STOPWORDS and len(w) > 2]
    # simple frequency sort
    freq: Dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    return [w for (w, _) in sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:k]]

def default_key_from_goal(goal: str) -> str:
    """
    Buckets similar queries under a stable key like:
      'db count candidates' or 'email outreach draft' or 'rank jd data science'
    """
    kws = _keywords(goal, k=4)
    return " ".join(kws) or "general"

@dataclass
class Lesson:
    key: str
    goal_preview: str
    text: str
    ts: float
    tags: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class ReflexionStore:
    """
    Very small JSONL-based store:
      - file on disk (default: data/reflexion_store.jsonl)
      - append-only writes
      - in-memory read cache on demand
    """
    def __init__(self, path: str = "data/reflexion_store.jsonl", max_per_key: int = 5) -> None:
        self.path = path
        self.max_per_key = max_per_key
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def add_lesson(self, key: str, goal: str, text: str, tags: Optional[List[str]] = None) -> None:
        rec = Lesson(
            key=key,
            goal_preview=(goal or "")[:140],
            text=text.strip(),
            ts=time.time(),
            tags=list(tags or []),
        )
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
        # optional: prune excess for this key (cheap in-place rebuild)
        self._prune_key(key)

    def _prune_key(self, key: str) -> None:
        try:
            items = self._read_all()
            items_for_key = [r for r in items if r.get("key") == key]
            if len(items_for_key) <= self.max_per_key:
                return
            # keep most recent max_per_key
            items_for_key.sort(key=lambda r: r.get("ts", 0.0), reverse=True)
            keep_ids = set(id(items_for_key[i]) for i in range(self.max_per_key))
            new_items = []
            count_seen = 0
            for r in items:
                if r.get("key") == key:
                    if count_seen < self.max_per_key:
                        new_items.append(items_for_key[count_seen])
                    count_seen += 1
                else:
                    new_items.append(r)
            # rewrite file
            with open(self.path, "w", encoding="utf-8") as f:
                for r in new_items:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        except Exception:
            # pruning is best-effort; ignore errors
            pass

    def _read_all(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        out: List[Dict[str, Any]] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
        return out

    def get_lessons(self, key: str, limit: int = 3) -> List[str]:
        items = [r for r in self._read_all() if r.get("key") == key]
        items.sort(key=lambda r: r.get("ts", 0.0), reverse=True)
        return [r.get("text", "") for r in items[: max(1, int(limit))]]

# ---- Lesson generation helpers ------------------------------------------------

def should_write_lesson(result: Dict[str, Any], max_steps: Optional[int] = None) -> Tuple[bool, List[str]]:
    """
    Decide if we should write a lesson based on the run outcome.
    Returns (flag, tags)
    """
    tags: List[str] = []
    ok = bool(result.get("ok", True))
    steps_used = int(result.get("steps_used", 0))
    error = result.get("error") or ""
    traj = result.get("trajectory") or []
    evidence = result.get("evidence") or []

    if not ok:
        tags.append("error")
    if error:
        tags.append("planner_error")
    if max_steps and steps_used >= max_steps:
        tags.append("step_cap")
    # Evidence policy breach (if the agent had to be corrected)
    if isinstance(traj, list):
        if any(isinstance(s, dict) and s.get("observation", {}).get("error") == "evidence_required" for s in traj):
            tags.append("evidence_required")

    write = (not ok) or error or (max_steps and steps_used >= max_steps) or ("evidence_required" in tags)
    return bool(write), tags

def make_lesson(goal: str, result: Dict[str, Any]) -> str:
    """
    Convert the last trajectory + error into a short, practical hint.
    Keep it <= 1-2 lines; no chain-of-thought.
    """
    error = (result.get("error") or "").strip()
    traj = result.get("trajectory") or []
    # detect common issues
    if error:
        return f"If planning fails, retry with a simpler first tool and add a cite step before Finish. (Last error: {error[:90]})"
    if any(isinstance(s, dict) and s.get("observation", {}).get("error") == "evidence_required" for s in traj):
        return "Before Finish on factual queries, always gather at least one grounded source (web.get) or DB citation."
    if result.get("steps_used", 0) >= 7:
        return "Avoid looping: vary the tool or keywords if two consecutive thoughts look similar."
    # generic
    return "Prefer information-gathering tools first, then synthesize, then Finish; avoid repeating the same plan."
