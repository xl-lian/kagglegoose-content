import json
import unittest
from decimal import Decimal
from refresh import CATALOG, public_scores, score_rank, bound_version


class EvidenceTests(unittest.TestCase):
    def test_directions_and_ties(self):
        scores = [Decimal(v) for v in range(100)]
        self.assertEqual(score_rank(Decimal(90), scores, True), 10)
        self.assertEqual(score_rank(Decimal(9), scores, False), 10)
        self.assertIsNone(score_rank(Decimal(89), scores, True))
        self.assertEqual(score_rank(Decimal(1), [Decimal(1)] * 10, True), 1)

    def test_incomplete_board(self):
        self.assertEqual(
            public_scores(
                dict(
                    teams=[dict(teamId=1), dict(teamId=2)],
                    publicLeaderboard=[dict(teamId=1, rank=1, displayScore="3")],
                )
            ),
            [],
        )

    def test_best_score_must_bind_to_one_run(self):
        k = dict(scriptVersionId=9, hasLinkedSubmission=True)
        v = dict(
            version=dict(versionNumber=1),
            run=dict(
                id=9,
                status="COMPLETE",
                commit=dict(settings=dict(dataSources=[dict(sourceId=7)])),
            ),
        )
        self.assertEqual(bound_version(k, [v], 7), v)
        self.assertIsNone(bound_version(k, [v, v], 7))
        self.assertIsNone(bound_version(k, [v], 8))
        self.assertIsNone(bound_version(dict(k, scriptVersionId=10), [v], 7))

    def test_catalog_integrity(self):
        d = json.loads(CATALOG.read_text())
        ids = {c["id"] for c in d["competitions"]}
        self.assertGreaterEqual(
            sum(l["evidence"]["kind"] == "final" for l in d["lessons"]), 6
        )
        self.assertEqual(len(d["lessons"]), len(set(l["id"] for l in d["lessons"])))
        for lesson in d["lessons"]:
            self.assertIn(lesson["competitionID"], ids)
            self.assertTrue(lesson["sources"])
            for step in lesson["steps"]:
                self.assertIn(step["source"], range(len(lesson["sources"])))

    def test_bilingual_reading_material_stays_paired(self):
        catalog = json.loads(CATALOG.read_text())
        for competition in catalog["competitions"]:
            if "guide" in competition:
                self.assertTrue(
                    all(competition["guide"][lang] for lang in ("zh", "en"))
                )
                self.assertTrue(competition["summaryEN"])
        for lesson in catalog["lessons"]:
            if not lesson["steps"]:
                continue
            self.assertTrue(lesson["summaryEN"] and lesson["takeawayEN"])
            self.assertTrue(all(step["bodyEN"] for step in lesson["steps"]))
            if lesson.get("readingMode") != "code":
                self.assertTrue(lesson["titleEN"])
                self.assertTrue(all(lesson["exercise"][lang] for lang in ("zh", "en")))

    def test_comparisons_reference_different_competitions_with_sources(self):
        catalog = json.loads(CATALOG.read_text())
        lessons = {lesson["id"]: lesson for lesson in catalog["lessons"]}
        for comparison in catalog["comparisons"]:
            cited = [lessons[key] for key in comparison["lessonIDs"]]
            self.assertGreaterEqual(len({l["competitionID"] for l in cited}), 2)
            self.assertTrue(all(l["steps"] and l["sources"] for l in cited))


class ReadingTests(unittest.TestCase):
    def test_source_notes_reference_real_cells(self):
        from reading import guide

        text = "Cell 1:\nmodel = CatBoostClassifier(depth=7)\nCell 2:\nparts = StratifiedKFold(4)"
        notes = guide(text)
        assert notes is not None
        self.assertEqual({p["reference"] for p in notes["steps"]}, {"Cell 1", "Cell 2"})
        validation = next(p for p in notes["steps"] if p["title"] == "验证设计")
        self.assertIn("minority examples", validation["bodyEN"])
        self.assertIn("少数类样本数", validation["body"])
        self.assertIsNone(
            guide("Cell 1:\n# This notebook mentions CatBoostClassifier and KFold")
        )
