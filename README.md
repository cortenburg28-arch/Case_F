# Project Pomfret sorter

Picks which projects run this year and sorts students into them. The result
is one Excel file laid out like last year's roster document, with a one-line
reason for every placement. A human reviews and tweaks it afterwards
(friends, special cases).

How it decides is explained in [METHODOLOGY.md](METHODOLOGY.md).

## Run it from an iPad (GitHub Codespaces)

1. On the repo page on github.com: **Code → Codespaces → Create codespace on
   main**. It opens VS Code in the browser and installs everything (takes a
   minute the first time).
2. In the file list on the left, open the `data` folder. Drag the CSV files
   into it (or right-click `data` → **Upload...**):
   - the three Google Form exports (file names must contain `Seniors`,
     `Juniors`, `Sophomores`, which Google's download names already do if
     the forms are named that way)
   - the project list (`project` in the name)
   - optional: `roster.csv` (gender), `last year.csv`, `exclusions.csv`
3. Run it: menu (☰) → **Terminal → Run Task... → Sort students**.
   Or type `./sort.sh` in the terminal.
4. In the `output` folder, right-click **Project_Pomfret_Rosters.xlsx →
   Download**.

To try it without real data first: **Run Task... → Try with dummy data**.

**Privacy:** `data/` and `output/` are never committed, so real student
data stays out of the repo. Do **not** use github.com's "Add file → Upload
files": that would commit the files. Delete the codespace when you are done
(github.com/codespaces → ... → Delete). **Sort students (anonymized)**
replaces names with codes and leaves out comments. The key to put names back
is saved as `output/name_key.csv`.

## The Excel file

| Sheet | What it shows |
| --- | --- |
| Projects | #, project (MAJ-/MIN-), location, faculty 1-3, group sizes |
| Students | per grade, alphabetical: name, Project #1 + faculty, Project #2 + faculty (majors appear in both, minors are week 1 / week 2), and why |
| one sheet per project | students with grade, faculty, location, Celebration of Learning, comments; `TOTAL - N Students`; minors split into GROUP 1 (week 1) and GROUP 2 (week 2) |
| Details | every student with picks, last year's project, full rationale |
| Group sizes, Stats, Not running, Excluded, Notes | checks on the result |

Emails are not written to the output.

## Input files

See `dummy_data/` for the exact format.

| File | What it holds |
| --- | --- |
| responses (one per grade) | the Google Form export as is: email, name ("Last, First"), two SDG goals, two project types, major vs. two minors, Celebration of Learning, five checkbox questions with projects, comments |
| projects | Project ID, Project (exactly as in the form), Major/Minor, Type tags, SDG tags, Must run, Location, Faculty |
| roster (optional) | Email Address, Gender (the form does not ask for gender) |
| last year | Email Address, Project, Role (Leader/Student) |
| exclusions | Email Address, Reason (leaders, freshman leaders, trip students) |

Columns are found by a piece of the question text set in `config.toml`, so
a reworded form only needs a config change. Projects are found inside the
checkbox answers by name, so a comma inside a project name is fine. All
weights are in `config.toml` too.

## On a computer

Needs Python 3.11+ and `pip install -r requirements.txt`.

```bash
python -m sorter dummy                 # fake inputs in dummy_data/
python -m sorter run                   # sort the files named in config.toml
python -m sorter run --data data       # sort whatever CSVs are in data/
python -m unittest discover tests
```
