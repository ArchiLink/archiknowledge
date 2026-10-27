#!/bin/sh
set -eu

: "${MAX_UPLOAD_MB:=10}"
: "${MAX_IMAGES_PER_LESSON:=6}"
# Largest legitimate request: every image at the limit, plus 5 MB for the form fields.
MAX_BODY_MB=$((MAX_UPLOAD_MB * MAX_IMAGES_PER_LESSON + 5))
MAX_BODY_BYTES=$((MAX_BODY_MB * 1000 * 1000))  # Caddy's "MB" is 10^6 bytes
FRAME_ANCESTORS="${FRAME_ANCESTORS:-}"
export MAX_BODY_MB MAX_BODY_BYTES FRAME_ANCESTORS

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
