"""Read the config, the project list and the response sheets into plain objects."""
import csv
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

TYPE_TAGS = ("hands", "feet", "head", "heart")


@dataclass
class Project:
    id: str
    name: str
    track: str              # "major" or "minor"
    types: set
    sdgs: set
    must_run: bool


@dataclass
class Student:
    id: str
    name: str
    grade: str              # "senior" / "junior" / "sophomore"
    gender: str             # "M" / "F" / other
    track: str              # "major" or "minor"
    choices: list           # project ids, in order of preference
    types: set
    sdgs: set
    comments: str
    last_year: str = ""     # project id (or name if unknown)
    last_year_leader: bool = False
    warnings: list = field(default_factory=list)

    @property
    def single_pick(self):
        return len(self.choices) == 1


def load_config(path):
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    cfg["_base"] = Path(path).resolve().parent
    return cfg


def _path(cfg, p):
    p = Path(p)
    return p if p.is_absolute() else cfg["_base"] / p


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()}
                for row in csv.DictReader(f)]


def parse_types(text):
    low = text.lower()
    return {t for t in TYPE_TAGS if re.search(rf"\b{t}\b", low)}


def parse_sdgs(text):
    return {int(n) for n in re.findall(r"\b(\d{1,2})\b", text) if 1 <= int(n) <= 17}


def parse_yes(text):
    return text.strip().lower() in {"yes", "y", "true", "1", "x", "must run", "must"}


def parse_track(text):
    return "minor" if "minor" in text.lower() else "major"


class ProjectMatcher:
    """Finds project names/ids inside free text, in the order they appear.

    Works regardless of the separator Google Forms uses, and matches longer
    names first so "Garden" never steals a match from "Garden Design".
    """

    def __init__(self, projects):
        keys = []
        for p in projects:
            keys.append((p.name.lower(), p.id))
            keys.append((p.id.lower(), p.id))
        self.keys = sorted(keys, key=lambda k: -len(k[0]))

    def find(self, text):
        low = text.lower()
        hits = []
        for key, pid in self.keys:
            for m in re.finditer(rf"(?<![\w]){re.escape(key)}(?![\w])", low):
                hits.append((m.start(), m.end(), pid))
                low = low[:m.start()] + " " * (m.end() - m.start()) + low[m.end():]
        out = []
        for _, _, pid in sorted(hits):
            if pid not in out:
                out.append(pid)
        return out


def load_projects(cfg):
    c = cfg["project_columns"]
    projects = []
    for row in read_csv(_path(cfg, cfg["inputs"]["projects"])):
        if not row.get(c["name"]):
            continue
        projects.append(Project(
            id=row.get(c["id"]) or row[c["name"]],
            name=row[c["name"]],
            track=parse_track(row.get(c["track"], "")),
            types=parse_types(row.get(c["types"], "")),
            sdgs=parse_sdgs(row.get(c["sdgs"], "")),
            must_run=parse_yes(row.get(c["must_run"], "")),
        ))
    return projects


def grade_of(cfg, text):
    low = text.strip().lower()
    for grade, g in cfg["grades"].items():
        if low in [a.lower() for a in g["aliases"]]:
            return grade
    return None


def load_students(cfg, projects):
    """Returns (students, excluded, problems)."""
    c = cfg["columns"]
    matcher = ProjectMatcher(projects)
    by_id = {p.id: p for p in projects}
    choice_cols = c["choices"] if isinstance(c["choices"], list) else [c["choices"]]

    excluded_ids = {}
    ex_path = cfg["inputs"].get("exclusions")
    if ex_path and _path(cfg, ex_path).exists():
        for row in read_csv(_path(cfg, ex_path)):
            sid = row.get(c["id"], "").lower()
            if sid:
                excluded_ids[sid] = row.get("Reason", "excluded")

    last_year = {}
    ly_path = cfg["inputs"].get("last_year")
    if ly_path and _path(cfg, ly_path).exists():
        for row in read_csv(_path(cfg, ly_path)):
            sid = row.get(c["id"], "").lower()
            found = matcher.find(row.get("Project", ""))
            last_year[sid] = (found[0] if found else row.get("Project", ""),
                              "leader" in row.get("Role", "").lower())

    students, excluded, problems, seen = [], [], [], set()
    for sheet in cfg["inputs"]["responses"]:
        for row in read_csv(_path(cfg, sheet)):
            sid = row.get(c["id"], "").lower()
            if not sid:
                continue
            name = row.get(c["name"], sid)
            if sid in seen:
                problems.append(f"Duplicate response for {name} ({sid}); kept the first one.")
                continue
            seen.add(sid)
            if sid in excluded_ids:
                excluded.append((name, sid, excluded_ids[sid]))
                continue
            grade = grade_of(cfg, row.get(c["grade"], ""))
            if grade is None:
                problems.append(f"Unrecognized grade '{row.get(c['grade'])}' for {name}; skipped.")
                continue
            choices = []
            for col in choice_cols:
                for pid in matcher.find(row.get(col, "")):
                    if pid not in choices:
                        choices.append(pid)
            track = parse_track(row.get(c["track"], ""))
            s = Student(
                id=sid, name=name, grade=grade,
                gender=row.get(c["gender"], "").strip().upper()[:1] or "?",
                track=track,
                choices=[p for p in choices if by_id[p].track == track],
                types=parse_types(row.get(c["types"], "")),
                sdgs=parse_sdgs(row.get(c["sdgs"], "")),
                comments=row.get(c["comments"], ""),
            )
            dropped = [by_id[p].name for p in choices if by_id[p].track != track]
            if dropped:
                s.warnings.append(f"picked {', '.join(dropped)} outside their {track} track")
            if sid in last_year:
                s.last_year, s.last_year_leader = last_year[sid]
            students.append(s)
    return students, excluded, problems
