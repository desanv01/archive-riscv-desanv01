from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

import cov
import run_suite


TEST_TMP = run_suite.ROOT / "tests" / ".tmp"
TEST_TMP.mkdir(parents=True, exist_ok=True)


class ConfigSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = run_suite.load_manifest()

    def test_manifest_has_exactly_32_unique_suites(self):
        suites = self.manifest["suites"]
        self.assertEqual(32, self.manifest["suite_count"])
        self.assertEqual(32, len(suites))
        self.assertEqual(32, len({item["id"] for item in suites}))

    def test_every_config_is_complete_and_valid(self):
        for item in self.manifest["suites"]:
            path = run_suite.ROOT / item["config"]
            config = yaml.safe_load(path.read_text(encoding="ascii"))
            self.assertFalse(
                run_suite.validate_config(item, config, self.manifest["isa"]),
                msg=item["id"],
            )

    def test_standard_aapg_runtime_paths(self):
        item = self.manifest["suites"][0]
        expected = run_suite.WORK / "suites" / item["id"] / "work"
        self.assertEqual(expected, run_suite.aapg_work_dir(item))
        self.assertEqual(expected / "bin", run_suite.aapg_work_dir(item) / "bin")

    def test_self_checking_and_multiseed_metadata(self):
        by_id = {item["id"]: item for item in self.manifest["suites"]}
        self.assertTrue(by_id["31_self_checking"]["self_checking"])
        self.assertEqual(1, by_id["31_self_checking"]["programs"])
        self.assertEqual(3, by_id["32_long_multiseed"]["programs"])


class CoverageTests(unittest.TestCase):
    def test_dynamic_spike_parser_and_extension_classifier(self):
        sample = """\
core   0: 0x0000000080000000 (0x00500513) addi a0, zero, 5
core   0: 3 0x0000000080000004 (0x02b50533) mul a0, a0, a1
core   0: 3 0x0000000080000008 (0x20c5b52f) amoadd.d.aq a0, a2, (a1)
core   0: 3 0x000000008000000c (0x1a2081d3) fdiv.d ft3, ft1, ft2
"""
        path = TEST_TMP / "trace.log"
        path.write_text(sample, encoding="ascii")
        counts = cov.parse_trace(path, "dynamic")
        self.assertEqual(1, counts["addi"])
        self.assertEqual(1, counts["mul"])
        self.assertEqual("A", cov.classify_instruction("amoadd.d.aq"))
        self.assertEqual("D", cov.classify_instruction("fdiv.d"))

    def test_empty_ucis_and_histogram_are_structurally_valid(self):
        manifest = run_suite.load_manifest()
        metadata = {"parsed_files": [], "dynamic_suites": [], "missing_dynamic_suites": [item["id"] for item in manifest["suites"]]}
        summary = cov.build_summary(manifest, [], metadata)
        xml_path = TEST_TMP / "cov.xml"
        html_path = TEST_TMP / "histogram.html"
        cov.write_ucis(xml_path, manifest, [], metadata)
        cov.write_histogram(html_path, manifest, [], summary)
        root = ET.parse(xml_path).getroot()
        self.assertEqual("UCIS", root.tag)
        self.assertIn("AAPG Instruction Histogram", html_path.read_text(encoding="utf-8"))



if __name__ == "__main__":
    unittest.main()
