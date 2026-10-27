"""Step 1 (which projects run) and step 2 (who goes where)."""
import math
import random
from collections import Counter, defaultdict

FORBIDDEN = -10_000


class Scorer:
    def __init__(self, cfg, projects):
        self.cfg = cfg
        self.sc = cfg["scoring"]
        self.by_id = {p.id: p for p in projects}

    def named_points(self, student, pid):
        if pid not in student.choices:
            return 0
        rank = student.choices.index(pid)
        ranks = self.sc["named_by_rank"]
        pts = ranks[min(rank, len(ranks) - 1)] if ranks else self.sc["named_unranked"]
        if student.single_pick:
            pts *= self.sc["single_pick_factor"]
        return pts

    def type_points(self, student, pid):
        n = len(student.types & self.by_id[pid].types)
        return min(n * self.sc["type_match"], self.sc["type_match_cap"])

    def sdg_points(self, student, pid):
        n = len(student.sdgs & self.by_id[pid].sdgs)
        return min(n * self.sc["sdg_match"], self.sc["sdg_match_cap"])

    def blocked(self, student, pid):
        if student.last_year != pid:
            return False
        return not (student.last_year_leader and self.sc["allow_repeat_if_leader"])

    def score(self, student, pid):
        if self.blocked(student, pid):
            return FORBIDDEN
        return (self.named_points(student, pid) + self.type_points(student, pid)
                + self.sdg_points(student, pid))


def grade_weight(cfg, student):
    return cfg["grades"][student.grade]["weight"]


def demand(cfg, scorer, students, projects):
    """Estimated interest per project: grade-weighted, rank-weighted named picks,
    plus a small share of type/SDG fit so unpicked projects can still be ranked."""
    rw = cfg["selection"]["demand_rank_weights"]
    d = {p.id: 0.0 for p in projects}
    for s in students:
        w = grade_weight(cfg, s)
        for rank, pid in enumerate(s.choices):
            if not scorer.blocked(s, pid):
                f = cfg["scoring"]["single_pick_factor"] if s.single_pick else 1.0
                d[pid] += w * f * rw[min(rank, len(rw) - 1)]
        for p in projects:
            if p.track == s.track:
                d[p.id] += 0.002 * w * (scorer.type_points(s, p.id) + scorer.sdg_points(s, p.id))
    return d


