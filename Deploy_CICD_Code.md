# Agent 10 — Docker / Deploy / CI-CD: OWNED SOURCE CODE

Hand edits back as TEXT per HANDBACK_TEXT_PROTOCOL.md.

## `Dockerfile`

```dockerfile
# Backend image. Build the frontend separately (npm run build) and mount/copy
# frontend/dist, or extend this with a multi-stage Node build.
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY frontend/dist/ frontend/dist/
EXPOSE 8000
# run migrations then serve
CMD sh -c "cd backend && alembic upgrade head && cd .. && uvicorn backend.main:app --host 0.0.0.0 --port 8000"

```

## `docker-compose.yml`

```yaml
services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      DEPLOYMENT_MODE: server
      DATABASE_URL: postgresql+asyncpg://termaid:termaid@db:5432/termaid
      TERMAID_ROOT: /termaid-cli
      JWT_SECRET: ${JWT_SECRET:-change_me_in_prod}
      AI_PROVIDER: ${AI_PROVIDER:-}
      GEMINI_API_KEY: ${GEMINI_API_KEY:-}
    volumes:
      - ../termaid-complete-windows:/termaid-cli:ro
    depends_on:
      - db
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: termaid
      POSTGRES_PASSWORD: termaid
      POSTGRES_DB: termaid
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:

```

## `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:

jobs:
  backend:
    name: Backend · Python ${{ matrix.python }}
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
          cache: pip
      - name: Install deps
        run: |
          pip install -r backend/requirements.txt
          pip install pytest pytest-asyncio
      - name: Compile check
        run: python -m compileall backend
      - name: Run tests
        # policy + stream-parser tests need no external project;
        # test_api uses a fake engine, so the TermAId CLI is not required.
        run: pytest backend/tests -q

  frontend:
    name: Frontend · TypeScript
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - working-directory: frontend
        run: |
          npm install
          npm run build        # tsc (strict) + vite build
      - uses: actions/upload-artifact@v4
        with:
          name: frontend-dist
          path: frontend/dist

  rust-native:
    name: Rust · native scanner
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - uses: Swatinem/rust-cache@v2
        with:
          workspaces: native
      - working-directory: native
        run: |
          cargo fmt --check || true
          cargo clippy -- -D warnings || true
          cargo test --release
          cargo build --release

  rust-tauri:
    name: Rust · Tauri shell (check)
    runs-on: ubuntu-latest
    needs: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - uses: dtolnay/rust-toolchain@stable
      - uses: Swatinem/rust-cache@v2
        with:
          workspaces: desktop-mobile/src-tauri
      - name: Linux Tauri system deps
        run: |
          sudo apt-get update
          sudo apt-get install -y libwebkit2gtk-4.1-dev libappindicator3-dev \
            librsvg2-dev patchelf libgtk-3-dev
      - uses: actions/download-artifact@v4
        with:
          name: frontend-dist
          path: frontend/dist
      - working-directory: desktop-mobile/src-tauri
        run: cargo check

```

## `.github/workflows/release.yml`

```yaml
name: Release

# Tag a version to build native installers for every desktop OS.
#   git tag v2.0.0 && git push origin v2.0.0
on:
  push:
    tags: ["v*"]
  workflow_dispatch:

