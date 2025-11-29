# Release Guide

This document provides detailed guidelines for creating releases of the Greek Alphabet Mastery application.

## Version Numbering

This project follows **Semantic Versioning 2.0.0** (https://semver.org/)

### Format: MAJOR.MINOR.PATCH

```
1.0.0
│ │ │
│ │ └─ PATCH: Bug fixes, backwards-compatible
│ └─── MINOR: New features, backwards-compatible
└───── MAJOR: Breaking changes, incompatible API changes
```

**IMPORTANT**: Never use a 'v' prefix in version numbers!
- ✅ Correct: `1.0.0`, `2.3.4`, `1.0.0-beta.1`
- ❌ Wrong: `v1.0.0`, `v2.3.4`, `v1.0.0-beta.1`

## When to Increment Versions

### MAJOR version (X.0.0)
Increment when making incompatible changes:
- Database schema changes that require migration
- API endpoint removals or signature changes
- Changing cookie format or authentication mechanism
- Removing or renaming configuration options
- Breaking changes to quiz algorithm that affect user experience

**Examples:**
- `1.5.3` → `2.0.0`: Remove old API endpoints
- `2.4.1` → `3.0.0`: Change database schema incompatibly

### MINOR version (0.X.0)
Increment when adding functionality in a backwards-compatible manner:
- New quiz features or question types
- New API endpoints
- New configuration options (with defaults)
- Enhanced UI features
- Performance improvements without breaking changes
- New database tables (without changing existing ones)

**Examples:**
- `1.0.0` → `1.1.0`: Add pronunciation hints feature
- `1.1.0` → `1.2.0`: Add user achievement system
- `1.2.0` → `1.3.0`: Add quiz themes

### PATCH version (0.0.X)
Increment when making backwards-compatible bug fixes:
- UI bug fixes
- Quiz logic corrections
- Security patches
- Performance optimizations
- Documentation updates
- Dependency updates (non-breaking)

**Examples:**
- `1.0.0` → `1.0.1`: Fix quiz completion bug
- `1.0.1` → `1.0.2`: Fix progress bar display issue
- `1.0.2` → `1.0.3`: Update dependencies for security

## Pre-release Versions

For testing before official release:

### Alpha (early development)
```
1.0.0-alpha.1
1.0.0-alpha.2
```
- Major features incomplete
- Known bugs expected
- Internal testing only

### Beta (feature complete)
```
1.0.0-beta.1
1.0.0-beta.2
```
- All features implemented
- Testing and bug fixing phase
- Limited external testing

### Release Candidate (almost ready)
```
1.0.0-rc.1
1.0.0-rc.2
```
- All tests passing
- Final testing before release
- No new features, only critical fixes

## Release Workflow

### Step-by-Step Process

#### 1. Prepare the Release

```bash
# Ensure you're on main branch with latest changes
git checkout main
git pull origin main

# Run all tests
pytest

# Verify Docker build works
docker build -t greek-alphabet-mastery-test .

# Test the application
docker run -p 8000:8000 greek-alphabet-mastery-test
# Open http://localhost:8000 and test functionality
```

#### 2. Update Version Documentation

Before tagging, update these files:
- [ ] `CHANGELOG.md` - Add entry for new version
- [ ] `README.md` - Update version references if needed
- [ ] Any version strings in code (if applicable)

#### 3. Commit Changes

```bash
git add .
git commit -m "Prepare for release 1.0.0"
git push origin main
```

#### 4. Create Git Tag

**REMEMBER: No 'v' prefix!**

```bash
# Create annotated tag (recommended)
git tag -a 1.0.0 -m "Release 1.0.0"

# Push tag to GitHub
git push origin 1.0.0
```

#### 5. Create GitHub Release

1. Go to your repository on GitHub
2. Click "Releases" → "Create a new release"
3. Select the tag you just created (e.g., `1.0.0`)
4. Fill in release details:
   - **Release title**: Version number (e.g., `1.0.0`)
   - **Description**: Use the template below

#### 6. Monitor GitHub Actions

- GitHub Actions will automatically build and publish the Docker image
- Check the "Actions" tab to monitor progress
- Verify the build completes successfully

#### 7. Verify Published Image

```bash
# Pull the new image
docker pull ghcr.io/jaycollett/koinegreekalphabet:1.0.0

# Test it
docker run -p 8000:8000 ghcr.io/jaycollett/koinegreekalphabet:1.0.0
```

## Release Notes Template

Use this template for GitHub Release descriptions:

```markdown
## What's New in 1.0.0

### Features
- Added quiz resume functionality on page refresh
- Implemented dark theme with subtle answer feedback
- Added exit/home button with confirmation dialog

### Bug Fixes
- Fixed quiz completion not triggering after 14 questions
- Fixed Greek letter display color inconsistency

### Improvements
- Optimized database queries for better performance
- Enhanced mobile responsiveness

### Breaking Changes
- None (for MINOR/PATCH versions)
- List any breaking changes here (for MAJOR versions)

### Docker Images
```bash
docker pull ghcr.io/jaycollett/koinegreekalphabet:1.0.0
docker pull ghcr.io/jaycollett/koinegreekalphabet:latest
```

### Full Changelog
See CHANGELOG.md for complete details.
```

## Common Scenarios

### Scenario 1: Bug Fix Release
Current version: `1.2.3`

You fixed a quiz display bug. This is a PATCH release:

```bash
git tag -a 1.2.4 -m "Release 1.2.4 - Fix quiz display bug"
git push origin 1.2.4
```

### Scenario 2: New Feature Release
Current version: `1.2.4`

You added a new quiz mode. This is a MINOR release:

```bash
git tag -a 1.3.0 -m "Release 1.3.0 - Add timed quiz mode"
git push origin 1.3.0
```

### Scenario 3: Breaking Change Release
Current version: `1.3.0`

You changed the database schema. This is a MAJOR release:

```bash
git tag -a 2.0.0 -m "Release 2.0.0 - New database schema"
git push origin 2.0.0
```

### Scenario 4: Beta Release
Current version: `1.3.0`

You're testing new features before official release:

```bash
git tag -a 1.4.0-beta.1 -m "Release 1.4.0-beta.1 - Beta test for new features"
git push origin 1.4.0-beta.1
```

## Rollback Procedure

If a release has critical issues:

### Option 1: Quick Fix (Recommended)
Create a patch release with the fix:

```bash
# Fix the bug
git commit -m "Fix critical bug in 1.3.1"
git push origin main

# Create patch release
git tag -a 1.3.2 -m "Release 1.3.2 - Fix critical bug"
git push origin 1.3.2
```

### Option 2: Rollback to Previous Version
Use previous Docker image:

```bash
# Pull previous working version
docker pull ghcr.io/jaycollett/koinegreekalphabet:1.3.0

# Run it
docker run -p 8000:8000 ghcr.io/jaycollett/koinegreekalphabet:1.3.0
```

## Version History Example

```
2.0.0 - 2024-03-01 - Major: New user profile system
1.3.2 - 2024-02-28 - Patch: Fix quiz completion bug
1.3.1 - 2024-02-25 - Patch: Update dependencies
1.3.0 - 2024-02-20 - Minor: Add timed quiz mode
1.2.0 - 2024-02-10 - Minor: Add achievement system
1.1.0 - 2024-02-01 - Minor: Add quiz themes
1.0.1 - 2024-01-25 - Patch: Fix display issue
1.0.0 - 2024-01-20 - Major: Initial release
```

## Checklist for Every Release

Use this checklist before creating any release:

- [ ] All tests passing (`pytest`)
- [ ] Docker build successful
- [ ] Application tested locally
- [ ] CHANGELOG.md updated
- [ ] Version number follows semantic versioning
- [ ] No 'v' prefix in version number
- [ ] All changes committed and pushed to main
- [ ] Git tag created and pushed
- [ ] GitHub Release created with proper description
- [ ] GitHub Actions build completed successfully
- [ ] Published Docker image tested

## Automated CI/CD

The GitHub Actions workflow (`.github/workflows/docker-publish.yml`) automatically:

1. Validates semantic versioning format
2. Builds Docker image
3. Publishes to GitHub Container Registry
4. Creates multiple tags:
   - Exact version: `1.2.3`
   - Minor version: `1.2`
   - Major version: `1` (for versions ≥ 1.0.0)
   - Latest: `latest` (for releases on main branch)

## Questions?

If you're unsure which version to use:
- Ask: "Does this break existing functionality?" → MAJOR
- Ask: "Does this add new functionality?" → MINOR
- Ask: "Does this only fix bugs?" → PATCH

When in doubt, consult https://semver.org/
