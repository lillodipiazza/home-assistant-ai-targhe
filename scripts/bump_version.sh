#!/bin/bash
# Script per incrementare la versione dell'addon AI Targhe
# Uso: ./scripts/bump_version.sh [major|minor|patch]
#
# Esempio:
#   ./scripts/bump_version.sh patch   -> 1.0.1 => 1.0.2
#   ./scripts/bump_version.sh minor   -> 1.0.1 => 1.1.0
#   ./scripts/bump_version.sh major   -> 1.0.1 => 2.0.0

set -e

BUMP_TYPE="${1:-patch}"
CONFIG_FILE="ai_targhe/config.yaml"
CHANGELOG_FILE="ai_targhe/CHANGELOG.md"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Errore: $CONFIG_FILE non trovato. Esegui lo script dalla root del repository."
    exit 1
fi

# Leggi versione corrente
CURRENT_VERSION=$(grep '^version:' "$CONFIG_FILE" | sed 's/version: *"\(.*\)"/\1/')
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Calcola nuova versione
case "$BUMP_TYPE" in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
    *)
        echo "Uso: $0 [major|minor|patch]"
        exit 1
        ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"

# Aggiorna config.yaml
sed -i '' "s/version: \"${CURRENT_VERSION}\"/version: \"${NEW_VERSION}\"/" "$CONFIG_FILE"

# Aggiungi sezione vuota nel CHANGELOG
CHANGELOG_ENTRY="## ${NEW_VERSION}\n\n- \n"
sed -i '' "s/^# Changelog$/# Changelog\n\n${CHANGELOG_ENTRY}/" "$CHANGELOG_FILE"

echo "Versione aggiornata: ${CURRENT_VERSION} -> ${NEW_VERSION}"
echo ""
echo "Prossimi passi:"
echo "  1. Modifica ai_targhe/CHANGELOG.md e descrivi le modifiche"
echo "  2. git add -A && git commit -m 'Bump version to ${NEW_VERSION}'"
echo "  3. git tag v${NEW_VERSION}"
echo "  4. git push origin main --tags"
