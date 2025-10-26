#!/bin/bash
set -euo pipefail

echo "🔄 Generating TypeScript types from OpenAPI spec..."

# Backend URL (default to localhost:8000, can be overridden)
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
OPENAPI_URL="${BACKEND_URL}/api/v1/openapi.json"

# Output directory and file
TYPES_DIR="app/frontend/types"
TYPES_FILE="${TYPES_DIR}/api.ts"

# Validate tooling
if ! command -v pnpm >/dev/null 2>&1; then
  echo "❌ Error: pnpm is not installed or not on PATH"
  echo "   Install pnpm 10+ (https://pnpm.io/installation) and try novamente"
  exit 1
fi

# Create types directory if it doesn't exist
mkdir -p "${TYPES_DIR}"

echo "📥 Fetching OpenAPI spec from ${OPENAPI_URL}..."

# Download OpenAPI spec
if ! curl -fSs "${OPENAPI_URL}" -o "${TYPES_DIR}/openapi.json"; then
  echo "❌ Error: não foi possível baixar o OpenAPI em ${OPENAPI_URL}"
  echo "   Certifique-se de que o backend está rodando (ex.: python app/backend/run.py ou make docker-up)"
  exit 1
fi

echo "✨ Generating TypeScript types..."

# Generate types using openapi-typescript
cd app/frontend
pnpm dlx openapi-typescript ./types/openapi.json -o ./types/api.ts

# Remove the downloaded spec to evitar arquivos grandes versionados
rm -f ./types/openapi.json

echo "✅ Types generated successfully at ${TYPES_FILE}"
echo "🎉 You can now import types from '@/types/api'"
