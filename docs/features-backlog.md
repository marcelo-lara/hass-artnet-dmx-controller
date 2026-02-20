# DMX Scene Creator Backlog (LLM-Assisted)

## Goal
Build a lightweight Home Assistant DMX scene creator focused on scene capture/apply/manage.

## Product Definition (Fixture Model)

- Each fixture is represented as a Home Assistant `Device` with internal entities (similar to ESPHome device/entity structure).
- New fixture setup must request:
  - `fixture_type` (model)
  - `start_channel` (initial DMX channel)
- Fixture channel metadata is sourced from a shared `fixture_mapping.json`.
- `fixture_mapping.json` is reused for every new fixture setup and is the single source of truth for fixture model channel descriptions.

### Acceptance Criteria

- Creating a fixture creates one HA device plus child entities derived from model channel mapping.
- Setup flow cannot complete without both `fixture_type` and `start_channel`.
- Channel/entity definitions are loaded from `fixture_mapping.json` for the selected model.
- Adding a new fixture model requires only updating `fixture_mapping.json` (no per-model hardcoded channel definitions in setup logic).
- Channels marked `hidden_by_default: true` are created disabled/hidden in HA UI (initially `reset` and `program`).

### Distinct Fixtures Extracted from `docs/fixtures.json`

- `mini_beam_prism_l` + `mini_beam_prism_r` -> `mini_beam_prism`
- `head_el150` -> `head_el150`
- `parcan_l` -> `parcan` (5-channel RGB + strobe)
- `parcan_pl` + `parcan_pr` + `parcan_r` -> `proton` (6-channel RGB + strobe + program)

### Fixture Specie Convention

- Add `fixture_specie` to each fixture model in `fixture_mapping.json`.
- Initial species:
  - `moving_head` for moving fixtures (`mini_beam_prism`, `head_el150`)
  - `parcan` for RGB wash fixtures (`parcan`, `proton`)
- Use `fixture_specie` to drive default entity creation and channel behavior interpretation later (position channels, wheel channels, RGB channels, etc.).

## Implementation Plan (VSCode Copilot / GPT-5-mini Friendly)

### Phase 0 — Baseline + Scope Lock
- Confirm `fixture_mapping.json` is the single source of truth.
- Freeze mapping schema fields:
  - `fixture_specie`
  - `channel_count`
  - `channels[].name`
  - `channels[].offset`
  - `channels[].description`
  - `channels[].value_map` (optional)
- Document fixture type normalization rules.
- Test:
  - Manual schema review with `mini_beam_prism` and `parcan`.
- Exit criteria:
  - Mapping spec documented in `docs/`.

### Phase 1 — Mapping Loader + Validation
- Add `fixture_mapping.py` loader in `custom_components/artnet_dmx_controller/`.
- Load and validate JSON strictly with clear, actionable errors.
- Cache parsed mapping in integration runtime.
- Tests:
  - Valid mapping loads.
  - Missing file fails with clear error.
  - Malformed JSON fails with clear error.
  - Missing required keys fails with clear error.
- Exit criteria:
  - Loader returns validated structure and all error paths are handled.
  - Status: Done (validation tests added; cache helper added)

### Phase 2 — Config Flow Inputs for Fixture Creation
- Extend config flow to request:
  - `fixture_type`
  - `start_channel`
  - optional `name`
- Populate fixture types from mapping (no hardcoded list).
- Validate:
  - DMX bounds (`start + channel_count - 1 <= 512`)
  - Channel overlap against existing fixtures
- Tests:
  - Happy path fixture creation.
  - Invalid channel rejected.
  - Overlap rejected.
  - Unknown fixture type rejected.
- Exit criteria:
  - Setup cannot complete without `fixture_type` and `start_channel`.

### Phase 3 — Device + Entity Modeling
- Implement one HA device per fixture instance.
- Create child entities from mapped channels.
- For channels with `value_map` (color/gobo), expose discrete selectable options.
- For channels with `hidden_by_default: true`, create entities as disabled by default in entity registry.
- Tests:
  - `mini_beam_prism` creates expected entities.
  - `head_el150` wheel channels expose discrete options.
  - `parcan` and `proton` map expected RGB/strobe/program channels.
  - `reset` and `program` entities are hidden by default in HA UI.
- Exit criteria:
  - Device/entity structure matches product definition.

### Phase 4 — DMX Runtime Write Path
- Map entity updates to absolute DMX channels using `start_channel + offset - 1`.
- Keep all offset/value transformation in one central module.
- Enforce value range guards (`0..255`).
- Tests:
  - Manual DMX verification for dimmer, RGB, color wheel, gobo wheel.
  - Confirm expected channel/value pairs are emitted.
