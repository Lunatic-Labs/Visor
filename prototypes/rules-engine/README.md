# Rules engine prototype (KAN-26, KAN-27)

A throwaway spike to prove the core checks before we pick a stack. It's pure Python with no web or database code.

- `find_conflicts`: flags any two sections whose meeting times overlap on a shared day. Back-to-back times are allowed.
- `missing_prereqs`: prerequisites stored as AND of OR-groups (see `specs/02-design-data-model.md`)

```
python demo.py          # sample CS schedule with a planted conflict
python -m pytest -q     # 6 tests, including edge cases
```
