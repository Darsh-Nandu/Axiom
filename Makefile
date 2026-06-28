.PHONY: install reinstall uninstall test lint format clean

install:
	uv pip install -e .

reinstall:
	uv pip uninstall -y axiom
	uv pip install -e .

uninstall:
	uv pip uninstall -y axiom

test:
	pytest

clean:
	rm -rf build dist *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

mcp:
    PYTHONPATH=src python -m axiom.mcp.mcp