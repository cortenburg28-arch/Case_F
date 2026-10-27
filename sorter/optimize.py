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
        if self.cfg["columns"].get("choices_ranked", True):
            ranks = self.sc["named_by_rank"]
            pts = ranks[min(student.choices.index(pid), len(ranks) - 1)]
        else:
            pts = self.sc["named_unranked"]
        if student.single_pick:
            pts *= self.sc["single_pick_factor"]
        return pts

    def type_points(self, student, pid):
        n = sum(w for t, w in student.types.items() if t in self.by_id[pid].types)
        return min(n * self.sc["type_match"], self.sc["type_match_cap"])

    def sdg_points(self, student, pid):
        n = sum(w for g, w in student.sdgs.items() if g in self.by_id[pid].sdgs)
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
    if not cfg["columns"].get("choices_ranked", True):
        rw = [1.0]
    d = {p.id: 0.0 for p in projects}
    for s in students:
        w = grade_weight(cfg, s)
        # With unranked checkboxes, someone who ticks 12 projects should not
        # count 12 times: each student's picks share about 3 votes.
        spread = 1.0 if len(rw) > 1 else min(1.0, 3 / max(len(s.choices), 1))
        for rank, pid in enumerate(s.choices):
            if not scorer.blocked(s, pid):
                f = cfg["scoring"]["single_pick_factor"] if s.single_pick else spread
                d[pid] += w * f * rw[min(rank, len(rw) - 1)]
        for p in projects:
            if p.track == s.track:
                d[p.id] += 0.002 * w * (scorer.type_points(s, p.id) + scorer.sdg_points(s, p.id))
    return d


def minor_weeks(cfg):
    return cfg["selection"].get("minors_run_each_week", True)


