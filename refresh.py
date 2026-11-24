"""Build one self-contained, versioned snapshot for all iOS readers."""

import argparse
import hashlib
import os
import json
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from editorial import Editor, enrich, providers
from kaggle_web import ORIGIN, api, fetch, SourceUnavailable

CATALOG = Path(__file__).parent / "site/v1/catalog.json"
LOCALIZED = json.loads(Path(__file__).with_name("competition_zh.json").read_text())
CATEGORIES = {
    "音频": ("audio", "sound", "birdclef", "speech"),
    "视觉": ("computer vision", "image", "segmentation", "camera", "digit recognizer"),
    "NLP/LLM": ("language", "text", "nlp", "llm", "gemma", "reasoning"),
    "时间序列": ("time series", "forecast", "time-series"),
    "表格": ("tabular", "categorical", "regression", "playground series", "titanic"),
    "优化": ("optimization", "packing", "squares", "compilation", "santa"),
    "智能体": ("agent", "reinforcement", "simulation", "game playing"),
}


def stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify(c):
    text = " ".join(
        [c["title"], c.get("briefDescription", "")]
        + [x.get("displayName", "") for x in c.get("categories", [])]
    ).lower()
    return [
        label for label, terms in CATEGORIES.items() if any(s in text for s in terms)
    ] or ["其他"]


def competition(c):
    summary, categories = LOCALIZED.get(
        c["competitionName"], (c.get("briefDescription") or c["title"], classify(c))
    )
    return dict(
        id=c["competitionName"],
        title=c["title"],
        summary=summary,
        summaryEN=c.get("briefDescription") or c["title"],
        categories=categories,
        metric=c.get("evaluationAlgorithm", {}).get("name") or "见竞赛规则",
        start=c.get("dateEnabled") or c["dateCreated"],
        deadline=c["deadline"],
        url=ORIGIN + "/competitions/" + c["competitionName"],
    )


def list_competitions(option, order):
    body = dict(selector=dict(listOption=option, sortOption=order), pageSize=100)
    result = []
    while True:
        page = api("competitions.CompetitionService/ListCompetitions", **body)
        result.extend(page["competitions"])
        token = page.get("nextPageToken")
        if not token or option == "LIST_OPTION_COMPLETED":
            return result
        if token == body.get("pageToken"):
            raise ValueError("Repeated competition cursor")
        body["pageToken"] = token


def public_scores(board):
    teams = {t["teamId"] for t in board.get("teams", []) if not t.get("isBenchmark")}
    rows = {
        r["teamId"]: Decimal(r["displayScore"])
        for r in board.get("publicLeaderboard", [])
        if r.get("rank", 0) > 0 and r["teamId"] in teams
    }
    if (
        not rows
        or rows.keys() != teams
        or not all(v.is_finite() for v in rows.values())
    ):
        return []
    return list(rows.values())


def score_rank(score, scores, maximize):
    if not scores or not score.is_finite():
        return None
    rank = 1 + sum((other > score if maximize else other < score) for other in scores)
    return rank if rank * 10 <= len(scores) else None


def bound_version(kernel, versions, comp_id):
    # The notebook card reports its all-version best. This is attributable to
    # one run only if there is exactly one version, v1, tied to this competition.
    if len(versions) != 1 or not kernel.get("hasLinkedSubmission"):
        return None
    item = versions[0]
    run = item.get("run", {})
    sources = run.get("commit", {}).get("settings", {}).get("dataSources", [])
    competition_ids = {
        s.get("sourceId")
        for s in sources
        if s.get("sourceType", "DATA_SOURCE_TYPE_COMPETITION")
        == "DATA_SOURCE_TYPE_COMPETITION"
    }
    if (
        item.get("version", {}).get("versionNumber") == 1
        and run.get("id") == kernel["scriptVersionId"]
        and competition_ids == {comp_id}
        and run.get("status") == "COMPLETE"
    ):
        return item
    return None


