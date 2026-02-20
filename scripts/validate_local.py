#!/usr/bin/env python3
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
errors = []

# 1) Validate translations JSON files
for trans in root.glob('custom_components/**/translations/en.json'):
    try:
        data = json.loads(trans.read_text(encoding='utf-8'))
    except Exception as e:
        errors.append(f"Invalid JSON in {trans}: {e}")
        continue
    # Check for URLs in config.step.user.description
    cfg = data.get('config', {})
    step = cfg.get('step', {})
    user = step.get('user', {})
    desc = user.get('description') if isinstance(user, dict) else None
    if isinstance(desc, str) and ('http://' in desc or 'https://' in desc):
        errors.append(f"Translations {trans}: description contains URL; use placeholders instead")

# 2) Check services.yaml exists for integrations that register services
# simple heuristic: if __init__.py contains 'hass.services.async_register' then expect services.yaml
for init in root.glob('custom_components/*/__init__.py'):
    text = init.read_text(encoding='utf-8')
    if 'hass.services.async_register' in text:
        svc = init.parent / 'services.yaml'
        if not svc.exists():
            errors.append(f"Integration {init.parent.name} registers services but has no services.yaml at {svc}")

# 3) Validate hacs.json keys
hacs = root / 'hacs.json'
if hacs.exists():
    try:
        hj = json.loads(hacs.read_text(encoding='utf-8'))
        # Disallowed keys in HACS manifest for integration per validator
        disallowed = ['type', 'description', 'homeassistant_type']
        for k in disallowed:
            if k in hj:
                errors.append(f"hacs.json: disallowed key '{k}' present")
        if 'domains' not in hj and 'type' not in hj:
            errors.append("hacs.json: missing 'domains' key (e.g. ['light'])")
    except Exception as e:
        errors.append(f"Invalid JSON in hacs.json: {e}")
else:
    errors.append('hacs.json not found')

if errors:
    print('Validation FAILED:')
    for e in errors:
        print(' -', e)
    sys.exit(1)

print('Validation OK')
sys.exit(0)
