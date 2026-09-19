#!/bin/sh
set -eu

APP_SOURCE="${1:-}"
if [ -z "$APP_SOURCE" ] || [ ! -f "$APP_SOURCE/VERSION" ] || [ ! -f "$APP_SOURCE/RELEASE_FILES.txt" ]; then
  echo "End of the World Bot setup could not find the installed release files." >&2
  exit 1
fi

VERSION="$(tr -d '[:space:]' < "$APP_SOURCE/VERSION")"
DEST="$HOME/.local/share/end-of-world-bot/$VERSION"
CURRENT="$HOME/.local/share/end-of-world-bot/current"

printf '\nEnd of the World Bot - Windows/WSL setup\n'
printf 'Release: %s\n\n' "$VERSION"

need_packages=0
command -v python3 >/dev/null 2>&1 || need_packages=1
command -v pdftotext >/dev/null 2>&1 || need_packages=1

if command -v python3 >/dev/null 2>&1; then
  if ! python3 - <<'PY'
import sqlite3
db = sqlite3.connect(":memory:")
db.execute("CREATE VIRTUAL TABLE probe USING fts5(text)")
db.close()
PY
  then
    need_packages=1
  fi
fi

if [ "$need_packages" -eq 1 ]; then
  printf 'Linux prerequisites are missing.\n'
  printf 'Installing them uses your Internet connection and may ask for your Linux password.\n'
  printf 'Install Python, SQLite/FTS5, and Poppler now? [y/N] '
  IFS= read -r answer || answer=
  case "$answer" in
    y|Y|yes|YES|Yes)
      sudo apt-get update
      sudo apt-get install -y python3 python3-venv python3-pip poppler-utils
      ;;
    *)
      echo "Setup stopped without changing Linux packages."
      exit 2
      ;;
  esac
fi

if ! python3 - <<'PY'
import sqlite3
db = sqlite3.connect(":memory:")
db.execute("CREATE VIRTUAL TABLE probe USING fts5(text)")
db.close()
PY
then
  echo "Python SQLite FTS5 support is still unavailable." >&2
  exit 1
fi

if [ -e "$DEST" ]; then
  echo "Release $VERSION is already installed in WSL:"
  echo "  $DEST"
else
  mkdir -p "$DEST"
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    src="$APP_SOURCE/$name"
    dst="$DEST/$name"
    [ -f "$src" ] || { echo "Missing packaged file: $name" >&2; exit 1; }
    mkdir -p "$(dirname "$dst")"
    cp -p -- "$src" "$dst"
  done < "$APP_SOURCE/RELEASE_FILES.txt"
fi

mkdir -p "$DEST/library/guides"
mkdir -p "$(dirname "$CURRENT")"
rm -f "$CURRENT"
ln -s "$DEST" "$CURRENT"

printf '\nRunning self-check...\n'
(
  cd "$DEST"
  sh launch.sh doctor
)

cat <<EOF

Setup complete.

The full Bot runs inside WSL, not as a native Windows program.
Your Linux installation is:
  $DEST

Put documents in:
  $DEST/library/guides

Useful commands:
  cd "$DEST"
  sh launch.sh index
  sh launch.sh search "your question"

You can rerun the Windows Setup Assistant at any time to repair/check the install.
EOF
