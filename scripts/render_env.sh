#!/usr/bin/env bash
set -euo pipefail

required=(
  DATABASE_URL
  JWT_SECRET
  FERNET_KEY
  GOOGLE_CLIENT_ID
  GOOGLE_CLIENT_SECRET
  GOOGLE_OAUTH_REDIRECT_URI
  FRONTEND_REDIRECT_URL
  CORS_ORIGINS
)

optional=(
  APP_NAME
  APP_VERSION
  DEBUG
  API_V1_PREFIX
  API_SERVER_URL
  JWT_ALGORITHM
  ACCESS_TOKEN_TTL_MINUTES
  REFRESH_TOKEN_TTL_DAYS
  OAUTH_STATE_TTL_MINUTES
  GOOGLE_CALENDAR_API_BASE
  INVITATION_TTL_DAYS
)

get_value() {
  printenv "$1" || true
}

reject() {
  echo "render_env: cannot write $1 to .env: $2" >&2
  exit 1
}

check_value() {
  local name="$1"
  local value="$2"

  case "$value" in
    *$'\n'*)
      reject "$name" "the value contains a line break"
      ;;
    [\"\']* | '#'*)
      reject "$name" "the value starts with a quote or a comment character, which compose parses as syntax"
      ;;
    *' #'*)
      reject "$name" "the value contains a space followed by #, and compose treats the rest as a comment"
      ;;
    [[:space:]]* | *[[:space:]])
      reject "$name" "the value has leading or trailing whitespace, which compose strips"
      ;;
    *'\')
      reject "$name" "the value ends with a backslash"
      ;;
  esac

  if [ "$name" = "DATABASE_URL" ]; then
    local at_signs="${value//[^@]/}"
    if [ "${#at_signs}" -gt 1 ]; then
      reject "$name" "the value has more than one @, so the password is probably not percent-encoded (@ must be %40, : must be %3A)"
    fi
  fi
}

missing=0
for name in "${required[@]}"; do
  if [ -z "$(get_value "$name")" ]; then
    echo "render_env: required setting $name is not set" >&2
    missing=1
  fi
done
if [ "$missing" -ne 0 ]; then
  echo "render_env: refusing to write .env with missing settings" >&2
  exit 1
fi

for name in "${required[@]}" "${optional[@]}"; do
  value="$(get_value "$name")"
  if [ -z "$value" ]; then
    continue
  fi
  check_value "$name" "$value"
  printf '%s=%s\n' "$name" "${value//\$/\$\$}"
done