- Exit criteria:
  - DMX output is consistent with mapping and fixture config.

### Phase 5 — Persistence + Restart Reliability
- Persist fixture instances in Config Entries (and integration storage only if required).
- Recreate devices/entities after restart without duplication.
- Ensure stable unique IDs per fixture + channel entity.
- Tests:
  - Create fixtures, restart HA, confirm recovery and no duplicates.
- Exit criteria:
  - Fixtures survive restart with stable IDs and state path.

### Phase 6 — Manual Publish Pipeline (No CI)
- Use release branch strategy:
  - `release/v0.x`
- Publish prerelease tags first:
  - `v0.x.0-beta.1`, `v0.x.0-beta.2`, ...
- Promote to stable tag:
  - `v0.x.0`
- Maintain:
  - `CHANGELOG.md` with install/upgrade notes.
  - `README.md` section: "Try from GitHub".
- Tests (manual on clean HA instance):
  - Install from GitHub tag (HACS custom repo or manual copy).
  - Configure one moving head + one parcan fixture.
  - Run smoke checklist.
- Exit criteria:
  - Reproducible install and first fixture setup in <15 minutes.

### Phase 7 — Publish + Feedback Loop
- Release beta notes with known limitations.
- Collect tester feedback via GitHub issues template.
- Patch quickly on release branch and retag beta if needed.
- Promote to stable only after repeated passing smoke runs and no blockers.
- Exit criteria:
  - Stable release with no open blocker issues.

### Copilot Execution Rules
- Keep one phase per PR.
- Do not mix feature work with refactors in same PR.
- Add/update `TESTING.md` manual checklist each phase.
- Use short phase prompts with deterministic acceptance criteria.

### Phase 1
- Capture current fixture/channel states into a named scene
- Save/reuse/apply scenes with optional transitions
- Minimal UI for day-to-day scene usage
- Automation-ready services and blueprints

### Phase 2
- Full live DMX desk/controller
- Real-time joystick/canvas pan-tilt editor
- Advanced procedural effect engine (for MVP)

---

## Current Status Snapshot

### Implemented
### Implemented
- Custom integration scaffold: `custom_components/artnet_dmx_controller/`
- Services (registered under the integration domain `artnet_dmx_controller`): `record_scene`, `play_scene`, `list_scenes`, `delete_scene`
- Storage-backed scene repository (internal `scene` subpackage)
- Integration config entries and options are managed via the config flow (no YAML required)

### Needs Verification First
- Restart Home Assistant and confirm services are registered
- Validate service behavior from Developer Tools
- Confirm default DMX entity discovery matches your naming conventions

### Known Environment Constraint
- Local shell currently has no `python`/`python3` for compile checks in this workspace session

---

## Architecture Baseline

### Integration Type
- HACS-style custom integration (not Supervisor add-on)

### Data Model (MVP)
- Scene object:
  - `name`
  - `created_at`
  - `entities` map (`entity_id` -> payload)
- Entity payload:
  - `state` (`on`/`off`)
  - optional light attributes (`brightness`, `rgb_color`, etc.)

### Storage
- Home Assistant `Store` (`.storage` managed by integration)
- Versioned storage schema for forward migration
- Fixture metadata source: `custom_components/artnet_dmx_controller/fixture_mapping.json`

---

## Phase Plan with Deliverables

## Phase 1 — Stabilize MVP Engine
### Deliverables
- Service schemas hardened (input validation + clear errors)
- Deterministic scene overwrite behavior (`record_scene` same name)
- Better list output format (`count`, `names`, metadata)
- Basic diagnostics logging for record/play/delete

### Acceptance
- Record -> Play -> Delete succeeds for all fixture families:
  - `head_*`
  - `mini_beam_*`
  - `parcan_*`
  - `proton_*`

## Phase 2 — Minimal Scene UX
### Deliverables
- Lovelace section for scene management:
  - Scene name input helper
  - Capture button
  - Apply button
  - Delete button
  - Scene selector helper
- Optional script wrappers for one-click actions

### Acceptance
- No YAML edits needed for daily use
- Scene lifecycle usable by non-technical user from dashboard

## Phase 3 — Groups + Transitions
### Deliverables
- Logical fixture groups (helpers or group entities)
- Apply by group/subset
- Transition defaults per scene
- Graceful partial-availability handling

### Acceptance
- Applying scene to subset works without side effects
- Transition behavior is consistent and predictable

## Phase 4 — Preset/POI Helpers
### Deliverables
- Service(s) to store/reuse POI-aligned pan/tilt snapshots
- Preset abstraction for moving heads (from `fixtures.json`)
- Safe "arm" defaults for applicable fixtures

### Acceptance
- Can recall motion-oriented scenes without channel math