jobs:
  desktop:
    name: Desktop · ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: macos-latest      # universal Apple build
            args: "--target universal-apple-darwin"
          - os: ubuntu-latest
            args: ""
          - os: windows-latest
            args: ""
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - uses: dtolnay/rust-toolchain@stable
        with:
          targets: ${{ matrix.os == 'macos-latest' && 'aarch64-apple-darwin,x86_64-apple-darwin' || '' }}
      - uses: Swatinem/rust-cache@v2
        with:
          workspaces: desktop-mobile/src-tauri

      - name: Linux deps
        if: matrix.os == 'ubuntu-latest'
        run: |
          sudo apt-get update
          sudo apt-get install -y libwebkit2gtk-4.1-dev libappindicator3-dev \
            librsvg2-dev patchelf libgtk-3-dev

      - name: Install frontend deps
        working-directory: frontend
        run: npm install

      # --- OPTIONAL: bundle the local Python backend as a sidecar ---
      # Uncomment and provide the TermAId CLI (vendored or checked out) to ship
      # a fully self-contained local app. Without this, the build targets a
      # remote/standalone backend.
      #
      # - uses: actions/setup-python@v5
      #   with: { python-version: "3.12" }
      # - name: Build sidecar
      #   working-directory: backend
      #   env:
      #     TERMAID_ROOT: ${{ github.workspace }}/termaid-complete-windows
      #   run: |
      #     pip install -r requirements.txt pyinstaller
      #     pyinstaller termaid-backend.spec --noconfirm
      #     # rename to the Tauri externalBin target-triple convention:
      #     python ../scripts/name_sidecar.py

      - uses: tauri-apps/tauri-action@v0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          projectPath: desktop-mobile
          tagName: ${{ github.ref_name }}
          releaseName: "TermAId ${{ github.ref_name }}"
          releaseDraft: true
          args: ${{ matrix.args }}

  android:
    name: Mobile · Android
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - uses: dtolnay/rust-toolchain@stable
        with:
          targets: aarch64-linux-android,armv7-linux-androideabi,i686-linux-android,x86_64-linux-android
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: "17" }
      - name: Setup Android SDK/NDK
        uses: android-actions/setup-android@v3
      - working-directory: frontend
        run: npm install
      - working-directory: desktop-mobile
        run: |
          npm install
          npm run android:init
          npm run android:build
      - uses: actions/upload-artifact@v4
        with:
          name: android-apk
          path: desktop-mobile/src-tauri/gen/android/app/build/outputs/**/*.apk

  # iOS requires a macOS runner + Apple signing certs; left as a documented
  # template since it can't run without your Apple Developer credentials.
  #
  # ios:
  #   runs-on: macos-latest
  #   steps:
  #     - uses: actions/checkout@v4
  #     - ... setup node + rust (aarch64-apple-ios) + xcode ...
  #     - working-directory: desktop-mobile
  #       run: npm run ios:init && npm run ios:build

```

## `.github/workflows/release-bundled.yml`

```yaml
name: Release (bundled sidecar)

# Self-contained DESKTOP build: freezes the Python backend into the app so it
# runs fully on-device (local mode). Mobile stays remote-backend (no Python on
# phones) — see BUILD_LOCAL_APP.md.
#
# Provide the TermAId CLI source one of these ways (see scripts/fetch_cli.py):
#   • git submodule at vendor/termaid-cli
#   • repo variable TERMAID_CLI_TARBALL_URL (a .tar.gz)
#
# Trigger:  git tag v2.0.0 && git push origin v2.0.0   (or run manually)
on:
  push:
    tags: ["v*-bundled"]
  workflow_dispatch:

jobs:
  desktop-bundled:
    name: ${{ matrix.os }} (sidecar)
    strategy:
      fail-fast: false
      matrix:
        os: [macos-latest, ubuntu-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive          # picks up vendor/termaid-cli if a submodule

      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - uses: dtolnay/rust-toolchain@stable
        with:
          targets: ${{ matrix.os == 'macos-latest' && 'aarch64-apple-darwin,x86_64-apple-darwin' || '' }}
      - uses: Swatinem/rust-cache@v2
        with:
          workspaces: |
            desktop-mobile/src-tauri
            native

      - name: Linux deps
        if: matrix.os == 'ubuntu-latest'
        run: |
          sudo apt-get update
          sudo apt-get install -y libwebkit2gtk-4.1-dev libappindicator3-dev \
            librsvg2-dev patchelf libgtk-3-dev

      - name: Resolve TermAId CLI source
        env:
          TERMAID_CLI_TARBALL_URL: ${{ vars.TERMAID_CLI_TARBALL_URL }}
        run: python scripts/fetch_cli.py

      - name: Build backend sidecar (PyInstaller)
        run: |
          pip install -r backend/requirements.txt pyinstaller
          cd backend && pyinstaller termaid-backend.spec --noconfirm && cd ..
          python scripts/name_sidecar.py        # → desktop-mobile/src-tauri/binaries/<triple>

      - name: Install frontend deps
        working-directory: frontend
        run: npm install

      - uses: tauri-apps/tauri-action@v0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          projectPath: desktop-mobile
          tagName: ${{ github.ref_name }}
          releaseName: "TermAId ${{ github.ref_name }} (self-contained)"
          releaseDraft: true
          args: ${{ matrix.os == 'macos-latest' && '--target universal-apple-darwin' || '' }}

```
