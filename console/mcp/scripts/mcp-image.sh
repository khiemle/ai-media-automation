#!/usr/bin/env bash
# AI Media Console — MCP Docker image provisioner.
#
# Builds the ai-media-console-mcp image, ingests a token (pasted from the
# admin UI's "Copy command" output), normalizes the backend URL for
# in-container reachability, writes an env file, smoke-tests the
# container, and prints a docker-flavored `claude mcp add` snippet.
#
# Token source: paste the full `claude mcp add ...` command emitted by
# the System tab in the console UI (POST /api/system/mcp/mint-token).
#
# Usage:
#   ./console/mcp/scripts/mcp-image.sh                       # full flow (clipboard on macOS, stdin on Linux)
#   ./console/mcp/scripts/mcp-image.sh --build-only          # build image, skip token + smoke
#   ./console/mcp/scripts/mcp-image.sh --token-only          # skip build
#   ./console/mcp/scripts/mcp-image.sh --no-smoke-test       # skip docker run --self-test
#   ./console/mcp/scripts/mcp-image.sh --from-clipboard      # force pbpaste source (macOS)
#   ./console/mcp/scripts/mcp-image.sh --stdin               # read pasted command from stdin
#   ./console/mcp/scripts/mcp-image.sh --env-file PATH       # override default env-file path
#   ./console/mcp/scripts/mcp-image.sh --image-tag TAG       # override default image tag
#
# Exit codes: 0 success, 1 environment failure (Docker missing, smoke fail), 2 user-input error.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# ─── defaults ──────────────────────────────────────────────────────────
DO_BUILD=1
DO_TOKEN=1
DO_SMOKE=1
INPUT_SOURCE=""   # "" = auto, "clipboard" = pbpaste, "stdin" = stdin
ENV_FILE="${HOME}/.mcp/ai-media-console.env"
IMAGE_TAG="ai-media-console-mcp:latest"

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options]

