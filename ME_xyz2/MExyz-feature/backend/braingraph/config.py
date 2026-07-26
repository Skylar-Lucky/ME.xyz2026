from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GraphSettings:
    project_root: Path = Path(__file__).resolve().parents[2]

    @property
    def csv_path(self) -> Path:
        configured = os.getenv("MEMORY_GRAPH_CSV_PATH")
        if configured:
            return Path(configured).resolve()
        return (
            self.project_root.parent
            / "braingraph"
            / "memory-graph-demo"
            / "data"
            / "mexyz_memory_events.csv"
        )


settings = GraphSettings()
