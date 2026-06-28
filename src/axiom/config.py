from pathlib import Path
import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"

with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)