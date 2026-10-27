"""Run with: python -m unittest discover tests"""
import tempfile
import unittest
from pathlib import Path

from sorter import dummy, loader, optimize, report

ROOT = Path(__file__).resolve().parent.parent


class SorterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        dummy.generate(d / "in", seed=3)
        cfg = loader.load_config(ROOT / "config.toml")
        cfg["_base"] = d
        cfg["inputs"].update({
            "responses": [{"file": f"in/responses_{g}s.csv", "grade": g}
                          for g in ("sophomore", "junior", "senior")],
            "projects": "in/projects.csv", "last_year": "in/last_year.csv",
            "roster": "in/roster.csv",
            "exclusions": "in/exclusions.csv", "output_dir": "out",
        })
        cls.cfg = cfg
        cls.projects = loader.load_projects(cfg)
        cls.students, cls.excluded, cls.problems = loader.load_students(cfg, cls.projects)
        cls.asg, cls.dem, cls.notes, cls.scorer = optimize.run(cfg, cls.projects, cls.students)
        cls.out, cls.sheets = report.build(cfg, cls.asg, cls.dem, cls.notes, cls.scorer,
                                           cls.projects, cls.students, cls.excluded, [])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_everyone_placed_in_own_track(self):
        for (s, _), pid in zip(self.asg.units, self.asg.where):
            self.assertIsNotNone(pid)
            self.assertEqual(self.asg.running[pid].track, s.track)

    def test_real_form_headers_found(self):
        self.assertEqual(self.problems, [])
        s = self.students[0]
        self.assertIn(",", s.name)                  # "Last, First"
        self.assertIn(s.gender, ("M", "F"))         # from the roster
        self.assertTrue(s.types and s.sdgs and s.celebration)
        self.assertTrue(any(len(x.choices) > 1 for x in self.students))

    def test_excluded_students_not_sorted(self):
        ids = {s.id for s in self.students}
        self.assertTrue(self.excluded)
        for _, sid, _ in self.excluded:
            self.assertNotIn(sid, ids)

    def test_no_repeat_of_last_year_unless_leader(self):
        for (s, _), pid in zip(self.asg.units, self.asg.where):
            if pid == s.last_year:
                self.assertTrue(s.last_year_leader)

    def test_minor_students_get_two_different_minors(self):
        seen = {}
        for (s, _), pid in zip(self.asg.units, self.asg.where):
            if s.track == "minor":
                self.assertNotIn(pid, seen.setdefault(s.id, set()))
                seen[s.id].add(pid)
        self.assertTrue(all(len(v) == 2 for v in seen.values()))

    def test_sizes_within_limits(self):
        for pid, p in self.asg.running.items():
            n = len(self.asg.members[pid])
            self.assertLessEqual(n, self.cfg["size"]["hard_max"])
            if not p.must_run:
                self.assertGreaterEqual(n, self.cfg["size"]["min"])

    def test_seniors_do_at_least_as_well_as_sophomores(self):
        def rate(grade):
            # Students with a single pick can't be judged on picks (a minor
            # student needs two).
            u = [(s, p) for (s, _), p in zip(self.asg.units, self.asg.where)
                 if s.grade == grade and len(s.choices) > 1]
            return sum(p in s.choices for s, p in u) / len(u)
        self.assertGreaterEqual(rate("senior"), rate("sophomore"))

    def test_outputs_written(self):
        for f in ("master.xlsx", "master.csv", "rosters.csv", "projects.csv"):
            self.assertTrue((self.out / f).exists(), f)
        self.assertEqual(len(self.sheets["Master"]), len(self.students))
        self.assertTrue(all(r["Rationale"] for r in self.sheets["Master"]))


class MatcherTest(unittest.TestCase):
    def test_longest_name_wins_and_order_kept(self):
        P = loader.Project
        ps = [P("A", "Garden", "major", set(), set(), False),
              P("B", "Garden Design", "major", set(), set(), False),
              P("C", "Solar, Wind & Sun", "major", set(), set(), False)]
        m = loader.ProjectMatcher(ps)
        self.assertEqual(m.find("Solar, Wind & Sun, Garden Design, Garden"), ["C", "B", "A"])

    def test_tags_and_sdgs(self):
        self.assertEqual(loader.parse_types("Hands (building), Heart"), ["hands", "heart"])
        self.assertEqual(loader.parse_sdgs("Goal 4, 13 and 99"), [4, 13])
        self.assertEqual(loader.parse_sdgs("Climate Action"), [13])
        self.assertEqual(loader.parse_track("Two MINOR Projects"), "minor")
        self.assertEqual(loader.find_column(["Q1", "Please choose the TYPE\n of it"],
                                            "choose the type of"), "Please choose the TYPE\n of it")


if __name__ == "__main__":
    unittest.main()
