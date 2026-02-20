#!/usr/bin/env bash
# Ingest emails from test_mails/ into the Umbrella pipeline via SMTP.
#
# Delivers raw EML files to the in-cluster mailserver over SMTP. The deployed
# EmailConnector (polling IMAP every 5s) picks them up and feeds the rest of
# the pipeline (Stage 2 Processor → Stage 3 IngestionService).
#
# Automatically port-forwards the mailserver SMTP port to localhost:2525
# (port 25 requires root; 2525 does not) and tears it down on exit.
#
# Usage:
#   ./scripts/ingest-test-mails.sh [OPTIONS]
#
# Options:
#   --user USER       Only ingest emails for a specific maildir user (default: all)
#   --limit N         Stop after N emails (default: unlimited)
#   --delay SECS      Seconds to sleep between sends (default: 0)
#   --dry-run         Walk maildir and print metadata without sending
#
# Environment variables (with minikube defaults):
#   SMTP_HOST           default: localhost
#   SMTP_PORT           default: 2525
#   SMTP_RECIPIENT      default: testuser@umbrella.local
#   MAILSERVER_NS       default: umbrella-connectors

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"
TEST_MAILS_DIR="${REPO_ROOT}/test_mails/maildir"

SMTP_HOST="${SMTP_HOST:-localhost}"
SMTP_PORT="${SMTP_PORT:-2525}"
SMTP_RECIPIENT="${SMTP_RECIPIENT:-testuser@umbrella.local}"
MAILSERVER_NS="${MAILSERVER_NS:-umbrella-connectors}"

# ── Argument parsing ─────────────────────────────────────────────────────────
USER_FILTER=""
LIMIT=0
DELAY=0
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --user)    USER_FILTER="$2"; shift 2 ;;
        --limit)   LIMIT="$2";       shift 2 ;;
        --delay)   DELAY="$2";       shift 2 ;;
        --dry-run) DRY_RUN=true;     shift   ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Pre-flight checks ────────────────────────────────────────────────────────
if [[ ! -d "$TEST_MAILS_DIR" ]]; then
    echo "ERROR: test_mails directory not found: $TEST_MAILS_DIR" >&2
    exit 1
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "ERROR: venv Python not found: $VENV_PYTHON" >&2
    echo "  Run: uv pip install -e connectors/connector-framework/ -e connectors/email/ -e ingestion-api/" >&2
    exit 1
fi

SMTP_PF_PID=""

if [[ "$DRY_RUN" == "false" ]]; then
    if ! kubectl get svc mailserver -n "$MAILSERVER_NS" &>/dev/null; then
        echo "ERROR: mailserver service not found in namespace '$MAILSERVER_NS'." >&2
        echo "  Is minikube running and the pipeline deployed?" >&2
        exit 1
    fi

    # ── Port-forward mailserver SMTP ─────────────────────────────────────────
    echo "Port-forwarding mailserver SMTP → localhost:${SMTP_PORT} ..."
    kubectl port-forward -n "$MAILSERVER_NS" svc/mailserver "${SMTP_PORT}:25" &>/dev/null &
    SMTP_PF_PID=$!

    cleanup() {
        echo "Stopping port-forward..."
        kill "$SMTP_PF_PID" 2>/dev/null || true
        wait "$SMTP_PF_PID" 2>/dev/null || true
    }
    trap cleanup EXIT

    # Wait for port to be ready
    for i in $(seq 1 40); do
        if bash -c "echo >/dev/tcp/localhost/${SMTP_PORT}" 2>/dev/null; then
            echo "SMTP port-forward ready."
            break
        fi
        [[ $i -eq 40 ]] && { echo "ERROR: SMTP port-forward timed out." >&2; exit 1; }
        sleep 0.5
    done
fi

echo "============================================"
echo "Umbrella — Test Mail Ingestor (SMTP)"
echo "============================================"
echo "  Maildir:    $TEST_MAILS_DIR"
echo "  SMTP:       ${SMTP_HOST}:${SMTP_PORT}"
echo "  Recipient:  $SMTP_RECIPIENT"
echo "  User:       ${USER_FILTER:-<all>}"
echo "  Limit:      ${LIMIT:-unlimited}"
echo "  Delay:      ${DELAY}s"
echo "  Dry-run:    $DRY_RUN"
echo ""

# ── Embedded Python sender ───────────────────────────────────────────────────
"$VENV_PYTHON" - \
    "$TEST_MAILS_DIR" \
    "$USER_FILTER" \
    "$LIMIT" \
    "$DELAY" \
    "$DRY_RUN" \
    "$SMTP_HOST" \
    "$SMTP_PORT" \
    "$SMTP_RECIPIENT" \
    <<'PYTHON'
"""Send raw EML files to an SMTP server."""
from __future__ import annotations

import email
import smtplib
import sys
import time
from pathlib import Path


def extract_from(raw: bytes) -> str:
    """Return the From header value, or a fallback sender address."""
    try:
        msg = email.message_from_bytes(raw)
        from_header = msg.get("From", "")
        # Extract bare address from "Name <addr>" format
        if "<" in from_header and ">" in from_header:
            return from_header[from_header.index("<") + 1 : from_header.index(">")]
        if from_header.strip():
            return from_header.strip()
    except Exception:
        pass
    return "noreply@umbrella.local"


def main(
    maildir: Path,
    user_filter: str,
    limit: int,
    delay: float,
    dry_run: bool,
    smtp_host: str,
    smtp_port: int,
    recipient: str,
) -> None:
    pattern = f"{user_filter}/**/*" if user_filter else "**/*"
    all_files = [p for p in maildir.glob(pattern) if p.is_file()]

    if not all_files:
        print(f"WARNING: no files found in {maildir} (user_filter={user_filter or '<all>'})")
        return

    if limit:
        all_files = all_files[:limit]

    print(f"Files to process: {len(all_files)}")

    if dry_run:
        for path in all_files:
            raw = path.read_bytes()
            sender = extract_from(raw)
            try:
                msg = email.message_from_bytes(raw)
                subject = msg.get("Subject", "")
                message_id = msg.get("Message-ID", "")
            except Exception:
                subject = ""
                message_id = ""
            print(f"  DRY-RUN  {path.relative_to(maildir)}  from={sender}  subject={subject!r}  id={message_id}")
        return

    sent = 0
    errors = 0

    for path in all_files:
        rel = path.relative_to(maildir)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            print(f"  ERROR  read  {rel}: {exc}", flush=True)
            errors += 1
            continue

        sender = extract_from(raw)
        try:
            msg_obj = email.message_from_bytes(raw)
            message_id = msg_obj.get("Message-ID", "")
        except Exception:
            message_id = ""

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
                smtp.sendmail(sender, [recipient], raw)
            sent += 1
            print(f"  SENT [{sent}]  {rel}  id={message_id}", flush=True)
        except Exception as exc:
            print(f"  ERROR  smtp  {rel}: {exc}", flush=True)
            errors += 1

        if delay:
            time.sleep(delay)

    print("")
    print(f"Done — sent: {sent}, errors: {errors}")


if __name__ == "__main__":
    maildir     = Path(sys.argv[1])
    user_filter = sys.argv[2]
    limit       = int(sys.argv[3])
    delay       = float(sys.argv[4])
    dry_run     = sys.argv[5].lower() == "true"
    smtp_host   = sys.argv[6]
    smtp_port   = int(sys.argv[7])
    recipient   = sys.argv[8]

    main(maildir, user_filter, limit, delay, dry_run, smtp_host, smtp_port, recipient)
PYTHON
