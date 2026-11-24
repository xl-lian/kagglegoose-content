import copy
import contextlib
import io
import hashlib
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from editorial import Editor, providers, enrich, cited, request_json, SCREEN
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
            reference="Cell 1",
            quote="GroupKFold(5)",
        ),
        dict(
            title="拟合",
            titleEN="Fit",
            body="模型拟合。",
            bodyEN="Fit the model.",
            reference="Cell 2",
            quote="model.fit(train)",
        ),
    ],
    evidence={"rank": 42},
    sources=[{"url": "https://untrusted.example"}],
)


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
        for provider in KEYS.values():
            with patch("editorial.urllib.request.build_opener") as opener:
                opener.return_value.open.return_value.__enter__.return_value.read.return_value = (
                    b'{"choices":[{"message":{"content":"{}"}}]}'
                )
                self.assertEqual(request_json(provider, SCREEN, {}, 600), {})
                req = opener.return_value.open.call_args.args[0]
                self.assertEqual(req.full_url, provider.base + "/chat/completions")
                self.assertEqual(
                    req.get_header("Authorization"), "Bearer " + provider.key
                )
                self.assertNotIn(provider.key.encode(), req.data)

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