Builds the AI Media Console MCP Docker image, ingests a service token
from the admin UI's "Copy command" output, writes an env file, smoke-
tests the container, and prints a docker-flavored \`claude mcp add\`
snippet.

Options:
  --build-only          Build the image only; skip token ingestion + smoke.
  --token-only          Skip image build; only ingest token + write env + smoke.
  --no-smoke-test       Skip the post-write smoke test.
  --from-clipboard      Read the pasted command from \`pbpaste\` (macOS).
  --stdin               Read the pasted command from stdin.
  --env-file PATH       Override the default env file (default: \$HOME/.mcp/ai-media-console.env).
  --image-tag TAG       Override the default image tag (default: ai-media-console-mcp:latest).
  -h, --help            Show this help and exit.

Default input source: pbpaste on macOS if available, else stdin (or stdin
if input is piped in).

Exit codes:
  0  success
  1  environment failure (Docker missing, smoke-test failed)
  2  user-input error (unparseable token, unwritable env file)
USAGE
}

# ─── arg parse ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --build-only)      DO_BUILD=1; DO_TOKEN=0; DO_SMOKE=0 ;;
        --token-only)      DO_BUILD=0; DO_TOKEN=1; DO_SMOKE=1 ;;
        --no-smoke-test)   DO_SMOKE=0 ;;
        --from-clipboard)  INPUT_SOURCE="clipboard" ;;
        --stdin)           INPUT_SOURCE="stdin" ;;
        --env-file)        ENV_FILE="$2"; shift ;;
        --image-tag)       IMAGE_TAG="$2"; shift ;;
        -h|--help)         usage; exit 0 ;;
        *)                 echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

log()  { printf "  %s\n" "$1"; }
warn() { printf "  warning: %s\n" "$1" >&2; }
fail() { printf "  FAIL: %s\n" "$1" >&2; exit "${2:-1}"; }

# ─── helpers ───────────────────────────────────────────────────────────
read_input_source() {
    # Decide where to read the pasted command from. Prints to stdout.
    local src="$INPUT_SOURCE"
    if [[ -z "$src" ]]; then
        if [[ ! -t 0 ]]; then
            src="stdin"
        elif command -v pbpaste >/dev/null 2>&1; then
            src="clipboard"
        else
            src="stdin"
        fi
    fi
    case "$src" in
        clipboard) pbpaste ;;
        stdin)     cat ;;
        *)         fail "internal: unknown input source '$src'" 2 ;;
    esac
}

extract_token_and_base() {
    # Reads pasted text on stdin. Prints two lines: token, base.
    # Exits 2 with a remediation message if either is missing.
    local input token base
    input="$(cat)"

    # Try quoted variant first: MCP_API_TOKEN="..."
    token="$(printf '%s' "$input" | grep -oE 'MCP_API_TOKEN="[^"]+"' | head -1 | sed -E 's/^MCP_API_TOKEN="(.*)"$/\1/')" || true
    if [[ -z "$token" ]]; then
        # Allow unquoted variant too: MCP_API_TOKEN=foo
        token="$(printf '%s' "$input" | grep -oE 'MCP_API_TOKEN=[^[:space:]\"\\]+' | head -1 | sed -E 's/^MCP_API_TOKEN=//')" || true
    fi

    base="$(printf '%s' "$input" | grep -oE 'MCP_CONSOLE_API_BASE=[^[:space:]\"\\]+' | head -1 | sed -E 's/^MCP_CONSOLE_API_BASE=//')" || true

    if [[ -z "$token" ]]; then
        fail "could not find MCP_API_TOKEN in pasted text. Expected format: a 'claude mcp add' command from the System tab containing --env MCP_API_TOKEN=\"...\"." 2
    fi
    if [[ -z "$base" ]]; then
        fail "could not find MCP_CONSOLE_API_BASE in pasted text. Expected format: a 'claude mcp add' command from the System tab containing --env MCP_CONSOLE_API_BASE=..." 2
    fi

    printf '%s\n%s\n' "$token" "$base"
}

normalize_base() {
    # Rewrites localhost / 127.0.0.1 to host.docker.internal so the
    # container can reach the host's FastAPI. Other hosts pass through.
    local base="$1"
    case "$base" in
        http://localhost*|http://127.0.0.1*|https://localhost*|https://127.0.0.1*)
            local rewritten
            rewritten="$(printf '%s' "$base" | sed -E 's#^(https?://)(localhost|127\.0\.0\.1)#\1host.docker.internal#')"
            warn "rewrote $base → $rewritten so the container can reach the host's FastAPI."
            printf '%s\n' "$rewritten"
            ;;
        *)
            printf '%s\n' "$base"
            ;;
    esac
}

write_env_file() {
    local token="$1" base="$2" path="$3"
    local dir
    dir="$(dirname "$path")"
    mkdir -p "$dir"
    chmod 700 "$dir" 2>/dev/null || true
    # Write atomically via tmp file in the same dir.
    local tmp
    tmp="$(mktemp "${dir}/.mcp-env.XXXXXX")"
    {
        printf '# Written by mcp-image.sh — do not commit.\n'
        printf 'MCP_API_TOKEN=%s\n' "$token"
        printf 'MCP_CONSOLE_API_BASE=%s\n' "$base"
    } > "$tmp"
    chmod 600 "$tmp"
    mv "$tmp" "$path"
    log "wrote $path (mode 0600)"
}

require_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        fail "docker not on PATH. Install Docker Desktop or start the daemon."
    fi
    if ! docker info >/dev/null 2>&1; then
        fail "docker daemon not responding. Start Docker Desktop and retry."
    fi
}

build_image() {
    require_docker
    log "building $IMAGE_TAG ..."
    ( cd "$REPO_ROOT" && docker build -t "$IMAGE_TAG" -f Dockerfile.mcp . )
    log "built $IMAGE_TAG"
}

smoke_test() {
    require_docker
    log "smoke test: docker run --rm ... --self-test"
    if ! docker run --rm \
        --env-file "$ENV_FILE" \
        --add-host=host.docker.internal:host-gateway \
        "$IMAGE_TAG" --self-test; then
        fail "smoke test failed. See container output above. Common causes: token expired (re-mint in System tab), backend unreachable (check MCP_CONSOLE_API_BASE)."
    fi
    log "smoke test passed"
}

print_snippet() {
    cat <<SNIPPET

──── Run this to register the MCP with Claude Code ────

claude mcp add ai-media-console \\
  --transport stdio \\
  -- docker run -i --rm \\
       --env-file $ENV_FILE \\
       --add-host=host.docker.internal:host-gateway \\
       $IMAGE_TAG

Then restart Claude Code.

SNIPPET
}

# ─── main flow ─────────────────────────────────────────────────────────
if [[ "$DO_BUILD" -eq 1 ]]; then
    build_image
fi

if [[ "$DO_TOKEN" -eq 1 ]]; then
    log "reading pasted 'claude mcp add' command ..."
    pasted="$(read_input_source)"
    parsed="$(printf '%s' "$pasted" | extract_token_and_base)"
    token="$(printf '%s' "$parsed" | sed -n '1p')"
    base="$(printf '%s' "$parsed" | sed -n '2p')"
    base="$(normalize_base "$base")"
    write_env_file "$token" "$base" "$ENV_FILE"
fi

if [[ "$DO_SMOKE" -eq 1 ]]; then
    smoke_test
fi

if [[ "$DO_TOKEN" -eq 1 ]]; then
    print_snippet
fi
