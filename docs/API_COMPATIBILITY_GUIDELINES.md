# API Compatibility Guidelines

## Purpose

This document defines the minimum review process for API changes that can affect frontend behavior, external clients, saved automations, and contract tests.

The goal is to prevent accidental breaking changes before merge.

## Compatibility Rules

1. Do not remove existing response fields without an explicit migration plan.
2. Do not rename response fields in place. Add aliases first, deprecate later, then remove in a scheduled versioned change.
3. Do not narrow accepted input shapes without adding validation guidance and release notes.
4. Do not change semantic meaning of existing fields silently.
5. Prefer additive changes:
   - add optional fields
   - add new endpoints
   - add new enum values only when clients can safely ignore unknown values
6. Error payloads must keep stable envelopes and stable error codes.
7. If payload size or fallback behavior changes, update contract tests and examples in the same change.

## Change Classes

### Safe Additive

- Adding optional response fields
- Adding new endpoints
- Adding new filter parameters with backward-compatible defaults
- Expanding operator/debug metadata without changing core payload shape

### Review Required

- Changing required request fields
- Changing response field types
- Changing enum meaning or accepted values
- Reordering business-critical defaults
- Modifying error envelopes or error codes
- Changing pagination, sorting, or caching semantics

### Breaking

- Removing fields or endpoints
- Renaming fields without aliases
- Changing stable field type
- Returning different top-level envelope for an existing endpoint

Breaking changes require:

1. explicit approval
2. migration note
3. contract test updates
4. rollout timing

## Review Checklist

Every API-affecting change must answer:

1. Which endpoints changed?
2. Is the change additive, review-required, or breaking?
3. Which existing clients depend on the old shape?
4. Which contract tests were added or updated?
5. Is there an alias/deprecation window if shape changed?
6. Are examples, docs, and operator notes updated?

## Review Process

1. Classify the change as safe additive, review-required, or breaking.
2. Answer the full review checklist before merge.
3. Update or confirm the critical contract tests for the touched endpoints.
4. Update docs, examples, and operator-facing notes when behavior changes.
5. Confirm the rollout policy and deprecation window when compatibility risk exists.

## Required Review Artifacts

- updated or confirmed contract tests in `backend/tests/`
- operator-facing notes for non-obvious behavior changes
- stable error code coverage when error behavior changes
- example payloads for new response structures when useful

## Recommended Test Targets

- `backend/tests/test_api_contract_rankings.py`
- `backend/tests/test_search_api_validation_contract.py`
- `backend/tests/test_c96_creative_library_contract.py`
- endpoint-specific contract tests introduced by the change

## Rollout Policy

- Additive changes can merge after contract coverage is confirmed.
- Review-required changes must include a reviewer note referencing this guideline.
- Breaking changes must be scheduled and documented before release.

## Deprecation Policy

When an endpoint or response shape enters deprecation:

1. return `Deprecation: true`
2. return a concrete `Sunset` date
3. return a `Link` header pointing to successor docs or version info
4. publish the affected path, replacement, and migration note in an operator-visible registry
5. keep the compatibility window long enough for frontend and automation migration

Minimum deprecation registry fields:

- path
- replacement
- sunset_date
- migration_doc
- status
- note
