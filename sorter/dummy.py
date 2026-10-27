"""Generate fake input files in the same format as the real Google Form exports.

Names are "Student001, Test" style and emails end in @example.org, so nothing here
can be mistaken for real student data.
"""
import csv
import random
from pathlib import Path

PROJECTS = [
    # name, track, types, sdgs, must_run
    ("Community Garden", "Major", "hands;heart", "2;15", "yes"),
    ("River Restoration", "Major", "hands;feet", "6;14;15", "yes"),
    ("Habitat Build", "Major", "hands", "1;11", "yes"),
    ("Food Pantry Partnership", "Major", "heart;hands", "1;2", ""),
    ("Elementary Reading Buddies", "Major", "heart;head", "4", ""),
    ("Solar Audit", "Major", "head", "7;13", ""),
    ("Trail Maintenance", "Major", "feet;hands", "15;3", ""),
    ("Senior Center Visits", "Major", "heart", "3;10", ""),
    ("Water Quality Lab", "Major", "head;feet", "6;14", ""),
    ("Refugee Welcome Kits", "Major", "heart;hands", "10;16", ""),
    ("Local History Podcast", "Major", "head", "4;11", ""),
    ("Bike Repair Shop", "Major", "hands", "11;12", ""),
    ("Youth Soccer Coaching", "Major", "feet;heart", "3;4", ""),
    ("Composting Program", "Major", "hands;head", "12;13", ""),
    ("Climate Policy Brief", "Major", "head", "13;16", ""),
    ("Animal Shelter Support", "Major", "heart;hands", "15", ""),
    ("Farm-to-Table Kitchen", "Major", "hands;heart", "2;12", ""),
    ("Coding for Nonprofits", "Major", "head", "9;17", ""),
    ("Mural Project", "Major", "hands;heart", "11", ""),
    ("Invasive Species Survey", "Major", "feet;head", "15", ""),
    ("Tutoring Center", "Minor", "head;heart", "4", "yes"),
    ("Recycling Audit", "Minor", "head;hands", "12", ""),
    ("Blood Drive", "Minor", "heart", "3", ""),
    ("Pollinator Garden", "Minor", "hands", "15", ""),
    ("Fundraising 5K", "Minor", "feet", "3;17", ""),
    ("Letter Writing", "Minor", "heart", "10;16", ""),
    ("Campus Energy Watch", "Minor", "head", "7", ""),
    ("Clothing Drive", "Minor", "hands;heart", "1;12", ""),
    ("Bird Count", "Minor", "feet;head", "15", ""),
    ("Story Time Recording", "Minor", "heart;head", "4", ""),
]

GRADES = [("sophomores", 80), ("juniors", 80), ("seniors", 80)]

# The real form's questions (Google Forms uses the whole question as header).
H_EMAIL = "Email Address"
H_NAME = ("What is your Name?  Please answer Last name, First name  "
          "(i.e. Litowitz, Doug)")
H_SDG1 = ("Please choose a UN Sustainable Development Goals that you hope to focus on "
          "during your Project: Pomfret experience.   Note: Many Projects will include "
          "several Goals, so try to identify which you want to be central to your course:\n")
H_SDG2 = ("Please choose a second UN Sustainable Development Goals that you hope to focus "
          "on during your Project: Pomfret experience.   \n")
H_TYPE1 = ("Please choose the TYPE of Project you want to be the focus of your "
           "Project: Pomfret experience:\n")
H_TYPE2 = ("Please choose a second TYPE of Project you would be interested in focusing on "
           "for your Project: Pomfret experience:\n")
H_TRACK = ("Would you prefer to do a MAJOR Project (i.e. 2 weeks with a Celebration of "
           "Learning at the end) or two MINOR Projects (i.e. 1 week Projects with a short "
           "reflection essay at the end of each)?")
H_CEL = "What do you want to do for your Celebration of Learning at the end of Project: Pomfret?"
H_CLUB = ("The following Projects are connected to existing Clubs or Academic classes, but "
          "you do NOT need to be a part of the Club/Class to participate in the Project.  "
          "While the basic outline of these Projects are set, you will be involved in "
          "creating the Outcomes of these courses to fit the goals of the group.  Check ALL "
          "the Projects that you might be interested in joining.  ")
H_PMAJ = ("Below are some of the Projects that ran in previous years as MAJORS.  While the "
          "basic design of these Projects are set, you will be involved in modifying the "
          "Outcomes of these courses to fit the goals of the group.   Check ALL the Projects "
          "that you might be interested in joining.")
H_PMIN = H_PMAJ.replace("as MAJORS", "as MINORS")
H_TEDX = ("Below are some ideas for Projects that will end with a TedX performance in front "
          "of the entire School.  Check ALL the Projects that you might be interested in "
          "joining.")
H_NEW = ("Below are some ideas for entirely new Projects for this year.  Since these are new "
         "courses, you will be involved in helping design and create the Outcomes for these "
         "Projects.  Check ALL the Projects that you might be interested in joining.")
H_COMMENTS = ("Please share anything else you'd like me to know about your hopes for your "
              "Project: Pomfret experience (ideas, suggestions, people you'd like to work "
              "with, people you'd prefer not to work with, etc.)")
HEADERS = [H_EMAIL, H_NAME, H_SDG1, H_SDG2, H_TYPE1, H_TYPE2, H_TRACK, H_CEL,
           H_CLUB, H_PMAJ, H_PMIN, H_TEDX, H_NEW, H_COMMENTS]

