"""Check a simple dotenv contract without revealing values. Python 3.10+."""
import argparse
import json
import re
from pathlib import Path

ASSIGNMENT = re.compile(r'^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$')


def parse(text):
    keys, findings = {}, []
    for number, raw in enumerate(text.lstrip('\ufeff').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        match = ASSIGNMENT.fullmatch(line)
        if not match:
            findings.append({'kind': 'invalid_line', 'line': number})
            continue
        key, value = match.groups()
        raw_value = value
        value = value.strip()
        if key in keys:
            findings.append({'kind': 'duplicate', 'key': key, 'line': number})
        if value.startswith(('"', "'")):
            quote = value[0]
            # Deliberately support one-line values only; never evaluate expansions.
            closing = None
            escaped = False
            for i, char in enumerate(value[1:], 1):
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == quote:
                    closing = i
                    break
            if closing is None or (value[closing + 1:].strip() and not value[closing + 1:].strip().startswith('#')):
                findings.append({'kind': 'invalid_value', 'key': key, 'line': number})
                keys[key] = False
                continue
            nonempty = bool(value[1:closing].strip())
        else:
            nonempty = bool(re.split(r'\s+#', raw_value, maxsplit=1)[0].strip())
        keys[key] = nonempty
    return keys, findings


def check(example, actual, strict=False, optional=None):
    expected, template_findings = parse(example)
    present, actual_findings = parse(actual)
    optional = set(optional or [])
    if optional - expected.keys():
        raise ValueError('optional keys must exist in the example')
    findings = [dict(item, source='example') for item in template_findings]
    if not expected:
        findings.append({'kind': 'empty_contract', 'source': 'example'})
    findings += [dict(item, source='env') for item in actual_findings]
    for key in sorted(expected):
        if key in optional:
            continue
        if key not in present:
            findings.append({'kind': 'missing', 'key': key, 'source': 'env'})
        elif not present[key]:
            findings.append({'kind': 'empty', 'key': key, 'source': 'env'})
    if strict:
        findings += [{'kind': 'extra', 'key': key, 'source': 'env'} for key in sorted(present.keys() - expected.keys())]
    return {'ok': not findings, 'expected_keys': len(expected), 'actual_keys': len(present), 'findings': findings}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--example', default='.env.example')
    parser.add_argument('--env', default='.env')
    parser.add_argument('--strict', action='store_true', help='also reject keys absent from the example')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--optional', action='append', default=[], metavar='KEY',
                        help='allow an example key to be missing or empty; repeatable')
    args = parser.parse_args(argv)
    try:
        result = check(Path(args.example).read_text(encoding='utf-8-sig'), Path(args.env).read_text(encoding='utf-8-sig'), args.strict, args.optional)
    except (OSError, UnicodeError):
        # Do not include exception text: it can include private paths or file bytes.
        parser.exit(2, 'env-contract: could not read input files as UTF-8\n')
    except ValueError:
        parser.exit(2, 'env-contract: optional keys must exist in the example\n')
    if args.json:
        print(json.dumps(result))
    else:
        print('env-contract: ' + ('OK' if result['ok'] else 'CHECK FAILED'))
        for finding in result['findings']:
            print(f"{finding['source']}: {finding['kind']}" + (f" {finding['key']}" if 'key' in finding else '') + (f" (line {finding['line']})" if 'line' in finding else ''))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