## Phase 5 — Automation + Reliability
### Deliverables
- Blueprints for common triggers (time, presence, button, media)
- Idempotent apply semantics
- Retry/backoff policy for transient send failures
- Action logbook/event entries

### Acceptance
- Stable behavior in automations over several days

## Phase 6 — Packaging + Handover
### Deliverables
- HACS repo readiness (`hacs.json`, docs, release notes)
- Migration notes for storage schema changes
- Backup/restore guidance

### Acceptance
- Fresh install to first scene in <30 minutes

---

## LLM Session Workflow (Use Every Time)

1. Read current files first:
  - `custom_components/artnet_dmx_controller/__init__.py`
  - `custom_components/artnet_dmx_controller/scene/scene_store.py`
  - `custom_components/artnet_dmx_controller/scene/services.yaml`
  - `configuration.yaml`
2. State assumptions explicitly before coding
3. Make smallest viable patch
4. Validate with HA checks/restart logs when possible
5. Update this backlog status after each session

---

## Resume Checklist (Next Session)

- [ ] Restart Home Assistant
- [ ] Verify `artnet_dmx_controller.*` services appear in Developer Tools
- [ ] Test `record_scene` with a known scene name
- [ ] Test `play_scene` with and without transition
- [ ] Test `delete_scene` and confirm removal via `list_scenes`
- [ ] Log any entity compatibility mismatches

---

## Ready-to-Paste Prompts for LLM Coding

### Prompt A — MVP Validation Hardening
"Read `custom_components/artnet_dmx_controller/*` and improve service validation/errors only. Do not add new features. Add clear HomeAssistantError messages and keep patches minimal."

### Prompt B — Minimal Lovelace UX
"Create a minimal dashboard workflow for DMX scenes using helpers/scripts (no custom frontend card). Add only what is required for `record_scene`/`play_scene`/`delete_scene` from UI."

### Prompt C — Grouped Apply
"Add support to play scenes to an optional subset/group of entities while preserving existing default behavior. Include service schema updates and docs."

### Prompt D — HACS Readiness
"Prepare `artnet_dmx_controller` for external HACS repository: add `hacs.json`, tighten manifest metadata, and update README install instructions."

---

## Definition of Done (Per Phase)

- Code merged in `custom_components/artnet_dmx_controller/`
- Services visible and callable in HA Developer Tools
- One happy-path test and one failure-path test executed manually
- Backlog updated with what changed, what failed, and next action

---

## Risks & Mitigations

- **Risk:** Entity naming drift breaks default DMX discovery
  - **Mitigation:** Add configurable include patterns or explicit entity list
- **Risk:** Attribute mismatch across light platforms
  - **Mitigation:** Record/play only supported attributes per entity state
- **Risk:** UI complexity creep toward full controller
  - **Mitigation:** Enforce strict in-scope/out-of-scope checklist before each phase

---

## MVP Lock (Do Not Expand Before Done)

Must have:
- Capture scene
- Apply scene
- Delete scene
- List scenes
- Minimal UI flow

Must not add yet:
- Live pan/tilt joystick UI
- Procedural effects engine
- Full desk-like control surface

---

## Tomorrow Plan (Session Handoff)

### Primary Objective
Complete Phase 1 verification and hardening so the MVP scene engine is stable before building UI.

### Step-by-Step (In Order)
1. Restart Home Assistant and confirm `artnet_dmx_controller` integration loads without errors.
2. In Developer Tools, run:
  - `artnet_dmx_controller.list_scenes`
  - `artnet_dmx_controller.record_scene` (entry_id: `<entry_id>`, name: `test_scene`)
  - `artnet_dmx_controller.play_scene` (entry_id: `<entry_id>`, name: `test_scene`, transition: `1`)
  - `artnet_dmx_controller.delete_scene` (name: `test_scene`)
3. Record actual results and any error text in this file.
4. Harden validation/errors only (no new features):
  - clearer messages for missing entities/empty captures
  - safer handling for unsupported attributes
  - improve `list` response to include `count`
5. Re-run the same service test flow and confirm fixes.

### Tomorrow Deliverables
- [ ] Services verified end-to-end in Home Assistant
- [ ] At least 1 validation/error improvement merged
- [ ] `list` response includes `count` and names
- [ ] This backlog updated with outcomes and next action

### If Time Remains
- Start Phase 2 with a minimal UI workflow using helpers + scripts only
-- Keep scope to record/play/delete from dashboard (no custom card)

### Session Start Prompt (Copy/Paste)
"Continue Phase 1 in `custom_components/artnet_dmx_controller`. First verify services in Home Assistant from the existing checklist, then implement only validation/list-response hardening. Keep patches minimal and update `features-backlog.md` with test outcomes."
