# Repository Guidelines

## Project Structure & Module Organization

This workspace is currently an empty project scaffold. No application source, tests, assets, dependency manifests, or build configuration are present. The intended application stack has not yet been established.

When adding the initial implementation, group related code by feature or module and document the resulting layout in `README.md`. Use clearly named directories such as `src/`, `tests/`, and `assets/` only when they serve the chosen stack. Treat `.agents/`, `.codex/`, and `.aws/` as environment configuration directories, not application modules.

## Build, Test, and Development Commands

No build, test, lint, or local development commands are currently configured. Do not assume commands such as `npm test` or `make build` are available.

When introducing tooling, provide reproducible installation, development, build, and test commands in `README.md`. Commit the relevant manifests and lockfiles so contributors can reproduce the environment.

## Coding Style & Naming Conventions

No language-specific style or formatter is established. Follow the conventions of the language and framework selected for the initial implementation, and configure formatting and linting alongside it.

Use descriptive names, consistent indentation, and small modules with clear responsibilities. Avoid unrelated formatting changes in functional patches.

## Testing Guidelines

No testing framework or coverage threshold is configured. Add tests with new behavior and regression tests with bug fixes once executable code exists. Use descriptive test names that identify the behavior and expected result. Document the test location and exact execution command when introducing the test framework.

## Commit & Pull Request Guidelines

Git history is unavailable in this workspace, so no existing commit convention can be verified. Use concise, imperative commit subjects, such as `Add order validation`.

Pull requests should explain the change, its purpose, and validation performed. Link relevant issues when available; include screenshots for visible interface changes. Identify any setup steps or configuration changes reviewers need.

## Security & Configuration

Keep credentials, local environment files, and customer data out of source control. Document required configuration using examples with placeholder values.