SDG_LABELS = {
    1: "No Poverty", 2: "Zero Hunger", 3: "Good Health and Well-being",
    4: "Quality Education", 5: "Gender Equality", 6: "Clean Water and Sanitation",
    7: "Affordable and Clean Energy", 8: "Decent Work and Economic Growth",
    9: "Industry, Innovation and Infrastructure", 10: "Reduced Inequalities",
    11: "Sustainable Cities and Communities", 12: "Responsible Consumption and Production",
    13: "Climate Action", 14: "Life Below Water", 15: "Life on Land",
    16: "Peace, Justice and Strong Institutions", 17: "Partnerships for the Goals",
}
TYPE_LABELS = {"hands": "Hands (building, making, service)", "feet": "Feet (outdoors, moving)",
               "head": "Head (research, problem solving)", "heart": "Heart (people, community)"}
CELEBRATIONS = ["Presentation", "Exhibition", "Video", "Performance", "Not sure yet"]


def section(k, track):
    """Which checkbox question a project is listed under on the form."""
    if k % 6 == 0:
        return H_CLUB
    if k % 7 == 0:
        return H_TEDX
    if k % 5 == 0:
        return H_NEW
    return H_PMAJ if track == "Major" else H_PMIN


def generate(out_dir, seed=7):
    rng = random.Random(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    with open(out / "projects.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Project ID", "Project", "Major/Minor", "Type tags", "SDG tags", "Must run",
                    "Location", "Faculty"])
        for k, (name, track, types, sdgs, must) in enumerate(PROJECTS, 1):
            faculty = ", ".join(f"Teacher {rng.randint(1, 60):02d}"
                                for _ in range(rng.choice([2, 2, 3])))
            w.writerow([f"P{k:02d}", name, track, types.replace(";", ", "),
                        sdgs.replace(";", ", "), must, f"Room {100 + k}", faculty])

    majors = [p for p in PROJECTS if p[1] == "Major"]
    minors = [p for p in PROJECTS if p[1] == "Minor"]
    where = {p[0]: section(k, p[1]) for k, p in enumerate(PROJECTS, 1)}
    # Some projects are clearly more popular than others, like in real life.
    pop = {p[0]: rng.uniform(0.2, 3.0) for p in PROJECTS}
    pop["Habitat Build"], pop["Community Garden"], pop["Mural Project"] = 4.0, 3.5, 3.2
    pop["Climate Policy Brief"], pop["Letter Writing"] = 0.15, 0.2

    def pick(pool, k):
        pool = list(pool)
        chosen = []
        for _ in range(min(k, len(pool))):
            tot = sum(pop[p[0]] for p in pool)
            r, acc = rng.uniform(0, tot), 0
            for p in pool:
                acc += pop[p[0]]
                if acc >= r:
                    chosen.append(p)
                    pool.remove(p)
                    break
        return chosen

    everyone, n = [], 0
    for label, count in GRADES:
        rows = []
        for _ in range(count):
            n += 1
            sid = f"student{n:03d}@example.org"
            track = "Minor" if rng.random() < 0.22 else "Major"
            pool = majors if track == "Major" else minors
            k = 1 if rng.random() < 0.08 else rng.choice([3, 4, 5, 6, 8])
            picks = pick(pool, k)
            # Students sometimes also tick a project from the other track.
            if rng.random() < 0.3:
                picks += pick(minors if track == "Major" else majors, 1)
            types = [t for p in picks[:2] for t in p[2].split(";")]
            types = list(dict.fromkeys(types + rng.sample(list(TYPE_LABELS), 2)))[:2]
            goals = [int(g) for p in picks[:2] for g in p[3].split(";")]
            goals = list(dict.fromkeys(goals + [rng.randint(1, 17)]))[:2]
            comment = ""
            if rng.random() < 0.15:
                comment = f"I'd like to work with Student{rng.randint(1, 240):03d}"
            row = {
                H_EMAIL: sid,
                H_NAME: f"Student{n:03d}, Test",
                H_SDG1: f"Goal {goals[0]}: {SDG_LABELS[goals[0]]}",
                H_SDG2: f"Goal {goals[-1]}: {SDG_LABELS[goals[-1]]}",
                H_TYPE1: TYPE_LABELS[types[0]],
                H_TYPE2: TYPE_LABELS[types[-1]],
                H_TRACK: "MAJOR Project" if track == "Major" else "Two MINOR Projects",
                H_CEL: rng.choice(CELEBRATIONS),
                H_COMMENTS: comment,
            }
            for h in (H_CLUB, H_PMAJ, H_PMIN, H_TEDX, H_NEW):
                row[h] = ", ".join(p[0] for p in picks if where[p[0]] == h)
            rows.append(row)
            everyone.append((sid, label, pool))
        with open(out / f"responses_{label}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["Timestamp"] + HEADERS)
            w.writeheader()
            for r in rows:
                w.writerow({"Timestamp": "10/15/2026 9:00:00", **r})

    # The form does not ask for gender, so it comes from a separate roster.
    with open(out / "roster.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Email Address", "Gender"])
        for sid, _, _ in everyone:
            w.writerow([sid, rng.choice(["M", "F"])])

    # Last year's list: juniors and seniors did a project last year.
    with open(out / "last_year.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Email Address", "Project", "Role"])
        for sid, label, pool in everyone:
            if label != "sophomores":
                role = "Leader" if rng.random() < 0.05 else "Student"
                w.writerow([sid, rng.choice(pool)[0], role])

    # Leaders and trip students are taken out before sorting.
    with open(out / "exclusions.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Email Address", "Reason"])
        seniors = [e for e in everyone if e[1] == "seniors"]
        for sid, _, _ in rng.sample(seniors, 22):
            w.writerow([sid, "Project leader"])
        for sid, _, _ in rng.sample([e for e in everyone if e[1] != "seniors"], 10):
            w.writerow([sid, "Trip"])
    return out