def select_projects(cfg, projects, students, dem, cut=()):
    """Must-run projects first, then the most demanded, per track. Makes sure there
    are enough seats at target size; adds projects (and says so) if not."""
    sel = cfg["selection"]
    size = cfg["size"]
    units = {"major": 0, "minor": 0}
    for s in students:
        units[s.track] += 1 if s.track == "major" else sel["minors_per_minor_student"]
    wanted = {"major": sel["majors_to_run"], "minor": sel["minors_to_run"]}
    chosen, notes = [], []
    for track in ("major", "minor"):
        pool = [p for p in projects if p.track == track and p.id not in cut]
        pool.sort(key=lambda p: (not p.must_run, -dem[p.id]))
        need = math.ceil(units[track] / size["target_max"]) if units[track] else 0
        if track == "minor" and units[track]:
            need = max(need, sel["minors_per_minor_student"])
        n = max(wanted[track], need, sum(p.must_run for p in pool))
        # No point running more projects than can be filled to the minimum.
        cap = max(units[track] // size["min"], sum(p.must_run for p in pool))
        n = min(n, cap, len(pool))
        if n > wanted[track]:
            notes.append(f"{units[track]} {track} seats needed: running {n} {track}s instead of "
                         f"{wanted[track]} to stay within {size['target_max']} per project.")
        if units[track] > n * size["hard_max"]:
            notes.append(f"Not enough {track} projects: {units[track]} seats needed but only "
                         f"{n * size['hard_max']} fit at {size['hard_max']} per project. "
                         f"Some groups will be over the hard maximum.")
        chosen += pool[:n]
    return chosen, notes


class Assignment:
    """Assignment units: one per major student, N per minor student (one per minor)."""

    def __init__(self, cfg, scorer, students, running):
        self.cfg, self.scorer = cfg, scorer
        self.size, self.pen = cfg["size"], cfg["penalties"]
        self.running = {p.id: p for p in running}
        self.units = []
        k = cfg["selection"]["minors_per_minor_student"]
        for s in students:
            for slot in range(1 if s.track == "major" else k):
                self.units.append((s, slot))
        self.where = [None] * len(self.units)
        self.members = defaultdict(set)
        self.owner = defaultdict(list)          # student id -> unit indexes
        for i, (s, _) in enumerate(self.units):
            self.owner[s.id].append(i)
        self.cache = {}

    # --- scoring -----------------------------------------------------------
    def unit_value(self, i, pid):
        s = self.units[i][0]
        key = (s.id, pid)
        if key not in self.cache:
            self.cache[key] = self.scorer.score(s, pid)
        return grade_weight(self.cfg, s) * self.cache[key]

    def project_penalty(self, pid, members=None):
        m = self.members[pid] if members is None else members
        n = len(m)
        if n == 0:
            return 0.0
        p = 0.0
        if n < self.size["min"]:
            p += (self.size["min"] - n) * self.pen["under_min_per_student"]
        if n < self.size["target_min"]:
            p += (self.size["target_min"] - n) * self.pen["under_target_per_student"]
        if n > self.size["target_max"]:
            p += (n - self.size["target_max"]) * self.pen["over_target_per_student"]
        g = Counter(self.units[i][0].gender for i in m)
        mf = (g.get("M", 0), g.get("F", 0))
        if min(mf) > 0 and min(mf) < 3:
            p += (3 - min(mf)) * self.pen["gender_minority_per_missing"]
        return p

    def allowed(self, i, pid, ignore=None):
        s = self.units[i][0]
        if self.running[pid].track != s.track:
            return False
        if self.scorer.blocked(s, pid):
            return False
        # A minor student never gets the same minor twice.
        for j in self.owner[s.id]:
            if j != i and j != ignore and self.where[j] == pid:
                return False
        return True

    def objective(self):
        total = sum(self.unit_value(i, p) for i, p in enumerate(self.where) if p)
        return total - sum(self.project_penalty(p) for p in self.running)

    # --- moves -------------------------------------------------------------
    def put(self, i, pid):
        if self.where[i]:
            self.members[self.where[i]].discard(i)
        self.where[i] = pid
        if pid:
            self.members[pid].add(i)

    def greedy(self, rng):
        """Seniors first, then juniors, then sophomores; single-pickers last in
        their grade; random order otherwise (seeded, so runs are repeatable)."""
        order = list(range(len(self.units)))
        rng.shuffle(order)
        gorder = {g: v["order"] for g, v in self.cfg["grades"].items()}
        order.sort(key=lambda i: (self.units[i][1], gorder[self.units[i][0].grade],
                                  self.units[i][0].single_pick))
        for limit in ("target_max", "hard_max"):
            for i in order:
                if self.where[i]:
                    continue
                opts = [p for p in self.running if self.allowed(i, p)
                        and len(self.members[p]) < self.size[limit]]
                if opts:
                    self.put(i, max(opts, key=lambda p: self.unit_value(i, p)))
        for i in order:      # only if every project is at hard_max
            if not self.where[i]:
                opts = [p for p in self.running if self.allowed(i, p)]
                if opts:
                    self.put(i, max(opts, key=lambda p: self.unit_value(i, p)))

    def delta_move(self, i, new):
        old = self.where[i]
        if len(self.members[new]) >= self.size["hard_max"]:
            return None
        before = self.project_penalty(old) + self.project_penalty(new)
        after = (self.project_penalty(old, self.members[old] - {i})
                 + self.project_penalty(new, self.members[new] | {i}))
        return self.unit_value(i, new) - self.unit_value(i, old) - (after - before)

    def delta_swap(self, i, j):
        a, b = self.where[i], self.where[j]
        before = self.project_penalty(a) + self.project_penalty(b)
        ma = (self.members[a] - {i}) | {j}
        mb = (self.members[b] - {j}) | {i}
        after = self.project_penalty(a, ma) + self.project_penalty(b, mb)
        gain = (self.unit_value(i, b) + self.unit_value(j, a)
                - self.unit_value(i, a) - self.unit_value(j, b))
        return gain - (after - before)

    def improve(self, rng, max_passes):
        idx = list(range(len(self.units)))
        for _ in range(max_passes):
            improved = False
            rng.shuffle(idx)
            for i in idx:
                if not self.where[i]:
                    continue
                best, best_d = None, 1e-9
                for p in self.running:
                    if p != self.where[i] and self.allowed(i, p):
                        d = self.delta_move(i, p)
                        if d is not None and d > best_d:
                            best, best_d = p, d
                if best:
                    self.put(i, best)
                    improved = True
            for i in idx:
                for j in idx:
                    a, b = self.where[i], self.where[j]
                    if j <= i or not a or not b or a == b:
                        continue
                    if not (self.allowed(i, b, ignore=j) and self.allowed(j, a, ignore=i)):
                        continue
                    if self.units[i][0].id == self.units[j][0].id:
                        continue
                    if self.delta_swap(i, j) > 1e-9:
                        self.put(i, b)
                        self.put(j, a)
                        improved = True
            if not improved:
                break


def run(cfg, projects, students):
    """Select, assign, cut projects under the minimum, repeat until stable."""
    scorer = Scorer(cfg, projects)
    dem = demand(cfg, scorer, students, projects)
    cut, cut_log = [], []
    notes = []
    for _ in range(len(projects)):
        running, notes = select_projects(cfg, projects, students, dem, cut)
        asg = Assignment(cfg, scorer, students, running)
        rng = random.Random(cfg["optimizer"]["seed"])
        asg.greedy(rng)
        asg.improve(rng, cfg["optimizer"]["max_passes"])
        small = [p for p in running if not p.must_run
                 and len(asg.members[p.id]) < cfg["size"]["min"]]
        if not small:
            break
        worst = min(small, key=lambda p: (len(asg.members[p.id]), dem[p.id]))
        cut.append(worst.id)
        cut_log.append(f"Cut {worst.name}: only {len(asg.members[worst.id])} students "
                       f"after sorting (minimum {cfg['size']['min']}).")
    return asg, dem, notes + cut_log, scorer
