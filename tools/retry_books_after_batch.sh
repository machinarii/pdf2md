#!/bin/sh
set -eu

while systemctl --user is-active --quiet pdf2md-books; do
  sleep 60
done

exec /home/sidekick/pdf2md/.venv/bin/python \
  /home/sidekick/pdf2md/tools/batch_to_lightrag.py \
  --source /mnt/mac/Users/sidekick/knowledge-base/books-pdf \
  --target /home/sidekick/lightrag/lightrag-input/books-md \
  --state /home/sidekick/pdf2md-batch \
  --converter /home/sidekick/.local/bin/pdf2md \
  --model glm-5.3-flash:cloud \
  --ollama-host http://host.orb.internal:11434
