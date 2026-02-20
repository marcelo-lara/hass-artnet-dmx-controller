# Release Instructions

This document describes the manual release process for the ArtNet DMX Controller integration.

1. Create a release branch from `main`:

```bash
git checkout -b release/v0.1
```

2. Update `CHANGELOG.md` and `manifest.json` with the new version.

3. Tag a pre-release if desired:

```bash
git tag -a v0.1.0-beta.1 -m "v0.1.0 beta"
git push origin v0.1.0-beta.1
```

4. Push branch and open a Pull Request for review.

5. After merge, tag the stable release and push tags:

```bash
git tag -a v0.1.0 -m "v0.1.0"
git push origin --tags
```

6. Optionally create a GitHub Release and attach the changelog notes.

7. If publishing to HACS, follow HACS documentation for adding releases and validating `hacs.json`.

---

Notes:
- Ensure `homeassistant` compatibility in `hacs.json` and `manifest.json` reflect the targeted HA release.
- Keep changes minimal per release; prefer one phase per PR.