def notebook_material(raw):
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict) and "cells" in parsed:
        return "\n".join(
            f"Cell {i}:\n" + "".join(cell.get("source", ""))
            for i, cell in enumerate(parsed["cells"], 1)
        )
    if raw.lstrip().startswith("<"):
        raise ValueError("Notebook source unavailable")
    return "Source file\n" + raw


def editorial_source(item):
    if item["evidence"]["kind"] == "public":
        run = item["id"].removeprefix("k-")
        if not run.isdigit():
            raise ValueError("Invalid notebook version")
        return notebook_material(
            fetch(f"{ORIGIN}/kernels/scriptcontent/{run}/download")
        )
    slug = item["sources"][0]["url"].rstrip("/").rsplit("/", 1)[-1]
    writeup = api(
        "discussions.WriteUpsService/GetWriteUpBySlug",
        competitionName=item["competitionID"],
        slug=slug,
    )
    if (
        item["id"] != f"w-{writeup['id']}"
        or ORIGIN + writeup["url"] != item["sources"][0]["url"]
    ):
        raise ValueError("Writeup identity mismatch")
    return writeup["message"]["rawMarkdown"]


def sync_one(c, active, previous, now):
    comp = competition(c)
    if not c.get("hasLeaderboard"):
        return comp, []
    board = api("competitions.LeaderboardService/GetLeaderboard", competitionId=c["id"])
    results = []

    def add(item, material):
        digest = hashlib.sha256(material.encode()).hexdigest()
        old = previous.get(item["id"])
        cached = old and old.get("fingerprint") == digest
        if cached:
            results.append(
                {
                    **old,
                    **item,
                    "sources": list(
                        {s["url"]: s for s in old["sources"] + item["sources"]}.values()
                    ),
                    "stale": False,
                }
            )
            return
        if item["evidence"]["kind"] == "public":
            results.append(
                dict(
                    item,
                    title=item["originalTitle"],
                    summary="本版本已通过公开榜成绩核验。",
                    takeaway="打开固定版本，对照输入、特征和提交代码。",
                    steps=[],
                    tags=["Notebook"],
                    awaitingExplanation=True,
                    fingerprint=digest,
                )
            )
        else:
            # Verified final writeups should appear in the feed even before AI enrichment.
            results.append(
                dict(
                    item,
                    title=item["originalTitle"],
                    summary="获奖队伍已公开赛后复盘，最终名次已与队伍记录核对。",
                    takeaway="先阅读作者的验证设计与模型选择，再对照最终成绩。",
                    tags=["Writeup"],
                    steps=[],
                    awaitingExplanation=True,
                    fingerprint=digest,
                )
            )

    if not active:
        teams = {t["teamId"]: t for t in board.get("teams", [])}
        final = [r for r in board.get("privateLeaderboard", []) if r.get("rank")]
        for row in sorted(final, key=lambda z: z["rank"])[:3]:
            team = teams[row["teamId"]]
            path = team.get("solutionWriteUpUrl") or ""
            if not path.startswith("/competitions/" + comp["id"] + "/writeups/"):
                continue
            w = api(
                "discussions.WriteUpsService/GetWriteUpBySlug",
                competitionName=comp["id"],
                slug=path.split("/")[-1],
            )
            if w.get("url") != path:
                continue
            material = w["message"]["rawMarkdown"]
            add(
                dict(
                    id="w-" + str(w["id"]),
                    originalTitle=w["title"],
                    competitionID=comp["id"],
                    author=team["teamName"],
                    published=w.get("publishTime") or w["message"]["postDate"],
                    evidence=dict(
                        kind="final",
                        rank=row["rank"],
                        teams=len(final),
                        score=row["displayScore"],
                        checked=now,
                    ),
                    sources=[
                        dict(title="方案原文", url=ORIGIN + path),
                        dict(title="最终排行榜", url=comp["url"] + "/leaderboard"),
                    ],
                ),
                material,
            )
        return comp, results
    scores = public_scores(board)
    if not scores:
        return comp, []
    metric = c.get("evaluationAlgorithm", {})
    if not metric:
        return comp, []
    maximize = bool(metric.get("isMax"))
    sort = "SCORE_DESCENDING" if maximize else "SCORE_ASCENDING"
    candidates = {}
    for order in (sort, "DATE_RUN"):
        response = api(
            "kernels.KernelsService/ListKernels",
            kernelFilterCriteria=dict(
                listRequest=dict(
                    competitionId=c["id"],
                    group="EVERYONE",
                    page=1,
                    pageSize=30,
                    sortBy=order,
                )
            ),
        )
        candidates.update({k["id"]: k for k in response.get("kernels", [])})

    def inspect_kernel(kernel):
        if "bestPublicScore" not in kernel or not kernel.get("hasLinkedSubmission"):
            return
        score = Decimal(str(kernel["bestPublicScore"]))
        rank = score_rank(score, scores, maximize)
        if rank is None:
            return
        versions = api(
            "kernels.KernelsService/ListKernelVersions", kernelId=kernel["id"]
        ).get("items", [])
        item = bound_version(kernel, versions, c["id"])
        if not item:
            return
        run_id = kernel["scriptVersionId"]
        entry = dict(
            kernelID=kernel["id"],
            id="k-" + str(run_id),
            competitionID=comp["id"],
            originalTitle=kernel["title"],
            author=kernel["author"]["displayName"],
            published=kernel["scriptVersionDateCreated"],
            evidence=dict(
                kind="public",
                rank=rank,
                teams=len(scores),
                score=str(score),
                checked=now,
            ),
            sources=[
                dict(title="已核验的 Notebook · v1", url=ORIGIN + item["viewerUrl"]),
                dict(title="公开排行榜", url=comp["url"] + "/leaderboard"),
            ],
        )
        cached = previous.get(entry["id"])
        if cached and cached.get("fingerprint"):
            results.append({**cached, **entry, "stale": False})
            return
        material = notebook_material(
            fetch(f"{ORIGIN}/kernels/scriptcontent/{run_id}/download")
        )
        add(entry, material)

    for kernel in candidates.values():
        try:
            inspect_kernel(kernel)
        except (SourceUnavailable, ValueError) as exc:
            # A removed notebook must not invalidate the other teams in a competition.
            print(
                "Unavailable candidate",
                kernel.get("id"),
                type(exc).__name__,
                flush=True,
            )
            old = previous.get("k-" + str(kernel.get("scriptVersionId")))
            if old:
                results.append(dict(old, stale=True))
    # Previously verified immutable runs can fall out of the two discovery windows.
    # Recheck availability, fingerprint and current rank before carrying them forward.
    seen = {v["id"] for v in results} | {
        "k-" + str(k.get("scriptVersionId")) for k in candidates.values()
    }
    for old in previous.values():
        if (
            old["competitionID"] != comp["id"]
            or old["evidence"]["kind"] != "public"
            or old["id"] in seen
        ):
            continue
        rank = score_rank(Decimal(old["evidence"]["score"]), scores, maximize)
        if rank is None:
            continue
        run_id = old["id"].removeprefix("k-")
        if not run_id.isdigit():
            continue
        try:
            material = notebook_material(
                fetch(f"{ORIGIN}/kernels/scriptcontent/{run_id}/download")
            )
            if hashlib.sha256(material.encode()).hexdigest() != old.get("fingerprint"):
                continue
            results.append(
                dict(
                    old,
                    stale=False,
                    evidence=dict(
                        old["evidence"], rank=rank, teams=len(scores), checked=now
                    ),
                )
            )
        except (SourceUnavailable, ValueError):
            results.append(dict(old, stale=True))
    return comp, results


