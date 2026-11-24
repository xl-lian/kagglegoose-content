import copy
import contextlib
import io
import hashlib
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from editorial import (
    Editor,
    providers,
    enrich,
    cited,
    request_json,
    SCREEN,
    bind_references,
    source_blocks,
    lesson_result,
    appears,
    copied_decimals,
)
from refresh import sync_one

RAW = "Cell 1:\ntrain = GroupKFold(5)\nCell 2:\nmodel.fit(train)"
COMP = {"id": "comp", "title": "Demo", "summary": "Predict a value", "metric": "MAE"}
ITEM = {
    "id": "k-123",
    "competitionID": "comp",
    "published": "2020-01-01",
    "title": "Original",
    "originalTitle": "Original",
    "fingerprint": hashlib.sha256(RAW.encode()).hexdigest(),
    "evidence": {"kind": "public", "score": "0.9", "rank": 1},
    "sources": [{"url": "https://www.kaggle.com/code/a/b?scriptVersionId=123"}],
    "awaitingExplanation": True,
    "steps": [],
}
KEYS = providers({"OPENAI_API_KEY": "test-openai", "DEEPSEEK_API_KEY": "test-deepseek"})
YES = dict(
    selected=True,
    reason="可以复现分组验证和拟合。",
    reference="Cell 1",
    quote="GroupKFold(5)",
)
LESSON = dict(
    title="分组验证",
    titleEN="Group folds",
    summary="按组划分样本。",
    summaryEN="Split by group.",
    takeaway="检查各折。",
    takeawayEN="Inspect the folds.",
    exercise={"zh": "对比各折。", "en": "Compare folds."},
    tags=["GroupKFold"],
    steps=[
        dict(
            title="划分",
            titleEN="Split",
            body="分组验证。",
            bodyEN="Group validation.",
            why="同组样本不跨折。",
            whyEN="Groups never span folds.",
            limit="未报告收益。",
            limitEN="No gain is reported.",
            reference="Cell 1",
            quote="GroupKFold(5)",
        ),
        dict(
            title="拟合",
            titleEN="Fit",
            body="模型拟合。",
            bodyEN="Fit the model.",
            why="用训练折拟合。",
            whyEN="Fit on training folds.",
            limit="无对照。",
            limitEN="No baseline.",
            reference="Cell 2",
            quote="model.fit(train)",
        ),
    ],
    findings=[],
    evidence={"rank": 42},
    sources=[{"url": "https://untrusted.example"}],
)
REPORT = (
    "## Setup\nFive group folds.\n"
    "## Results\nAUC by context rows: 107,000 gives 0.946076; 214,000 gives 0.946175; "
    "the last step added +14.2u. Pseudo-labels cost −0.13u.\n"
    "## Notes\nOne seed, fold 0 only."
)


def finding(**chart):
    return dict(
        claim="上下文越多 AUC 越高，从 0.946076 升到 0.946175。",
        claimEN="More context raised AUC from 0.946076 to 0.946175.",
        setup="同一折、同一模型，只改上下文行数。",
        setupEN="Same fold and model; only context rows change.",
        caveat="只用了一个种子。",
        caveatEN="A single seed.",
        reference="## Results",
        quote="AUC by context rows",
        chart=chart or None,
    )


def write(*findings):
    doc = copy.deepcopy(LESSON)
    for step, ref in zip(doc["steps"], ("## Setup", "## Results")):
        step.update(reference=ref, quote=REPORT.split(ref + "\n")[1][:12])
    doc["findings"] = list(findings)
    return doc


