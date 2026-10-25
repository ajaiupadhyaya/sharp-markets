.PHONY: all test lint fixtures markets match prices panel power dryrun paper

# Network steps (fixtures, markets, prices) read through the response cache in data/raw/cache,
# so a rerun only fetches what isn't cached yet.
all: lint fixtures markets match prices panel power test

test:
	uv run pytest -v

lint:
	uv run ruff check

fixtures:
	uv run python -m sharpmkt.footballdata

markets:
	uv run python -m sharpmkt.kalshi markets
	uv run python -m sharpmkt.polymarket markets

match:
	uv run python -m sharpmkt.match

prices:
	uv run python -m sharpmkt.kalshi prices
	uv run python -m sharpmkt.polymarket prices

panel:
	uv run python -m sharpmkt.panel

power:
	uv run python -m sharpmkt.power

dryrun:
	uv run python -m sharpmkt.confirm --dry-run 2025-12-01

paper:
	uv run python paper/make_inputs.py
	cd paper && latexmk -pdf -interaction=nonstopmode main.tex
