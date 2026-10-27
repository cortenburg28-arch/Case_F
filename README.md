# Pomfret project sorter

Picks which projects run this year and sorts students into them, then writes a
master spreadsheet with a one-line reason for every placement. A human reviews
and tweaks the result afterwards (friends, special cases).

How it decides is explained in [METHODOLOGY.md](METHODOLOGY.md).

## Run it

Needs Python 3.11+ and `openpyxl` (`pip install openpyxl`).

```bash
python -m sorter dummy          # writes fake inputs to dummy_data/
python -m sorter run            # sorts using config.toml, writes output/
python -m unittest discover tests
```

Output (in `output/`):

- `master.xlsx` with sheets **Master** (every student by grade: project,
  picked or not, rationale, comments/friends, Celebration of Learning), **Rosters** (per project),
  **Projects** (size, gender, grade mix, flags), **Not running**, **Stats**
  (1st choice / top 3 per grade), **Excluded**, **Notes**.
- `master.csv`, `rosters.csv`, `projects.csv` for importing into Google Sheets.

## Real data

**Never commit real student data.** Download the Google Form sheets as CSV
into `data/` (ignored by git), copy `config.toml` to `data/config.toml`,
point the `[inputs]` paths at the real files and run
`python -m sorter run --config data/config.toml`. Paths are relative to the config file.

Input files (see `dummy_data/` for the exact format):

| File | What it holds |
| --- | --- |
| responses (one per grade) | the Google Form export as is: email, name ("Last, First"), two SDG goals, two project types, major vs. two minors, Celebration of Learning, five checkbox questions with projects, comments |
| projects | Project ID, Project (exactly as in the form), Major/Minor, Type tags, SDG tags, Must run |
| roster (optional) | Email Address, Gender (the form does not ask for gender) |
| last_year | Email Address, Project, Role (Leader/Student) |
| exclusions | Email Address, Reason (leaders, freshman leaders, trip students) |

The grade comes from which sheet a response is in (set per file in
`config.toml`).

Columns are found by a piece of the question text set in `config.toml`, so
a reworded form only needs a config change. Projects are found inside the
checkbox answers by name, so a comma inside a project name is fine.
