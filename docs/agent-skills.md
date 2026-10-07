# Agent skills and distribution

The [pdf2md skill](../plugins/pdf2md/skills/pdf2md/SKILL.md) is shared by Claude
Code, Codex, OpenClaw, and Hermes. It installs the converter separately at a tested
commit and runs it locally. Python 3.10+, Git, and PyMuPDF are required; Tesseract,
LibreOffice, and Ollama are optional. Ordinary conversion needs no account or API key.
Plugin version 0.1.0 targets converter version 0.2.0. The skill's tested install
revision is `821d6e1f2568e148d9d2e7d7215352433c5b6a94`, including structured table spans, native equations, strict PDF coverage,
parser budgets, the Python API, and optional PDF chunk export. Existing checkouts are not changed
automatically; confirm options with `--help`. Chunk export additionally requires
`tiktoken`; table vision requires a user-selected Ollama model and explicit flags.
See the [usage guide](usage.md#table-preservation-and-page-coverage).

## Claude Code

```bash
claude plugin marketplace add machinarii/pdf2md
claude plugin install pdf2md@pdf2md
```

Start a new session and invoke `/pdf2md:pdf2md`, or ask to convert a document.
The public repository hosts its own marketplace; that does not imply a listing
in Anthropic's directory or official marketplace.

## Codex CLI and app

```bash
codex plugin marketplace add machinarii/pdf2md
codex plugin add pdf2md@pdf2md
```

Start a new session and ask to use the pdf2md skill. Codex reads the catalog at
`.agents/plugins/marketplace.json` and the manifest in `plugins/pdf2md/.codex-plugin`.
This repository marketplace is separate from OpenAI's reviewed directory.

## OpenClaw

Until a ClawHub listing is published, copy the standalone skill from a checkout
into your OpenClaw workspace's `skills/pdf2md` directory. From the checkout, with
your actual workspace path substituted:

```bash
mkdir -p /path/to/openclaw-workspace/skills
cp -R plugins/pdf2md/skills/pdf2md /path/to/openclaw-workspace/skills/pdf2md
```

If that destination already exists, review it before replacing it. Restart the
agent session to load the skill. This manual installation does not register a
public ClawHub listing.

## Hermes

Hermes supports direct GitHub skill sources:

```bash
hermes skills inspect machinarii/pdf2md/plugins/pdf2md/skills/pdf2md
hermes skills install machinarii/pdf2md/plugins/pdf2md/skills/pdf2md
```

The skill is also compatible with Hermes' ClawHub source once published there.
A GitHub install is not a listing in Hermes' default curated sources.

## Release artifacts

```bash
python3 tools/package_skill.py
```

This builds `dist/pdf2md-plugin-0.1.0.zip` for Claude/Codex and
`dist/pdf2md-skill-0.1.0.zip` for standalone skill use. The explicit file allowlist
excludes document inputs, local configuration, and development artifacts. Both
archives include the MIT license. The plugin ZIP includes both plugin manifests
and the shared skill; it does not bundle the converter or PyMuPDF.

Validate with installed development tools before publishing:

```bash
claude plugin validate --strict plugins/pdf2md
claude plugin validate .
python3 tools/package_skill.py
```

Increment both plugin manifests together for subsequent plugin releases. Update
the skill's pinned converter commit only after testing that revision.

## Marketplace submissions

- **Claude:** pushing this repository publishes its own installable marketplace.
  For Anthropic's directory, use the [developer portal](https://claude.ai/directory/manage)
  with the GitHub plugin path `plugins/pdf2md`. The directory requires a paid
  account and review; official-marketplace placement is a separate partner route.
  See [Claude publishing guidance](https://code.claude.com/docs/en/plugins/publish).
- **Codex:** pushing this repository publishes its own installable marketplace.
  For OpenAI's directory, upload the plugin ZIP as a skills-only plugin at the
  [submission portal](https://platform.openai.com/plugins), complete listing and
  review fields, and submit. See [OpenAI's upload guidance](https://developers.openai.com/plugins/guides/submit-claude-plugin).
- **OpenClaw:** authenticate to ClawHub through your approved credential workflow,
  then publish the standalone skill directory. Do not commit credentials or put
  tokens in command arguments. Check that the slug is available or owned by you.
- **Hermes:** the GitHub path above is directly installable. Hermes also indexes
  [multiple skill sources, including ClawHub](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/).
  Publishing to ClawHub makes the same skill available through that source; there
  is no separate Hermes upload required for this route.

ClawHub publish command (requires authentication; not a claim of publication):

```bash
npx --yes clawhub@0.23.3 skill publish plugins/pdf2md/skills/pdf2md \
  --slug machinarii-pdf2md --name "pdf2md" --version 0.1.0 \
  --changelog "Initial portable document-to-Markdown skill" \
  --source-repo https://github.com/machinarii/pdf2md \
  --source-commit 7dbf10022dd3d0d57b4075da63985cb5954a4873 \
  --source-path plugins/pdf2md/skills/pdf2md
```

After ClawHub confirms publication, users can run `clawhub install machinarii-pdf2md`
in an OpenClaw workspace or `hermes skills install clawhub/machinarii-pdf2md`.
See the [ClawHub CLI reference](https://docs.openclaw.ai/clawhub/cli).
