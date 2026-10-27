# How the sorter decides

This is the proposal for how projects are chosen and students are placed.
Every number below is a setting in `config.toml`, so it can be changed and
re-run in seconds.

## Before sorting

- **Removed first:** project leaders, freshman leaders and trip students
  (the exclusions list). Freshmen are not in the response sheets.
- **Last year:** a student is never placed in the project they did last year,
  unless they were its leader.
- **Track:** major students get one major; minor students get two different
  minors. Picks outside a student's track are ignored and noted.

## Step 1: which projects run

1. Every **must-run** project runs.
2. The rest are ranked by **demand**: each pick counts by rank (1st = 1.0,
   2nd = 0.8, 3rd = 0.6, 4th = 0.45, 5th = 0.35), multiplied by the grade
   weight (below). Hands/feet/head/heart and SDG fit add a small amount so
   projects nobody named can still be ranked.
3. The top projects are taken until there are **14 majors and 8 minors**.
   If that is not enough seats to keep groups at 12 or fewer, more projects
   run and the Notes sheet says so.
4. After sorting, any project with **fewer than 8** students is cut (unless
   it is must-run), its students are re-sorted, and the next project in line
   may take its place. This repeats until no project is under 8.

## Step 2: who goes where

Each student gets points for each possible project:

| What matches | Points |
| --- | --- |
| Named the project: 1st / 2nd / 3rd / 4th / 5th choice | 100 / 85 / 72 / 60 / 50 |
| Each matching hands/feet/head/heart tag | +12 (max 24) |
| Each matching SDG goal | +5 (max 15) |
| Did it last year (not as leader) | not allowed |

So a named project with matching type and goals scores best, a named project
alone comes next, and an unnamed project with matching type comes after that.
Placing a student in a project they did not name is allowed when needed.

**Grade priority.** Points are multiplied by a grade weight: seniors x4,
juniors x2, sophomores x1. Seniors are also placed first, then juniors, then
sophomores, so a senior keeps their 1st choice unless that would cost a lot
for several younger students.

**Only one pick.** Students who named a single project get half the points
for it and are placed last within their grade, so naming one project does
not guarantee it.

**Group size.** Target 10 to 12. Groups can go up to 14 but each student
above 12 costs 40 points; each student below 10 costs 8 points; below 8
costs 60 more (and the project is cut, see above).

**Gender.** Lowest priority. A group should be all one gender or have at
least 3 of each. A mixed group with only 1 or 2 of a gender costs 6 points
per missing student, which is small on purpose: it only decides between
otherwise similar options. Groups that still miss the rule are flagged.

**Friends.** Not automated. Comments are shown next to each student in the
master sheet and the rosters for a human to review.

## How the placement is found

1. Students are placed one by one in priority order (seniors first, random
   order within a grade with a fixed seed, so runs are repeatable), each
   into their best-scoring project that still has room.
2. The result is then improved by moving single students and swapping pairs
   whenever that raises the total of all points minus size and gender
   penalties. It stops when no move or swap helps.

## What to check in the output

- **Master** sheet: the rationale column explains every placement, e.g.
  "2nd choice; matches hands/heart; SDG 15" or "none of their picks
  (not running: Solar Audit); matches head".
- **Projects** sheet: size, gender and grade mix, and flags for groups that
  are above target size or miss the gender rule.
- **Stats** sheet: share of 1st choice, top 3, and any named pick per grade.
