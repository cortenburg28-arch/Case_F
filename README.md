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
  choice rank, rationale, comments/friends), **Rosters** (per project),
  **Projects** (size, gender, grade mix, flags), **Not running**, **Stats**
  (1st choice / top 3 per grade), **Excluded**, **Notes**.
- `master.csv`, `rosters.csv`, `projects.csv` for importing into Google Sheets.

## Real data

**Never commit real student data.** Download the Google Form sheets as CSV
into `data/` (ignored by git), copy `config.toml` to `data/config.toml`,
point the `[inputs]` paths at the real files and run
`python -m sorter run --config data/config.toml`. Paths are relative to the config file.

Input files (see `dummy_data/` for the exact format):

| File | Columns |
| --- | --- |
| responses (one per grade) | Email Address, Name, Grade, Gender, Major or Minor, 1st..5th choice, Hands / Feet / Head / Heart, SDG goals, Comments |
| projects | Project ID, Project, Major/Minor, Type tags, SDG tags, Must run |
| last_year | Email Address, Project, Role (Leader/Student) |
| exclusions | Email Address, Reason (leaders, freshman leaders, trip students) |

Column names are set in `config.toml`, so a reworded form only needs a
config change. Project names are found inside the cells by name, so commas
or semicolons as separators both work.