class EditorialTests(unittest.TestCase):
    def run_editor(self, item, transport, configured=None, budget=8):
        editor = Editor(KEYS if configured is None else configured, transport, budget)
        with contextlib.redirect_stdout(io.StringIO()):
            enrich({item["id"]: item}, {"comp": COMP}, lambda _: RAW, "now", editor)
        return editor

    def test_both_providers_and_independent_leaderboard(self):
        for keys, expected in [
            (KEYS, ["deepseek", "openai"]),
            ({"openai": KEYS["openai"]}, ["openai", "openai"]),
            ({"deepseek": KEYS["deepseek"]}, ["deepseek", "deepseek"]),
        ]:
            item = copy.deepcopy(ITEM)
            transport = Mock(side_effect=[YES, LESSON])
            self.run_editor(item, transport, keys)
            self.assertEqual(
                [call.args[0].name for call in transport.call_args_list], expected
            )
            self.assertEqual(item["llmReview"]["status"], "published")
            self.assertEqual(item["evidence"], ITEM["evidence"])
            self.assertEqual(item["sources"], ITEM["sources"])
            self.assertEqual(item["steps"][0]["source"], 0)
            self.assertNotIn("awaitingExplanation", item)
            self.run_editor(item, transport)
            self.assertEqual(transport.call_count, 2)

    def test_skip_and_no_key(self):
        item = copy.deepcopy(ITEM)
        transport = Mock(return_value={"selected": False, "reason": "缺少方法细节"})
        self.run_editor(item, transport, {})
        self.assertNotIn("llmReview", item)
        self.run_editor(item, transport)
        self.run_editor(item, transport)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(item["llmReview"]["status"], "skipped")
        self.assertTrue(item["awaitingExplanation"])
        self.assertEqual(item["steps"], [])

    def test_failed_screen_fallback_and_resume_after_budget(self):
        item = copy.deepcopy(ITEM)
        transport = Mock(side_effect=[HTTPError("test", 429, "limited", {}, None), YES])
        editor = self.run_editor(item, transport, budget=2)
        self.assertEqual(editor.remaining, 0)
        self.assertEqual(item["llmReview"]["screenedBy"]["provider"], "openai")
        writer = Mock(return_value=LESSON)
        self.run_editor(item, writer, budget=1)
        self.assertEqual(writer.call_count, 1)
        self.assertEqual(item["llmReview"]["status"], "published")

    def test_wrong_cell_or_changed_material_cannot_publish(self):
        item = copy.deepcopy(ITEM)
        bad = copy.deepcopy(LESSON)
        bad["steps"][0]["reference"] = "Cell 2"
        self.run_editor(item, Mock(side_effect=[YES, bad, bad]))
        self.assertEqual(item["llmReview"]["status"], "selected")
        self.assertEqual(item["steps"], [])
        fresh = copy.deepcopy(ITEM)
        fresh["fingerprint"] = "outdated"
        transport = Mock()
        self.run_editor(fresh, transport)
        transport.assert_not_called()
        self.assertFalse(
            cited(
                {"reference": "Validation", "quote": "fit the model"},
                "## Validation\nsplit rows\n## Training\nfit the model",
                False,
            )
        )

    def test_provider_request_uses_only_its_own_key(self):
        self.assertEqual(KEYS["openai"].model, "gpt-6.2-sol")
        self.assertEqual(providers({"OPENAI_API_KEY": "k", "OPENAI_MODEL": "other"})["openai"].model, "other")
        for provider in KEYS.values():
            with patch("editorial.urllib.request.build_opener") as opener:
                opener.return_value.open.return_value.__enter__.return_value.read.return_value = (
                    b'{"choices":[{"message":{"content":"{}"}}]}'
                )
                self.assertEqual(
                    request_json(
                        provider, SCREEN, {"source": RAW, "type": "notebook"}, 600
                    ),
                    {},
                )
                req = opener.return_value.open.call_args.args[0]
                self.assertEqual(req.full_url, provider.base + "/chat/completions")
                self.assertEqual(
                    req.get_header("Authorization"), "Bearer " + provider.key
                )
                self.assertNotIn(provider.key.encode(), req.data)

    def test_server_binds_real_source_blocks(self):
        blocks = source_blocks(RAW, True)
        selected = bind_references({"selected": True, "evidenceID": 2}, blocks, True)
        self.assertEqual(selected["reference"], "Cell 2")
        self.assertTrue(cited(selected, RAW, True))
        with self.assertRaises(ValueError):
            bind_references({"steps": [{"evidenceID": 200}]}, blocks, False)
        writeup = (
            "## Validation\nFit models on held-out groups.\n## Results\nReported AUC."
        )
        blocks = source_blocks(writeup, False)
        result = bind_references({"steps": [{"evidenceID": 1}]}, blocks, False)
        self.assertTrue(cited(result["steps"][0], writeup, False))

    def test_recent_writeup_changes_reenter_queue(self):
        c = dict(
            id=123,
            hasLeaderboard=True,
            competitionName="comp",
            title="Competition",
            deadline="later",
            dateCreated="before",
        )
        path = "/competitions/comp/writeups/demo"
        board = dict(
            teams=[dict(teamId=1, teamName="Author", solutionWriteUpUrl=path)],
            privateLeaderboard=[dict(teamId=1, rank=1, displayScore="1")],
        )

        def api(method, **kw):
            return (
                board
                if "Leaderboard" in method
                else dict(
                    id=9,
                    title="Original",
                    url=path,
                    message={
                        "rawMarkdown": "# Method\nNew evidence",
                        "postDate": "then",
                    },
                )
            )

        with patch("refresh.api", side_effect=api):
            _, items = sync_one(c, False, {}, "now")
            indexed = items[0]
            indexed["llmReview"] = {"status": "skipped"}
            _, same = sync_one(c, False, {"w-9": indexed}, "later")
            self.assertEqual(same[0]["llmReview"]["status"], "skipped")
            indexed["fingerprint"] = "earlier material"
            _, changed = sync_one(c, False, {"w-9": indexed}, "later")
            self.assertNotIn("llmReview", changed[0])
            self.assertTrue(changed[0]["awaitingExplanation"])