def save_catalog(catalog):
    with tempfile.NamedTemporaryFile(mode="w", dir=CATALOG.parent, delete=False) as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    Path(f.name).replace(CATALOG)


def editorial_only():
    editor = Editor(providers(os.environ))
    if not editor.providers:
        raise SystemExit(
            "Configure OPENAI_API_KEY or DEEPSEEK_API_KEY in Actions Secrets first."
        )
    catalog = json.loads(CATALOG.read_text())
    comps = {c["id"]: c for c in catalog["competitions"]}
    now = stamp()
    cutoff = datetime.now(timezone.utc).timestamp() - 36 * 3600
    # Reuse final standings and only recent public standings; do not advance verification dates.
    eligible = {
        v["id"]: v
        for v in catalog["lessons"]
        if v["evidence"]["kind"] == "final"
        or (
            comps[v["competitionID"]]["deadline"] > now
            and datetime.fromisoformat(
                v["evidence"]["checked"].replace("Z", "+00:00")
            ).timestamp()
            >= cutoff
        )
    }
    enrich(eligible, comps, editorial_source, now, editor)
    if any(v.get("llmReview", {}).get("lastAttempt") == now for v in eligible.values()):
        catalog["updated"] = now
        save_catalog(catalog)


def main():
    old = json.loads(CATALOG.read_text())
    previous = {v["id"]: v for v in old["lessons"]}
    now = stamp()
    active = list_competitions("LIST_OPTION_ACTIVE", "SORT_OPTION_NEWEST")
    if not active:
        raise ValueError("Empty active directory")
    completed = list_competitions(
        "LIST_OPTION_COMPLETED", "SORT_OPTION_RECENTLY_CLOSED"
    )
    # Recent closings may publish writeups several weeks after the deadline.
    cutoff = datetime.now(timezone.utc).timestamp() - 60 * 86400
    recent = [
        c
        for c in completed
        if datetime.fromisoformat(c["deadline"].replace("Z", "+00:00")).timestamp()
        >= cutoff
    ]
    jobs = [(c, True) for c in active] + [(c, False) for c in recent]
    comps = {c["id"]: c for c in old["competitions"]}
    lessons = {k: v for k, v in previous.items() if v["evidence"]["kind"] == "final"}
    failures = []

    def run(pair):
        c, is_active = pair
        try:
            result = sync_one(c, is_active, previous, now)
            print(c["competitionName"], len(result[1]), flush=True)
            return result
        except Exception as exc:
            print(
                c["competitionName"],
                type(exc).__name__,
                str(exc)[:200],
                file=sys.stderr,
                flush=True,
            )
            failures.append(c["competitionName"])
            return competition(c), []

    with ThreadPoolExecutor(max_workers=3) as pool:
        for comp, items in pool.map(run, jobs):
            # Preserve edited bilingual briefs while updating dates, scores and categories.
            prior = comps.get(comp["id"], {})
            if prior.get("guide"):
                comp.update(
                    {key: prior[key] for key in ("summary", "summaryEN", "guide")}
                )
            comps[comp["id"]] = comp
            lessons.update({v["id"]: v for v in items})
    if len(failures) == len(jobs):
        raise RuntimeError("All competition reads failed")
    for v in previous.values():
        if v["competitionID"] in failures and v["evidence"]["kind"] == "public":
            lessons[v["id"]] = dict(v, stale=True)
    enrich(lessons, comps, editorial_source, now)
    catalog = dict(
        version=1,
        updated=now,
        competitions=sorted(comps.values(), key=lambda c: c["id"]),
        lessons=sorted(lessons.values(), key=lambda v: v["id"]),
        comparisons=old.get("comparisons", []),
    )
    save_catalog(catalog)
    print(
        f"{len(active)} active competitions, {len(lessons)} lessons, {len(failures)} incomplete reads"
    )
    if failures:
        print(
            "::warning::Some competitions could not be refreshed: "
            + ", ".join(failures)
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--editorial-only", action="store_true")
    if parser.parse_args().editorial_only:
        editorial_only()
    else:
        main()
