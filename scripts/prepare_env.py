from pathlib import Path
import secrets
path = Path('.env')
if path.exists():
    content = path.read_text(encoding='utf-8-sig')
    if 'replace-with-a-long-random-secret' in content:
        path.write_text(content.replace('replace-with-a-long-random-secret', secrets.token_urlsafe(64)), encoding='utf-8')
        print('Generated the Django secret key; database settings preserved.')
    else:
        print('Existing environment preserved.')
else:
    print('Waiting for .env; no user settings changed.')
