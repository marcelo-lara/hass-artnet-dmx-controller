# Changelog

## Unreleased

- Implement Phase 4: centralized DMX write helper `DMXWriter` (batches writes and falls back to single-channel helpers).
- Refactor light entities to prefer the centralized DMX writer for bulk writes.
- Add unit tests for `DMXWriter` batching and fallback behavior.
