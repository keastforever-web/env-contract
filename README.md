# env-contract

Catch missing environment configuration before starting a service. Compare a local `.env` against `.env.example`; report **key names and line numbers only**, never values or raw input lines. Python 3.10+, no runtime dependencies, no network calls.

```sh
python env_contract.py --example .env.example --env .env
python env_contract.py --strict --json
```

Optional installation: `python -m pip install .`, then run `env-contract`.

Every key listed in the example is required and must have a nonblank value in the actual file. Example values themselves are ignored. An example with no keys fails with `empty_contract`, preventing an accidentally blank template from silently passing. Duplicate keys and invalid lines in either file fail validation. Extra actual keys are allowed unless `--strict` is supplied. Exit codes: 0 success, 1 findings, 2 unreadable/non-UTF-8 input or invalid CLI arguments.

Example: an example file containing `DATABASE_URL=` and `PORT=` paired with an actual file containing only `PORT=3000` produces `env: missing DATABASE_URL` and exits 1.

## Supported format

For explicitly optional configuration, repeat `--optional KEY` (for example, `--optional METRICS_URL`). The key must exist in the example, otherwise the CLI exits 2 to catch typos. Optional keys may be absent or empty; malformed definitions and duplicates still fail. Required-key behavior is unchanged. Python callers can pass `optional=['METRICS_URL']` to `check`.

One `KEY=value` per line; ASCII identifier keys, optional `export`, UTF-8/BOM, blank lines, full-line comments, single/double quoted one-line values and trailing comments. Unquoted inline comments require whitespace before `#`. Quoted values must close on the same line. This intentionally checks a small dotenv subset; it does not source files, interpolate variables, evaluate shell commands, validate URLs/types, detect placeholders or inspect the process environment. Multiline values are unsupported and may produce multiple findings. Quoted backslashes are scanned only to find the closing quote, not decoded.

Input files stay local and are never modified. Key names may themselves reveal configuration details; review before sharing reports. Do not commit real `.env` files. A successful check confirms presence, not validity of credentials.

## CI integration

Run the check after your CI job has provisioned its temporary environment file:

```yaml
- name: Validate environment contract
  run: python env_contract.py --example .env.example --env .env.ci --strict --json
```

Keep `.env.ci` out of version control if it contains credentials. This command does not load secrets into the process or verify that credentials work. Findings exit 1 and stop a normal CI step; unreadable files or misspelled optional keys exit 2. An optional key must still be declared in `.env.example`:

```sh
python env_contract.py --example .env.example --env .env.ci --optional METRICS_URL
```

If validation reports `empty_contract`, restore the intended example keys rather than bypassing the failure. If it reports `invalid_line`, check the reported line locally; the report deliberately omits its contents. Multiline secrets must be supplied using another supported configuration mechanism because this checker accepts one-line assignments only.

```sh
python -m unittest -v
```

Tests cover required keys, empty values, extras, duplicate definitions, malformed quotes, UTF-8 BOM, safe reporting and CLI output. CI is configured for Windows/Linux and Python 3.10/3.13; remote results are not implied by configuration.

MIT licensed. Independently implemented after observing demand for security-oriented developer tooling on [GitHub Trending](https://github.com/trending), including [Cloudflare's security-audit-skill](https://github.com/cloudflare/security-audit-skill); no upstream source copied.

Planned maintenance: optional-key declarations, clearer dotenv compatibility and CI-friendly annotations without values.
