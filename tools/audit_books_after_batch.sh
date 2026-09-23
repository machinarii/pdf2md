#!/bin/sh
set -eu

while systemctl --user is-active --quiet pdf2md-books; do
  sleep 60
done

exec /home/sidekick/pdf2md/.venv/bin/python \
  /home/sidekick/pdf2md/tools/audit_markdown_quality.py \
  /home/sidekick/lightrag/lightrag-input/books-md \
  --output /home/sidekick/pdf2md-batch/quality-audit
