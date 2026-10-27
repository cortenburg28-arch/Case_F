"""Read the config, the project list and the response sheets into plain objects."""
import csv
import re
import tomllib
from collections import Counter
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
    location: str = ""
    faculty: list = field(default_factory=list)
    form_text: str = ""     # the full option text on the form, if different from name


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


def email_column(rows, preferred=None):
    """The column holding email addresses: the preferred header if its values
    look like emails, else whichever column has the most values with an @."""
    if not rows:
        return None
    headers = list(rows[0].keys())

    def share(h):
        vals = [r.get(h, "") for r in rows if r.get(h, "")]
        return sum("@" in v for v in vals) / len(vals) if vals else 0

    if preferred and preferred in headers and share(preferred) >= 0.5:
        return preferred
    best = max(headers, key=share)
    return best if share(best) >= 0.5 else None


def norm_name(text):
    """'Last, First' and 'First Last' both become 'first last'."""
    text = text.strip().lower()
    if "," in text:
        last, first = text.split(",", 1)
        text = f"{first} {last}"
    return " ".join(re.findall(r"[a-z0-9]+", text))


NOT_A_PROJECT = re.compile(r"not interested|none of (these|the)", re.I)


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
            if p.form_text:
                # Match the whole option; a short name could also appear inside
                # another project's description.
                keys.append((" ".join(p.form_text.split()).lower(), p.id))
            else:
                keys.append((p.name.lower(), p.id))
            keys.append((p.id.lower(), p.id))
        self.keys = sorted(keys, key=lambda k: -len(k[0]))

    def find(self, text):
        low = " ".join(text.split()).lower()
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
        if not row.get(c["name"]) or NOT_A_PROJECT.search(row[c["name"]]):
            continue
        projects.append(Project(
            id=row.get(c["id"]) or row[c["name"]],
            name=row[c["name"]],
            track=parse_track(row.get(c["track"], "")) or "major",
            types=set(parse_types(row.get(c["types"], ""))),
            sdgs=set(parse_sdgs(row.get(c["sdgs"], ""))),
            must_run=parse_yes(row.get(c["must_run"], "")),
            location=row.get(c.get("location", "Location"), ""),
            faculty=[f.strip() for f in re.split(r"[;,/]", row.get(c.get("faculty", "Faculty"), ""))
                     if f.strip()],
            form_text=row.get("Form text", ""),
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

    def by_email(rows):
        col = email_column(rows, "Email Address")
        return [((r.get(col, "") if col else "").strip().lower(), r) for r in rows]

    excluded_ids, excluded_names = {}, {}
    ex_rows = _optional(cfg, "exclusions")
    name_col = next((h for h in (ex_rows[0] if ex_rows else {})
                     if "name" in h.lower()), None)
    for sid, r in by_email(ex_rows):
        reason = r.get("Reason", "") or "excluded (trip/leader list)"
        if sid:
            excluded_ids[sid] = reason
        if name_col and r.get(name_col):
            excluded_names[norm_name(r[name_col])] = reason

    # Optional roster: gender (and grade) per email, since the form does not ask.
    roster = {sid: r for sid, r in by_email(_optional(cfg, "roster")) if sid}

    last_year = {}
    for sid, row in by_email(_optional(cfg, "last_year")):
        found = matcher.find(row.get("Project", ""))
        last_year[sid] = (found[0] if found else row.get("Project", ""),
                          "leader" in row.get("Role", "").lower())

    # Collect answers first: if someone answered twice, the later answer wins.
    answers, dupes, odd = {}, 0, set()
    for sheet in cfg["inputs"]["responses"]:
        sheet = sheet if isinstance(sheet, dict) else {"file": sheet}
        rows = read_csv(_path(cfg, sheet["file"]))
        if not rows:
            continue
        headers = list(rows[0].keys())
        col = {k: find_column(headers, c.get(k)) for k in
               ("id", "name", "grade", "gender", "track", "comments", "celebration")}
        col["id"] = email_column(rows, col["id"])
        if not col["id"]:
            problems.append(f"{Path(sheet['file']).name}: no column with email addresses; "
                            "file skipped.")
            continue
        multi = {k: [find_column(headers, n) for n in as_list(c.get(k))]
                 for k in ("choices", "types", "sdgs")}
        for k, v in list(col.items()) + [(k, x) for k, xs in multi.items() for x in xs]:
            if v is None and c.get(k) and k not in ("grade", "gender", "celebration"):
                problems.append(f"{Path(sheet['file']).name}: no column matching "
                                f"'{c[k]}' for {k}.")
        for row in rows:
            sid = row.get(col["id"], "").strip().lower()
            name = row.get(col["name"], "") if col["name"] else ""
            trip = ""
            if "@" not in sid:
                # Something else is in the email field (on the real sheets: the
                # trip destination of trip students). Go by name instead.
                if not norm_name(name):
                    continue
                trip = sid
                if sid:
                    odd.add(sid)
                sid = "name:" + norm_name(name)
            if sid in answers:
                dupes += 1
                del answers[sid]            # re-insert so order follows the latest
            answers[sid] = (sheet, row, col, multi, trip)
    trips_out = cfg["inputs"].get("non_email_means_trip", True)
    if odd:
        what = ("treated as trip students and left out" if trips_out
                else "matched by name")
        problems.append(f"Some answers had something other than an email in the email "
                        f"column ({', '.join(sorted(odd)[:6])}); those students were {what}.")
    if dupes:
        problems.append(f"{dupes} students answered more than once; their latest "
                        "answer was used.")

    students, excluded = [], []
    for sid, (sheet, row, col, multi, trip) in answers.items():
        name = row.get(col["name"], "") or sid
        reason = excluded_ids.get(sid) or excluded_names.get(norm_name(name))
        if not reason and trip and trips_out:
            reason = f"Trip ({trip})"
        if reason:
            excluded.append((name, sid, reason))
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
            # "Not sure - willing to do either": go with the track they ticked
            # more projects in (majors on a tie).
            n_minor = sum(by_id[p].track == "minor" for p in choices)
            track = "minor" if n_minor > len(choices) - n_minor else "major"
            warnings.append(f"open to major or minor; placed as {track} since most of "
                            f"their picks are {track}s" if choices and raw_track else
                            f"no major/minor answer, treated as {track}")
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


def split_options(cells):
    """Split Google Forms checkbox answers into the options that were ticked.

    The export joins options with ", ", but option texts (with descriptions)
    contain commas too. A piece is glued back onto the one before it when it
    starts with a lower-case letter, or when the two pieces only ever appear
    together, side by side (then they are one option). Returns one list of
    options per cell."""
    seqs = [[x.strip() for x in cell.split(", ") if x.strip()] for cell in cells if cell.strip()]

    def glue_lowercase(seq):
        out = []
        for x in seq:
            if out and x[0].islower():
                out[-1] += ", " + x
            else:
                out.append(x)
        return out

    seqs = [glue_lowercase(q) for q in seqs]
    while True:
        count, nxt, prv = Counter(), {}, {}
        for q in seqs:
            for k, x in enumerate(q):
                count[x] += 1
                nxt.setdefault(x, Counter())[q[k + 1] if k + 1 < len(q) else None] += 1
                prv.setdefault(x, Counter())[q[k - 1] if k else None] += 1
        pair = None
        for a in count:
            (b, n), = nxt[a].most_common(1)
            if b is None or n != count[a] or prv[b][a] != count[b] or len(nxt[a]) != 1:
                continue
            # Two real options ticked together by one or two students stay apart.
            if count[a] >= 3 or not (" - " in a and " - " in b):
                pair = (a, b)
                break
        if not pair:
            return seqs
        a, b = pair
        merged = []
        for q in seqs:
            out, k = [], 0
            while k < len(q):
                if q[k] == a and k + 1 < len(q) and q[k + 1] == b:
                    out.append(a + ", " + b)
                    k += 2
                else:
                    out.append(q[k])
                    k += 1
            merged.append(out)
        seqs = merged


def short_name(option):
    """'Glass Art - Explore the history of…' -> 'Glass Art'."""
    m = re.match(r"(.+?)\s+-\s*\S", option)
    if m:
        return m.group(1).strip()
    # 'Beyond Reality: A two-week deep dive…' -> 'Beyond Reality', but keep
    # 'Project: Pomfret Runway' (a one-word part before the colon is part of the name).
    head, sep, _ = option.partition(": ")
    if sep and len(head.split()) >= 2:
        return head.strip()
    return option.strip()


def project_list_from_form(cfg, response_files, out_path):
    """When there is no project list yet, start one from the checkbox answers:
    every option someone ticked becomes a project. Options in a 'MINORS'
    question become minors, everything else majors. Tags, must-run, location
    and faculty are left empty to fill in. Returns the number of projects."""
    c = cfg["columns"]
    found = {}
    for needle in as_list(c.get("choices")):
        cells = []
        for path in response_files:
            rows = read_csv(path)
            col = find_column(list(rows[0].keys()), needle) if rows else None
            if col:
                cells += [r.get(col, "") for r in rows]
        track = "Minor" if "minor" in needle.lower() else "Major"
        for seq in split_options(cells):
            for option in seq:
                if not NOT_A_PROJECT.search(option):
                    found.setdefault(option, [track, 0])[1] += 1
    used = set()
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Project ID", "Project", "Major/Minor", "Type tags", "SDG tags",
                    "Must run", "Location", "Faculty", "Times ticked", "Form text"])
        for k, (option, (track, n)) in enumerate(sorted(found.items()), 1):
            name = short_name(option)
            if name.lower() in used:
                name = option
            used.add(name.lower())
            w.writerow([f"P{k:02d}", name, track, "", "", "", "", "", n,
                        option if option != name else ""])
    return len(found)


def is_untouched_form_list(path):
    """True for a project list this tool made that nobody has filled in yet."""
    rows = read_csv(path)
    keys = ("Type tags", "SDG tags", "Must run", "Location", "Faculty")
    return bool(rows) and "Times ticked" in rows[0] and not any(r.get(k) for r in rows
                                                                 for k in keys)
