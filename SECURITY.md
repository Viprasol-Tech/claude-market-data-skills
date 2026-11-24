# Security policy

## Reporting a vulnerability

Please report security problems privately through
[GitHub security advisories](https://github.com/Viprasol-Tech/claude-market-data-skills/security/advisories/new)
or by email to [support@viprasol.com](mailto:support@viprasol.com). Do not open a public issue.
We aim to reply within 3 working days.

## Scope

- The bundled scripts (`adjust_prices.py`, `bar_check.py`, `make_bars.py`) read
  local CSV files and print or write results. They make no network calls and
  run no shell commands. Wrong adjustments, missed data errors or mislabelled
  bars are in scope.
- Skill instructions that could lead an assistant to weaken account safety:
  mixing adjusted and raw prices in order logic, silent forward-filling, or
  ignoring data licences.

## Keep secrets out of chats

These skills never need your keys or funds. Never paste broker or exchange API keys,
data vendor API keys or tokens into an issue, pull request or
chat. Use synthetic data and sandbox keys. If a key has been
exposed, rotate it with your provider immediately.
