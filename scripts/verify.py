"""Run repeatable checks and retain their actual output for the capstone report."""
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
output = root / '.local'
output.mkdir(exist_ok=True)
env = {**os.environ, 'PYTHONUTF8': '1'}
commands = [
    ('tests', ['manage.py', 'test', 'recruitment', '--noinput', '--verbosity', '2']),
    ('schema', ['manage.py', 'makemigrations', '--check', '--dry-run']),
    ('system', ['manage.py', 'check']),
]
if sys.argv[1:]:
    commands = [('regression', ['manage.py', 'test', *sys.argv[1:], '--noinput', '--verbosity', '2'])]
failed = False
for name, args in commands:
    print(f'Running {name} checks...', flush=True)
    result = subprocess.run([sys.executable, *args], cwd=root, env=env, text=True, encoding='utf-8', capture_output=True)
    (output / f'verification-{name}.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
    print(f'{name}: exit {result.returncode}', flush=True)
    print((result.stdout + result.stderr)[-3500:], flush=True)
    failed |= bool(result.returncode)
sys.exit(1 if failed else 0)