def select_projects(cfg, projects, students, dem, cut=()):
    """Must-run projects first, then the most demanded, per track. Makes sure there
    are enough seats at target size; adds projects (and says so) if not.

    Minors run once in week 1 and once in week 2 with different students, so
    the minor seats needed per week equal the number of minor students."""
    sel = cfg["selection"]
    size = cfg["size"]
    k = sel["minors_per_minor_student"]
    weekly = minor_weeks(cfg)
    seats = {"major": 0, "minor": 0}
    for s in students:
        seats[s.track] += 1 if s.track == "major" or weekly else k
    wanted = {"major": sel["majors_to_run"], "minor": sel["minors_to_run"]}
    chosen, notes = [], []
    for track in ("major", "minor"):
        groups_of = 1 if track == "major" or not weekly else k
        pool = [p for p in projects if p.track == track
                and not all(g in cut for g in group_ids(p, groups_of))]
        pool.sort(key=lambda p: (not p.must_run, -dem[p.id]))
        need = math.ceil(seats[track] / size["target_max"]) if seats[track] else 0
        if track == "minor" and seats[track]:
            need = max(need, k)
        must = sum(p.must_run for p in pool)
        n = max(wanted[track], need, must)
        # No point running more projects than can be filled to the minimum.
        n = min(n, max(seats[track] // size["min"], must, k if track == "minor" else 1),
                len(pool))
        if n != wanted[track] and seats[track]:
            per = " per week" if groups_of > 1 else ""
            notes.append(f"{seats[track]} {track} seats needed{per}: running {n} {track}s "
                         f"instead of {wanted[track]} to keep groups between "
                         f"{size['min']} and {size['target_max']}.")
        if seats[track] > n * size["hard_max"]:
            notes.append(f"Not enough {track} projects: {seats[track]} seats needed but only "
                         f"{n * size['hard_max']} fit at {size['hard_max']} per group. "
                         f"Some groups will be over the hard maximum.")
        chosen += pool[:n]
    return chosen, notes


def group_ids(project, n):
    return [project.id] if n == 1 else [f"{project.id}/W{w}" for w in range(1, n + 1)]


class Group:
    """One group of students: a major, or a minor in one week."""

    def __init__(self, gid, project, week):
        self.id, self.project, self.week = gid, project, week

    @property
    def label(self):
        return self.project.name + (f" (week {self.week})" if self.week else "")


def make_groups(cfg, running, cut=()):
    k = cfg["selection"]["minors_per_minor_student"]
    groups = {}
    for p in running:
        n = k if p.track == "minor" and minor_weeks(cfg) else 1
        for w, gid in enumerate(group_ids(p, n), 1):
            if gid not in cut:
                groups[gid] = Group(gid, p, w if n > 1 else None)
    return groups


class Assignment:
    """Assignment units: one per major student, N per minor student (one per minor).
    With weekly minors, a minor student's unit k goes to a week-k group."""

    def __init__(self, cfg, scorer, students, groups):
        self.cfg, self.scorer = cfg, scorer
        self.size, self.pen = cfg["size"], cfg["penalties"]
        self.groups = groups
        self.running = {g.project.id: g.project for g in groups.values()}
        self.units = []
        k = cfg["selection"]["minors_per_minor_student"]
        for s in students:
            for slot in range(1 if s.track == "major" else k):
                self.units.append((s, slot))
        self.where = [None] * len(self.units)
        self.members = defaultdict(set)         # group id -> unit indexes
        self.owner = defaultdict(list)          # student id -> unit indexes
        for i, (s, _) in enumerate(self.units):
            self.owner[s.id].append(i)
        self.cache = {}

    def project_of(self, i):
        return self.groups[self.where[i]].project.id if self.where[i] else None

    # --- scoring -----------------------------------------------------------
    def unit_value(self, i, gid):
        s = self.units[i][0]
        key = (s.id, self.groups[gid].project.id)
        if key not in self.cache:
            self.cache[key] = self.scorer.score(s, key[1])
        return grade_weight(self.cfg, s) * self.cache[key]

    def project_penalty(self, gid, members=None):
        m = self.members[gid] if members is None else members
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

    def allowed(self, i, gid, ignore=None):
        s, slot = self.units[i]
        g = self.groups[gid]
        if g.project.track != s.track:
            return False
        if g.week and g.week != slot + 1:
            return False
        if self.scorer.blocked(s, g.project.id):
            return False
        # A minor student never gets the same minor twice.
        for j in self.owner[s.id]:
            if j != i and j != ignore and self.project_of(j) == g.project.id:
                return False
        return True

    def objective(self):
        total = sum(self.unit_value(i, g) for i, g in enumerate(self.where) if g)
        return total - sum(self.project_penalty(g) for g in self.groups)

    # --- moves -------------------------------------------------------------
    def put(self, i, gid):
        if self.where[i]:
            self.members[self.where[i]].discard(i)
        self.where[i] = gid
        if gid:
            self.members[gid].add(i)

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
                opts = [g for g in self.groups if self.allowed(i, g)
                        and len(self.members[g]) < self.size[limit]]
                if opts:
                    self.put(i, max(opts, key=lambda g: self.unit_value(i, g)))
        for i in order:      # only if every group is at hard_max
            if not self.where[i]:
                opts = [g for g in self.groups if self.allowed(i, g)]
                if opts:
                    self.put(i, max(opts, key=lambda g: self.unit_value(i, g)))

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
                for g in self.groups:
                    if g != self.where[i] and self.allowed(i, g):
                        d = self.delta_move(i, g)
                        if d is not None and d > best_d:
                            best, best_d = g, d
                if best:
                    self.put(i, best)
                    improved = True
            for i in idx:
                for j in idx:
                    a, b = self.where[i], self.where[j]
                    if j <= i or not a or not b or a == b:
                        continue
                    if self.units[i][0].id == self.units[j][0].id:
                        continue
                    if not (self.allowed(i, b, ignore=j) and self.allowed(j, a, ignore=i)):
                        continue
                    if self.delta_swap(i, j) > 1e-9:
                        self.put(i, b)
                        self.put(j, a)
                        improved = True
            if not improved:
                break


def run(cfg, projects, students):
    """Select, assign, cut groups under the minimum, repeat until stable."""
    scorer = Scorer(cfg, projects)
    dem = demand(cfg, scorer, students, projects)
    cut, cut_log = [], []
    notes = []
    for _ in range(3 * len(projects)):
        running, notes = select_projects(cfg, projects, students, dem, cut)
        asg = Assignment(cfg, scorer, students, make_groups(cfg, running, cut))
        rng = random.Random(cfg["optimizer"]["seed"])
        asg.greedy(rng)
        asg.improve(rng, cfg["optimizer"]["max_passes"])
        small = [g for g in asg.groups.values() if not g.project.must_run
                 and len(asg.members[g.id]) < cfg["size"]["min"]]
        if not small:
            break
        worst = min(small, key=lambda g: (len(asg.members[g.id]), dem[g.project.id]))
        cut.append(worst.id)
        cut_log.append(f"Cut {worst.label}: only {len(asg.members[worst.id])} students "
                       f"after sorting (minimum {cfg['size']['min']}).")
    return asg, dem, notes + cut_log, scorer
