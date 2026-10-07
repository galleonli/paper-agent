# Paper Agent

Collect relevant papers, keep a local research library, and review your reading list from Raycast.

Paper Agent combines a Python pipeline with a macOS Raycast extension. It fetches arXiv papers and Google Scholar alert entries, filters and deduplicates them, and saves notes and digests as local files.

## What you can do

- Browse today's papers, search your library, and manage favorites and a reading queue in Raycast.
- Filter papers using your research interests, categories, and seed papers.
- Keep Markdown notes and daily or weekly digests; export BibTeX and RIS.
- Add optional AI summaries based on paper metadata and abstracts.
- Run the pipeline from the command line or configure a macOS daily schedule.

AI summaries are optional. They are not full-text evidence reviews. Google Scholar inbox entries are handled separately from the arXiv recommendation flow.

## Requirements

- Git and Python 3.11 or later with virtual-environment support for the core.
- macOS and Raycast for the extension.
- Network access to your selected paper sources.
- An OpenAI API key only if you enable AI summaries.

The extension currently requires a separate installation of the Python core.

## Quick start

```sh
git clone https://github.com/galleonli/paper-agent.git
cd paper-agent
./scripts/bootstrap.sh
```

Edit `config.yaml` to set your research interests and output directory. Use [config.example.yaml](config.example.yaml) as the configuration reference. Keep optional AI summaries disabled for the first run if you have not configured a provider.

```sh
.venv/bin/python -m paper_agent run --config config.yaml
```

Inspect the generated library and digest in your configured output directory.

## Use Raycast

Install the Paper Agent extension from the Raycast Store, then follow the [extension setup guide](https://github.com/galleonli/paper-agent-raycast#readme) to configure the core, configuration file, and paper directory. Open **Today's Papers** after a successful pipeline run.

Use **Check Run Status** to diagnose execution problems. Add the daily schedule only after the manual workflow works. A sleeping or unavailable machine can delay scheduled work.

## Configuration and troubleshooting

The [detailed setup reference](docs/usage.md) covers source settings, scheduling, exports, and configuration precedence. Raycast preferences currently override several core settings when the extension prepares a run.

Keep credentials out of the repository. Do not paste API keys into bug reports or print them in diagnostics.

## Install the CLI from source

After cloning the repository, install the core into your chosen Python environment:

```sh
python -m pip install .
paper-agent --help
```

This provides the `paper-agent` command. You still need a configuration file and output directory; the Raycast extension also needs the path to this environment's Python executable. The repository bootstrap remains the documented quick start for Raycast users.

## Development

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

Report reproducible problems in [Issues](https://github.com/galleonli/paper-agent/issues), including the command, platform, and redacted error output.

## License

See [LICENSE](LICENSE).
