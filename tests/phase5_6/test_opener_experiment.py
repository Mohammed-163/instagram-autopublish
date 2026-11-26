import ast
import json
from collections import Counter
from datetime import timedelta
from pathlib import Path
import re
import unittest

from phase5_6.lib import hook_experiment as experiment
from phase5_6.lib.quran_content import (
    format_verse_reference,
    load_verses,
    verse_by_key,
    verse_reference_parts,
)


class TestOpenerExperiment(unittest.TestCase):
    def test_two_weeks_are_balanced_by_slot_and_weekday(self):
        start, end = experiment.START, experiment.END
        days = [start + timedelta(days=i) for i in range(14)]
        self.assertEqual(days[-1], end)
        assignments = Counter()
        for index, day in enumerate(days):
            slots = (1, 2) if day.weekday() in (6, 1, 3) else (1,)
            for slot in slots:
                label = experiment.planned_hook_variant(day, slot)
                assignments.update([label])
                self.assertNotEqual(label, experiment.planned_hook_variant(days[(index + 7) % 14], slot))
            if len(slots) == 2:
                self.assertNotEqual(experiment.planned_hook_variant(day, 1), experiment.planned_hook_variant(day, 2))
        self.assertEqual(assignments, {experiment.CONTROL: 10, experiment.SITUATION: 10})
        self.assertIsNone(experiment.planned_hook_variant(start - timedelta(days=1), 1))
        self.assertIsNone(experiment.planned_hook_variant(end + timedelta(days=1), 1))
        self.assertIsNone(experiment.planned_hook_variant(start, 3))
        self.assertNotEqual(experiment.experiment_style(experiment.FALLBACK), experiment.experiment_style(experiment.SITUATION))
        self.assertEqual(experiment.experiment_style(None), experiment.BASE_VISUAL_STYLE)
        for variant in (experiment.CONTROL, experiment.SITUATION, experiment.FALLBACK):
            self.assertEqual(experiment.base_visual_style(experiment.experiment_style(variant)), experiment.BASE_VISUAL_STYLE)
        self.assertEqual(experiment.base_visual_style("different"), "different")

    def test_references_cover_every_catalog_entry(self):
        verses = load_verses()
        self.assertGreaterEqual(len(verses), 225)
        for verse in verses:
            with self.subTest(key=verse["key"]):
                surah, first, last = verse_reference_parts(verse)
                ref = format_verse_reference(verse)
                self.assertIn(surah, ref)
                if "-" in verse["key"]:
                    self.assertIn(f"الآيات من {first} إلى {last}", ref)
                else:
                    self.assertIn(f"الآية {first}", ref)
        self.assertEqual(format_verse_reference(verse_by_key("2:156-157")), "البقرة، الآيات من 156 إلى 157")
        self.assertEqual(format_verse_reference(verse_by_key("2:186")), "البقرة، الآية 186")
        with self.assertRaises(ValueError):
            format_verse_reference({"key": "2:157-156", "ayah": 157, "surah": "البقرة"})
        with self.assertRaises(ValueError):
            format_verse_reference({"key": "2:156-157", "ayah": 157, "surah": "البقرة"})

    def test_caption_scrubs_generated_single_and_range_references(self):
        # Compile this pure function only; daily_generate imports external SDKs.
        path = Path(__file__).resolve().parents[2] / "phase5_6/scripts/daily_generate.py"
        fn = next(node for node in ast.parse(path.read_text()).body
                  if isinstance(node, ast.FunctionDef) and node.name == "_prepare_caption_and_hashtags")
        ns = {"re": re, "verse_reference_parts": verse_reference_parts}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec"), ns)
        prep = ns[fn.name]
        verse = verse_by_key("2:156-157")
        for model_reference in ("البقرة، الآية 156", "البقرة، الآيات 156–157", "البقرة 2:156-157", "البقرة، الآيات من 156 إلى 157"):
            caption, tags = prep(f"شرح عراقي ({model_reference}) #اختبار", "#أمل #أمل", verse)
            self.assertEqual(caption, "شرح عراقي")
            self.assertEqual(tags, ["#أمل"])


    def test_situation_rewrite_retries_and_uses_only_hook_field(self):
        # Isolate the method and call it with a fake completion provider.
        path = Path(__file__).resolve().parents[2] / "phase5_6/lib/gemini_client.py"
        node = next(node for node in ast.parse(path.read_text()).body
                    if isinstance(node, ast.ClassDef) and node.name == "GeminiClient")
        fn = next(fn for fn in node.body if isinstance(fn, ast.FunctionDef)
                  and fn.name == "rewrite_situation_hook")
        ns = {"json": json}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec"), ns)
        rewrite = ns[fn.name]

        class FakeGemini:
            def __init__(self, responses):
                self.responses = iter(responses)
                self.prompts = []

            def _call_with_fallback(self, prompt):
                self.prompts.append(prompt)
                return next(self.responses)

            _extract_json = staticmethod(json.loads)
            _normalize_iraqi_dialect = staticmethod(lambda d: d)

        model = FakeGemini(["[]", '{"hook_line":"فتحت الموبايل وبقيت تنتظر رد الشغل؟","caption":"changed"}'])
        hook = rewrite(model, "انتظار فرصة العمل", "شايل هم رزقك كل يوم؟", "آية للسياق", "وقفة للسياق")
        self.assertEqual(hook, "فتحت الموبايل وبقيت تنتظر رد الشغل؟")
        self.assertEqual(len(model.prompts), 2)
        self.assertIn("وقفة للسياق", model.prompts[0])
        self.assertIn("آية للسياق", model.prompts[0])
        model = FakeGemini(['{"hook_line":"قال الله وكل ما تتمنى يتحقق"}', '{"hook_line":"شايل هم رزقك كل يوم؟"}'])
        with self.assertRaises(ValueError):
            rewrite(model, "انتظار فرصة العمل", "شايل هم رزقك كل يوم؟", "آية للسياق", "وقفة للسياق")


if __name__ == "__main__":
    unittest.main()
