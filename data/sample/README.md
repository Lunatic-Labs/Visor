# Sample data (FAKE)

Made-up data for development and demos (KAN-24). Course numbers look realistic, but the **times, capacities, and prerequisites are invented**. Replace this with real registrar data once Ms. Hood shares it (KAN-35).

Planted problems the app should catch in term `2027SP`:

1. **CS 3433-01 vs CS 3233-01**: both MWF, with 10:00–10:50 overlapping 10:30–11:20
2. **CS 4123-01 vs SENG 3233-01**: both TR, with 1:00–2:15 overlapping 2:00–3:15
3. **CS 3113-01 lab vs PH 2414-01**: Thursday lab 3:30–6:20 overlaps the PH lecture Thursday 3:30–4:45
4. **CS 3213-01 is full** (30/30), so students need section 02
5. **Not a conflict:** MA 2314-01 (TR 9:30–10:45) and CS 2113-01 (TR 10:45–12:00) are back-to-back, which is allowed

Files: `terms.csv`, `courses.csv`, `prereqs.csv` (one row per OR-group; `|` separates the options), `sections.csv` (one row per meeting; sections with a lab have two rows).
