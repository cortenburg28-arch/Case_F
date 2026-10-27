"""Read the config, the project list and the response sheets into plain objects."""
import csv
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

TYPE_TAGS = ("hands", "feet", "head", "heart")

# Short names of the UN SDGs, so "Quality Education" is understood as goal 4.
SDG_NAMES = {
    1: "no poverty", 2: "zero hunger", 3: "good health", 4: "quality education",
    5: "gender equality", 6: "clean water", 7: "clean energy", 8: "decent work",
    9: "industry, innovation", 10: "reduced inequalit", 11: "sustainable cities",
    12: "responsible consumption", 13: "climate action", 14: "life below water",
    15: "life on land", 16: "peace, justice", 17: "partnerships",
}


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
    id: str                 # email, lower case
    name: str
    grade: str              # "senior" / "junior" / "sophomore"
    gender: str             # "M" / "F" / "?" if unknown
    track: str              # "major" or "minor"
    choices: list           # project ids (in order of preference if ranked)
    types: dict             # tag -> weight (1.0 first choice, less for second)
    sdgs: dict              # goal number -> weight
    comments: str
    celebration: str = ""
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


def _norm(text):
    return " ".join(text.split()).lower()


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{" ".join((k or "").split()): (v or "").strip() for k, v in row.items()}
                for row in csv.DictReader(f)]


def find_column(headers, needle):
    """Google Form headers are whole questions. The config names a distinctive
    piece of each question; the first header containing it is used."""
    if not needle:
        return None
    n = _norm(needle)
    for h in headers:
        if _norm(h) == n:
            return h
    for h in headers:
        if n in _norm(h):
            return h
    return None


def as_list(v):
    return v if isinstance(v, list) else [v] if v else []


def parse_types(text):
    low = text.lower()
    return [t for t in TYPE_TAGS if re.search(rf"\b{t}\b", low)]


def parse_sdgs(text):
    found = [int(n) for n in re.findall(r"\b(\d{1,2})\b", text) if 1 <= int(n) <= 17]
    low = text.lower()
    found += [k for k, name in SDG_NAMES.items() if name in low and k not in found]
    return found


def weighted(cells, second_factor):
    """First answer counts fully, any later answer counts second_factor."""
    out = {}
    for k, values in enumerate(cells):
        for v in values:
            out.setdefault(v, 1.0 if k == 0 else second_factor)
    return out


def parse_yes(text):
    return text.strip().lower() in {"yes", "y", "true", "1", "x", "must run", "must"}


def parse_track(text):
    low = text.lower()
    if "minor" in low and "major" not in low:
        return "minor"
    if "major" in low and "minor" not in low:
        return "major"
    if "two minor" in low or "2 minor" in low:
        return "minor"
    return "major" if "major" in low else None


