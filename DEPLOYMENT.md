# Deployment and Release Guide

This repository is set up to do two important things:

- distribute the SDK from GitHub instead of PyPI
- promote code through `feature/*` -> `develop` -> `main`

It also deploys the documentation website from `main` to GitHub Pages.

## Recommended hosting setup

Use GitHub Pages for the docs website.

Why this is the best fit right now:

- the site is already a static site under [`website/`](./website/README.md)
- deployment is simple and free for a public repository
- GitHub Pages supports your custom subdomain
- it keeps the docs deployment close to the release workflow

## What is already implemented

- [`.github/workflows/branch-policy.yml`](./.github/workflows/branch-policy.yml): rejects PRs that do not follow the promotion path
- [`.github/workflows/ci-release.yml`](./.github/workflows/ci-release.yml): runs tests on PRs and protected branches, updates `CHANGELOG.md` after `main` merges, refreshes draft release notes on `main`, and publishes GitHub releases from version tags
- [`.github/workflows/deploy-docs.yml`](./.github/workflows/deploy-docs.yml): deploys the `website/` folder to GitHub Pages on `main`
- [`website/CNAME`](./website/CNAME): sets the intended custom domain to `messagingandcallingbackend.credianlab.xyz`

## GitHub package install strategy

This project is intentionally documented for GitHub installs, not PyPI.

Install the latest `main` branch build:

```bash
pip install "git+https://github.com/ukemeikot/messaging-and-calling-backend.git@main#subdirectory=messaging_and_calling_backend"
```

Install a tagged release:

```bash
pip install "git+https://github.com/ukemeikot/messaging-and-calling-backend.git@v1.0.0#subdirectory=messaging_and_calling_backend"
```

Why `subdirectory=messaging_and_calling_backend` is required:

- the GitHub repository root contains the website and repo-level files
- the Python package metadata lives inside [`messaging_and_calling_backend/`](./)

## One-time GitHub setup

### 1. Create the long-lived branches

Create these branches in GitHub:

- `develop`
- `main`

### 2. Enable GitHub Pages

In GitHub:

1. Open `Settings`
2. Open `Pages`
3. Under `Build and deployment`, choose `GitHub Actions`

The workflow in [`.github/workflows/deploy-docs.yml`](./.github/workflows/deploy-docs.yml) will handle deployments after that.

### 3. Add the custom domain

The site artifact already includes [`website/CNAME`](./website/CNAME) with:

```text
messagingandcallingbackend.credianlab.xyz
```

In GitHub Pages settings:

1. Confirm the custom domain is `messagingandcallingbackend.credianlab.xyz`
2. Enable HTTPS once DNS is live

### 4. Add the DNS record

In your DNS provider for `credianlab.xyz`, create:

- Type: `CNAME`
- Name: `messagingandcallingbackend`
- Target: `ukemeikot.github.io`

### 5. Protect the promotion branches

In GitHub `Settings` -> `Branches`, create branch protection rules for:

#### `develop`

- require a pull request before merging
- require approvals
- require status checks before merging
- include:
  - `PR Branch Policy / Validate Pull Request Flow`
  - `CI and Release / Test Suite`
- disable direct pushes for everyone except admins if you need an emergency path

#### `main`

- require a pull request before merging
- require status checks before merging
- include:
  - `PR Branch Policy / Validate Pull Request Flow`
  - `CI and Release / Test Suite`
- disable direct pushes
- optionally require a higher approval count than `develop`
- allow GitHub Actions to bypass protection so the changelog workflow can commit `CHANGELOG.md` after a merge

## Daily developer flow

### Create a feature branch

Start from `develop`:

```bash
git checkout develop
git pull origin develop
git checkout -b feature/contacts-pagination
```

### Push your feature branch

```bash
git push -u origin feature/contacts-pagination
```

### Open the first PR

Open:

- `feature/contacts-pagination` -> `develop`

The PR branch policy workflow will reject the PR if the base branch is wrong.

### Promote to production

After the feature PR merges into `develop`, open:

- `develop` -> `main`

This is the only merge that should trigger:

- changelog updates
- release-draft updates
- website deployment

## Release checklist

Before merging `develop` into `main`:

1. Confirm all feature work already landed in `develop`
2. Confirm develop is ready for production
3. Confirm docs are updated
4. Confirm `pytest` passes locally
5. Merge `develop` into `main`

After the merge to `main`:

1. Watch the `CI and Release` workflow
2. Confirm `CHANGELOG.md` was updated by the workflow
3. Confirm the draft GitHub release was refreshed
4. Confirm the `Deploy Documentation Website` workflow succeeded
5. Open the deployed site at `https://messagingandcallingbackend.credianlab.xyz`

### Publish a versioned release

When you want a formal install target:

```bash
git checkout main
git pull origin main
git tag v1.0.0
git push origin v1.0.0
```

That tag will trigger the GitHub release publish step in
[`.github/workflows/ci-release.yml`](./.github/workflows/ci-release.yml).

Consumers can then install that version directly from GitHub:

```bash
pip install "git+https://github.com/ukemeikot/messaging-and-calling-backend.git@v1.0.0#subdirectory=messaging_and_calling_backend"
```

## Website deployment check guide

Use this after your first deployment:

1. Visit `https://messagingandcallingbackend.credianlab.xyz`
2. Confirm the home page loads without GitHub Pages 404 errors
3. Open `/docs.html`
4. Test at least one copy button
5. Confirm CSS and JS assets load correctly
6. Confirm the custom domain is marked as secure in GitHub Pages settings

## If something fails

- PR rejected: check the source and target branches match the required promotion path
- changelog did not update: confirm `main` allows GitHub Actions to bypass protection
- site did not deploy: confirm Pages is set to `GitHub Actions`
- custom domain does not resolve: confirm the DNS `CNAME` target is your GitHub Pages host
