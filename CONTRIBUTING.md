# Contributing

Thanks for helping trading-system developers trust their data. Fixes, new skills, better
checklists and corrections are all welcome.

## Ways to help

- **Fix a fact.** Vendors, exchanges and libraries change often (adjustment defaults, endpoints, calendars, file formats). If a rule, limit
  or header is out of date, open a PR with a link to the official source.
- **Improve a skill.** Each skill is a folder in `plugins/market-data/skills/`
  with a `SKILL.md` (YAML frontmatter `name` + `description`, then instructions).
- **Add a skill.** Same layout. Keep `SKILL.md` under 500 lines; put long
  reference material in a separate file linked from it.
- **Improve the scripts** in `corporate-actions/scripts`, `data-quality/scripts` and `bar-building/scripts`.
  They must stay standard-library only and keep their `--self-test` passing.

## Before you open a PR

```bash
python tests/validate_repo.py
python plugins/market-data/skills/corporate-actions/scripts/adjust_prices.py --self-test
python plugins/market-data/skills/data-quality/scripts/bar_check.py --self-test
python plugins/market-data/skills/bar-building/scripts/make_bars.py --self-test
```

Code samples must run as written and use sandbox or paper accounts only; never
real API keys, access tokens, webhook secrets or client IDs.

## Ground rules

- Accuracy over volume: cite official docs for platform facts.
- Regulatory content is engineering guidance, not legal or tax advice; cite the vendor's, exchange's or library's own documentation and the date you checked it.
- Never include real API keys, account numbers or personal data.
