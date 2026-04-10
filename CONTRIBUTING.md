# Contributing

Thanks for helping improve the Messaging and Calling Backend. This project is
most useful when code, tests, security notes, and documentation stay aligned.

## Read first

- [README.md](./README.md) for setup and usage
- [FEATURES.md](./FEATURES.md) for the current feature inventory and implementation schema
- [SECURITY.md](./SECURITY.md) before changing auth, messaging, calling, uploads, or privacy behavior
- [DEPLOYMENT.md](./DEPLOYMENT.md) for branch promotion and release operations

## Development setup

```bash
python -m venv .venv

# PowerShell
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn messaging_sdk.main:app --reload
```

Recommended local settings:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/messaging_db
SECRET_KEY=replace-this-with-a-long-random-secret-key
EMAIL_PROVIDER=console
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
DEBUG=false
```

## Working rules

1. Branch from `develop` using `feature/*`.
2. Make the smallest complete change that solves the problem.
3. Add or update tests in the same change.
4. Update documentation in the same change when behavior or usage changes.
5. Run `pytest` before opening a pull request.
6. Promote changes through `develop` -> `main`.

Required branch flow:

- push work only to `feature/*` branches
- open PRs from `feature/*` into `develop`
- open production PRs from `develop` into `main`

The repository includes a PR branch policy workflow that enforces this path.

## Documentation is required work

If you change a feature, documentation must be updated with it.

Use this rule of thumb:

- update [README.md](./README.md) when setup, configuration, extension points, or usage examples change
- update [FEATURES.md](./FEATURES.md) when a feature is added, removed, renamed, or its architecture changes
- update [SECURITY.md](./SECURITY.md) when risk, auth boundaries, privacy behavior, or deployment guidance changes
- update [DEPLOYMENT.md](./DEPLOYMENT.md) when release flow, hosting, install strategy, or promotion policy changes
- update [CHANGELOG.md](./CHANGELOG.md) when the change is user-facing or release-visible

If a pull request changes behavior and does not update docs, it is incomplete.

## Tests

Baseline command:

```bash
pytest
```

When adding behavior:

- add service tests first for business-rule-heavy changes
- add route tests when request validation, permissions, or auth boundaries matter
- add regression tests for bugs before or alongside the fix

## Coding expectations

- Prefer service-layer logic over large route-level conditionals
- Keep configuration explicit
- Preserve truthful security behavior and documentation
- Use type hints for new code
- Favor clear code over clever code

## Pull request checklist

Every pull request should clearly state:

- what changed
- why it changed
- how it was tested
- which docs were updated
- any remaining limitations or follow-up work

Conventional-style commit messages are encouraged:

```text
feat(email): add customizable template composer
fix(auth): reject reused verification tokens
docs(features): document call signaling flow
test(chat): cover unauthorized conversation reads
```

## Security-sensitive changes

Call these out clearly in the PR description if you touch:

- token creation or verification
- authentication or authorization
- WebSocket authentication
- file uploads or static file serving
- profile visibility or privacy behavior
- search visibility or data exposure

If you discover a flaw but are not fixing it immediately, record it in
[SECURITY.md](./SECURITY.md).