class ProjectMatcher:
    """Finds project names/ids inside free text, in the order they appear.

    Works with Google Forms' comma-separated checkbox answers (even if an
    option itself contains a comma), and matches longer names first so
    "Garden" never steals a match from "Garden Design".
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
            track=parse_track(row.get(c["track"], "")) or "major",
            types=set(parse_types(row.get(c["types"], ""))),
            sdgs=set(parse_sdgs(row.get(c["sdgs"], ""))),
            must_run=parse_yes(row.get(c["must_run"], "")),
        ))
    return projects


def grade_of(cfg, text):
    low = text.strip().lower()
    for grade, g in cfg["grades"].items():
        if low == grade or low in [a.lower() for a in g["aliases"]]:
            return grade
    return None


def _optional(cfg, key):
    p = cfg["inputs"].get(key)
    if p and _path(cfg, p).exists():
        return read_csv(_path(cfg, p))
    return []


def load_students(cfg, projects):
    """Returns (students, excluded, problems)."""
    c = cfg["columns"]
    sc = cfg["scoring"]
    matcher = ProjectMatcher(projects)
    by_id = {p.id: p for p in projects}
    problems = []

    def email(row):
        return (row.get("Email Address") or row.get("Email") or "").lower()

    excluded_ids = {email(r): r.get("Reason", "excluded") for r in _optional(cfg, "exclusions")}

    # Optional roster: gender (and grade) per email, since the form does not ask.
    roster = {email(r): r for r in _optional(cfg, "roster")}

    last_year = {}
    for row in _optional(cfg, "last_year"):
        found = matcher.find(row.get("Project", ""))
        last_year[email(row)] = (found[0] if found else row.get("Project", ""),
                                 "leader" in row.get("Role", "").lower())

    students, excluded, seen = [], [], set()
    for sheet in cfg["inputs"]["responses"]:
        sheet = sheet if isinstance(sheet, dict) else {"file": sheet}
        rows = read_csv(_path(cfg, sheet["file"]))
        if not rows:
            continue
        headers = list(rows[0].keys())
        col = {k: find_column(headers, c.get(k)) for k in
               ("id", "name", "grade", "gender", "track", "comments", "celebration")}
        multi = {k: [find_column(headers, n) for n in as_list(c.get(k))]
                 for k in ("choices", "types", "sdgs")}
        for k, v in list(col.items()) + [(k, x) for k, xs in multi.items() for x in xs]:
            if v is None and c.get(k) and k not in ("grade", "gender", "celebration"):
                problems.append(f"{sheet['file']}: no column matching '{c[k]}' for {k}.")
        for row in rows:
            sid = row.get(col["id"], "").lower() if col["id"] else ""
            if not sid:
                continue
            name = row.get(col["name"], "") or sid
            if sid in seen:
                problems.append(f"Duplicate response for {name} ({sid}); kept the first one.")
                continue
            seen.add(sid)
            if sid in excluded_ids:
                excluded.append((name, sid, excluded_ids[sid]))
                continue
            extra = roster.get(sid, {})
            grade = (grade_of(cfg, row.get(col["grade"], "")) if col["grade"] else None) \
                or grade_of(cfg, sheet.get("grade", "")) or grade_of(cfg, extra.get("Grade", ""))
            if grade is None:
                problems.append(f"No grade for {name} ({sid}); skipped. Set the grade on "
                                "the sheet in config.toml or add it to the roster.")
                continue
            gender = (row.get(col["gender"], "") if col["gender"] else "") or extra.get("Gender", "")
            choices = []
            for cc in multi["choices"]:
                for pid in matcher.find(row.get(cc, "") if cc else ""):
                    if pid not in choices:
                        choices.append(pid)
            raw_track = row.get(col["track"], "") if col["track"] else ""
            track = parse_track(raw_track)
            warnings = []
            if track is None:
                track = "major"
                warnings.append(f"track answer '{raw_track}' unclear, treated as major")
            s = Student(
                id=sid, name=name, grade=grade,
                gender=gender.strip().upper()[:1] or "?",
                track=track,
                choices=[p for p in choices if by_id[p].track == track],
                types=weighted([parse_types(row.get(x, "")) for x in multi["types"] if x],
                               sc["second_choice_factor"]),
                sdgs=weighted([parse_sdgs(row.get(x, "")) for x in multi["sdgs"] if x],
                              sc["second_choice_factor"]),
                comments=row.get(col["comments"], "") if col["comments"] else "",
                celebration=row.get(col["celebration"], "") if col["celebration"] else "",
                warnings=warnings,
            )
            dropped = [by_id[p].name for p in choices if by_id[p].track != track]
            if dropped:
                s.warnings.append(f"also picked {', '.join(dropped)} (not {track}s)")
            if sid in last_year:
                s.last_year, s.last_year_leader = last_year[sid]
            students.append(s)
    if students and not roster and all(s.gender == "?" for s in students):
        problems.append("No gender data (the form does not ask). Add a roster file with "
                        "Email Address, Gender to use the gender rule.")
    if students and not last_year:
        problems.append("No last-year list found, so repeats of last year's project "
                        "are not checked.")
    return students, excluded, problems
