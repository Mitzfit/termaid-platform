# vendor/termaid-cli

Place (or submodule) your TermAId CLI project here so the bundled-sidecar build
can freeze it into the desktop app:

    git submodule add <your-termaid-cli-repo> vendor/termaid-cli

Expected layout: `vendor/termaid-cli/{termaid/,modules/}`.

Alternatively, set the repo variable `TERMAID_CLI_TARBALL_URL` to a `.tar.gz`
and CI will download it (see scripts/fetch_cli.py). This directory is otherwise
gitignored.
