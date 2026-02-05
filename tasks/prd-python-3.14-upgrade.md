# PRD: Upgrade to Python 3.14

## Linear Tickets

| User Story | Ticket | Title |
|------------|--------|-------|
| Parent | [SRE-121](https://linear.app/linq/issue/SRE-121) | Upgrade Medic to Python 3.14 |
| US-001 | [SRE-122](https://linear.app/linq/issue/SRE-122) | Update CI workflow Python version |
| US-002 | [SRE-123](https://linear.app/linq/issue/SRE-123) | Update Dockerfile to Python 3.14 |
| US-003 | [SRE-124](https://linear.app/linq/issue/SRE-124) | Evaluate alternative Docker base images |
| US-004 | [SRE-125](https://linear.app/linq/issue/SRE-125) | Fix dependency compatibility issues |
| US-005 | [SRE-126](https://linear.app/linq/issue/SRE-126) | Fix deprecation warnings and compatibility issues |
| US-006 | [SRE-127](https://linear.app/linq/issue/SRE-127) | Update type hints for Python 3.14 |
| US-007 | [SRE-128](https://linear.app/linq/issue/SRE-128) | Leverage Python 3.14 features (optional) |
| US-008 | [SRE-129](https://linear.app/linq/issue/SRE-129) | Validate full test suite passes |
| US-009 | [SRE-130](https://linear.app/linq/issue/SRE-130) | QA validation and manual testing |
| US-010 | [SRE-131](https://linear.app/linq/issue/SRE-131) | Update monitoring and telemetry |
| US-011 | [SRE-132](https://linear.app/linq/issue/SRE-132) | Create runbook and documentation |
| US-012 | [SRE-133](https://linear.app/linq/issue/SRE-133) | Handoff and ownership confirmation |

**Commit Convention:** Include ticket ID in commit messages, e.g.:
```
SRE-122: Update CI workflow to Python 3.14
```

## Introduction

Upgrade medic from Python 3.11 to Python 3.14.3 (the latest stable release as of February 2026). This upgrade will improve performance, enable modern Python features like template string literals and deferred annotation evaluation, and ensure the project stays current with security patches and language improvements.

**Current State:**
- Python version: 3.11
- Dockerfile base: `python:3.11-slim-bookworm`
- CI workflow: `PYTHON_VERSION: "3.11"`
- Test count: 1304+ tests

**Target State:**
- Python version: 3.14.3
- Evaluate and select optimal base image (slim-bookworm, alpine, or distroless)
- All tests passing with no regressions

## Goals

- Upgrade all Python references from 3.11 to 3.14
- Fix any deprecation warnings or compatibility issues
- Leverage beneficial Python 3.14 features where appropriate
- Evaluate alternative Docker base images for size/security improvements
- Maintain 100% test pass rate (all 1304+ tests)
- No increase in Docker image size (or reduction if possible)

## User Stories

### US-001: Update CI workflow Python version [SRE-122]
**Description:** As a developer, I need CI to run on Python 3.14 so that tests validate against the target runtime.

**Acceptance Criteria:**
- [ ] Update `PYTHON_VERSION` in `.github/workflows/build.yml` from "3.11" to "3.14"
- [ ] Verify GitHub Actions `setup-python@v5` supports Python 3.14
- [ ] CI lint job passes with Python 3.14
- [ ] CI test job passes with Python 3.14
- [ ] Typecheck passes (mypy may need updates for 3.14 compatibility)

### US-002: Update Dockerfile to Python 3.14 [SRE-123]
**Description:** As a developer, I need the production Docker image to use Python 3.14 so that deployed code matches the CI environment.

**Acceptance Criteria:**
- [ ] Update builder stage FROM `python:3.11-slim-bookworm` to `python:3.14-slim-bookworm`
- [ ] Update runtime stage FROM `python:3.11-slim-bookworm` to `python:3.14-slim-bookworm`
- [ ] Docker image builds successfully on both amd64 and arm64
- [ ] Application starts and responds to health checks
- [ ] Document final image size in PR description

### US-003: Evaluate alternative Docker base images [SRE-124]
**Description:** As a developer, I want to evaluate alpine and distroless base images so that we can optimize for size and security.

**Acceptance Criteria:**
- [ ] Build and test with `python:3.14-alpine` base image
- [ ] Build and test with Google distroless Python image (if 3.14 available)
- [ ] Document size comparison: slim-bookworm vs alpine vs distroless
- [ ] Document any compatibility issues with each base
- [ ] Select optimal base image with justification in PR description
- [ ] If alpine/distroless selected: update Dockerfile accordingly

### US-004: Fix dependency compatibility issues [SRE-125]
**Description:** As a developer, I need all dependencies to be compatible with Python 3.14 so the application runs correctly.

**Acceptance Criteria:**
- [ ] Run `pip install -r Medic/requirements.txt` on Python 3.14 without errors
- [ ] Run `pip install -r requirements-dev.txt` on Python 3.14 without errors
- [ ] Update any dependencies that require newer versions for 3.14 support
- [ ] Verify psycopg2-binary builds/installs on Python 3.14
- [ ] Verify cryptography package builds/installs on Python 3.14
- [ ] Verify opentelemetry packages are compatible with Python 3.14
- [ ] Document any dependency version changes in PR description

### US-005: Fix deprecation warnings and compatibility issues [SRE-126]
**Description:** As a developer, I need to resolve any Python 3.14 deprecation warnings so the codebase is future-proof.

**Acceptance Criteria:**
- [ ] Run test suite with `-W error::DeprecationWarning` to surface warnings
- [ ] Fix any deprecated stdlib usage (check `asyncio`, `typing`, `collections` changes)
- [ ] Fix any syntax or semantic changes between 3.11 and 3.14
- [ ] Verify no `DeprecationWarning` in test output
- [ ] All 1304+ tests pass

### US-006: Update type hints for Python 3.14 [SRE-127]
**Description:** As a developer, I want to leverage Python 3.14's improved type hint features so the code is more maintainable.

**Acceptance Criteria:**
- [ ] Update mypy to version compatible with Python 3.14
- [ ] Review and update type stubs in requirements-dev.txt if needed
- [ ] Fix any new type errors surfaced by stricter checking
- [ ] Mypy passes with no errors
- [ ] Consider using PEP 649 deferred annotation evaluation where beneficial

### US-007: Leverage Python 3.14 features (optional improvements) [SRE-128]
**Description:** As a developer, I want to use beneficial Python 3.14 features where they improve code quality.

**Acceptance Criteria:**
- [ ] Review Python 3.14 "What's New" for applicable features
- [ ] Identify 2-3 places where new features could improve code (document in PR)
- [ ] Apply improvements only where they genuinely help readability/performance
- [ ] Do NOT refactor working code just to use new syntax
- [ ] All tests still pass after any changes

### US-008: Validate full test suite passes [SRE-129]
**Description:** As a developer, I need confirmation that all tests pass on Python 3.14 before merging.

**Acceptance Criteria:**
- [ ] All unit tests pass (pytest tests/)
- [ ] All integration tests pass
- [ ] Test coverage does not decrease
- [ ] No flaky tests introduced
- [ ] CI pipeline fully green on PR

## Functional Requirements

- FR-1: The application MUST run on Python 3.14.3 or later 3.14.x patch releases
- FR-2: The Docker image MUST build successfully for linux/amd64 and linux/arm64
- FR-3: All 1304+ existing tests MUST pass without modification to test logic (only fixes to application code)
- FR-4: The CI pipeline MUST complete successfully (lint, test, build, helm-lint)
- FR-5: The application MUST start and pass health checks in the container
- FR-6: Dependencies MUST be pinned to versions compatible with Python 3.14

## Non-Goals

- No new features or functionality beyond the Python upgrade
- No major refactoring of existing code (only compatibility fixes)
- No changes to application behavior or APIs
- No database migration changes
- No Kubernetes/Helm chart changes (unless required for compatibility)
- No upgrade to Python 3.15 (still in alpha)

## Technical Considerations

### Files Requiring Updates
1. `Dockerfile` - Base image version (lines 10, 39)
2. `.github/workflows/build.yml` - `PYTHON_VERSION` env var (line 24)
3. `Medic/requirements.txt` - Dependency version bumps if needed
4. `requirements-dev.txt` - Dev dependency version bumps if needed

### Known Python 3.12-3.14 Changes to Watch
- `typing` module changes (many things moved to `collections.abc`)
- `asyncio` API changes
- `importlib` changes
- Removed deprecated functions from stdlib
- f-string parsing changes
- Exception group handling (PEP 654)

### Dependency Compatibility Concerns
- `psycopg2-binary` - Usually quick to support new Python versions
- `cryptography` - May need Rust toolchain for building
- `opentelemetry-*` - Check instrumentation compatibility
- `flask` - Should be compatible (3.0+ is modern)

### Docker Base Image Comparison (to be validated)
| Base | Approx Size | Pros | Cons |
|------|-------------|------|------|
| slim-bookworm | ~150MB | Stable, glibc, easy debugging | Larger |
| alpine | ~50MB | Small, security-focused | musl libc issues, harder to debug |
| distroless | ~30MB | Minimal attack surface | No shell, harder to debug |

## Success Metrics

- All 1304+ tests pass on Python 3.14
- Docker image builds in under 5 minutes
- No increase in Docker image size (ideally decrease with alpine/distroless)
- Zero deprecation warnings in test output
- CI pipeline runs in similar time to current (< 10 min)

### US-009: QA validation and manual testing [SRE-130]
**Description:** As a QA engineer, I need to manually validate the Python upgrade so we can confirm no regressions in production behavior.

**Acceptance Criteria:**
- [ ] Manual test plan documented and executed
- [ ] Edge cases checked (startup, shutdown, error handling)
- [ ] Health check endpoints validated
- [ ] API responses verified against previous version
- [ ] QA signoff obtained

### US-010: Update monitoring and telemetry [SRE-131]
**Description:** As an SRE, I need monitoring updated to track the new Python version so we can detect issues post-deployment.

**Acceptance Criteria:**
- [ ] Python version exposed in metrics/telemetry
- [ ] Alerts reviewed and updated if needed
- [ ] Dashboard updated to show Python version
- [ ] Performance baseline established for Python 3.14

### US-011: Create runbook and documentation [SRE-132]
**Description:** As a support engineer, I need documentation for the Python 3.14 upgrade so I can troubleshoot issues.

**Acceptance Criteria:**
- [ ] Runbook created/updated with Python 3.14 specifics
- [ ] Known issues and mitigations documented
- [ ] Rollback procedure documented
- [ ] Support and ops teams notified of changes

### US-012: Handoff and ownership confirmation [SRE-133]
**Description:** As a team lead, I need clear handoff so all stakeholders know about the Python upgrade.

**Acceptance Criteria:**
- [ ] Clear ownership assigned for post-deployment support
- [ ] Ops team notified and briefed
- [ ] Change communicated to relevant stakeholders
- [ ] Post-deployment monitoring owner identified

## Open Questions

1. Is there a preferred base image (alpine vs distroless) based on team experience?
2. Are there any known issues with Python 3.14 in production EKS environments?
3. Should we add Python version to the application's `/health` or `/info` endpoint?

## References

- [Python 3.14 What's New](https://docs.python.org/3/whatsnew/3.14.html)
- [Python Version Status](https://devguide.python.org/versions/)
- [Python End of Life Dates](https://endoflife.date/python)