class FindingTests(unittest.TestCase):
    CHART = dict(
        kind="line",
        unit="AUC",
        better="higher",
        labels=[{"zh": "10.7 万行", "en": "107k rows"}, {"zh": "21.4 万行", "en": "214k rows"}],
        series=[{"name": {"zh": "折 0", "en": "Fold 0"}, "values": ["0.946076", "0.946175"]}],
    )

    def test_reported_numbers_become_a_chart(self):
        lesson = lesson_result(write(finding(**self.CHART)), REPORT, False)
        result = lesson["findings"][0]
        self.assertEqual(result["reference"], "## Results")
        self.assertEqual(result["source"], 0)
        self.assertEqual(result["caveatEN"], "A single seed.")
        values = result["chart"]["series"][0]["values"]
        self.assertEqual([v["value"] for v in values], [0.946076, 0.946175])
        self.assertEqual(values[0]["text"], "0.946076")
        self.assertEqual(lesson["steps"][0]["limitEN"], "No gain is reported.")

    def test_numbers_outside_the_cited_section_are_not_charted(self):
        for values in (["0.946076", "0.95"], ["0.946076", "-14.2"], ["0.946", "0.946175"]):
            chart = dict(self.CHART, series=[dict(self.CHART["series"][0], values=values)])
            with contextlib.redirect_stdout(io.StringIO()):
                result = lesson_result(write(finding(**chart)), REPORT, False)
            self.assertNotIn("chart", result["findings"][0])
        signed = dict(self.CHART, kind="bar", series=[dict(self.CHART["series"][0], values=["+14.2u", "−0.13u"])])
        values = lesson_result(write(finding(**signed)), REPORT, False)["findings"][0]["chart"]["series"][0]["values"]
        self.assertEqual([v["value"] for v in values], [14.2, -0.13])

    def test_invented_decimal_or_missing_findings_block_publication(self):
        invented = finding()
        invented["claimEN"] = "Context raised AUC to 0.9512."
        with self.assertRaises(ValueError):
            lesson_result(write(invented), REPORT, False)
        missing = write()
        del missing["findings"]
        with self.assertRaises(ValueError):
            lesson_result(missing, REPORT, False)
        unsourced = finding()
        unsourced["quote"] = "not in the writeup"
        with self.assertRaises(ValueError):
            lesson_result(write(unsourced), REPORT, False)
        self.assertTrue(appears("668,665", "rows: 668,665 train"))
        self.assertFalse(appears("665", "rows: 668,665 train"))
        self.assertFalse(appears("1", "gain 1.62u"))
        self.assertTrue(copied_decimals("伪标签让堆叠下降 −0.13u。", REPORT))
        self.assertFalse(copied_decimals("Pseudo-labels added 0.13u.", REPORT))

    def test_earlier_lessons_gain_detail_without_moving_steps(self):
        item = copy.deepcopy(ITEM)
        item.pop("awaitingExplanation")
        item["fingerprint"] = hashlib.sha256(REPORT.encode()).hexdigest()
        item["evidence"] = {"kind": "final", "rank": 2}
        item["steps"] = [
            dict(title="设定", body="短。", reference="Setup", source=0),
            dict(title="结果", titleEN="Results", body="短。", reference="## Results", source=0),
        ]
        detail = write(finding(**self.CHART))
        for step in detail["steps"]:
            step.pop("title")
        detail["steps"][0]["titleEN"] = "Setup"
        transport = Mock(return_value=detail)
        editor = Editor(KEYS, transport, 8)
        with contextlib.redirect_stdout(io.StringIO()):
            enrich({item["id"]: item}, {"comp": COMP}, lambda _: REPORT, "now", editor)
        self.assertEqual(transport.call_args.args[1][:20], __import__("editorial").DEEPEN[:20])
        self.assertEqual([s["title"] for s in item["steps"]], ["设定", "结果"])
        self.assertEqual(item["steps"][0]["reference"], "Setup")
        self.assertEqual(item["steps"][0]["titleEN"], "Setup")
        self.assertEqual(item["steps"][1]["titleEN"], "Results")
        self.assertEqual(item["steps"][1]["whyEN"], "Fit on training folds.")
        self.assertEqual(len(item["findings"]), 1)
        self.assertEqual(item["llmReview"]["deepenedBy"]["provider"], "openai")
        with contextlib.redirect_stdout(io.StringIO()):
            enrich({item["id"]: item}, {"comp": COMP}, lambda _: REPORT, "later", editor)
        self.assertEqual(transport.call_count, 1)

    def test_deepening_cannot_move_a_step_and_keeps_a_budget_share(self):
        item = copy.deepcopy(ITEM)
        item.pop("awaitingExplanation")
        item["fingerprint"] = hashlib.sha256(REPORT.encode()).hexdigest()
        item["evidence"] = {"kind": "final", "rank": 2}
        item["steps"] = [
            dict(title="设定", body="短。", reference="## Setup", source=0),
            dict(title="结果", body="短。", reference="## Results", source=0),
        ]
        moved = write()
        moved["steps"].reverse()
        with contextlib.redirect_stdout(io.StringIO()):
            enrich({item["id"]: item}, {"comp": COMP}, lambda _: REPORT, "now",
                   Editor(KEYS, Mock(return_value=moved), 8))
        self.assertNotIn("findings", item)
        self.assertEqual(item["llmReview"]["lastDeepen"], "now")
        waiting = {}
        for n in range(12):
            entry = copy.deepcopy(ITEM)
            entry["id"] = f"k-{n}"
            waiting[entry["id"]] = entry
        waiting[item["id"]] = item
        transport = Mock(side_effect=lambda provider, prompt, *_: write() if prompt != SCREEN else {"selected": False, "reason": "无"})
        with contextlib.redirect_stdout(io.StringIO()):
            enrich(waiting, {"comp": COMP}, lambda l: REPORT if l is item else RAW, "later", Editor(KEYS, transport, 8))
        self.assertEqual(item["findings"], [])
        self.assertEqual(transport.call_count, 8)
