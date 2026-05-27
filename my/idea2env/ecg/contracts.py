from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ContractNode:
    id: str
    type: str
    label: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ContractNode":
        return cls(
            id=str(data["id"]),
            type=str(data["type"]),
            label=str(data.get("label", "")),
            attrs=dict(data.get("attrs", {})),
        )


@dataclass
class ContractEdge:
    src: str
    rel: str
    dst: str
    attrs: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ContractEdge":
        return cls(
            src=str(data["src"]),
            rel=str(data["rel"]),
            dst=str(data["dst"]),
            attrs=dict(data.get("attrs", {})),
        )


@dataclass
class EnvironmentContractGraph:
    instance_id: str
    repo_root: str = ""
    test_dir: str = ""
    runner: str = "pytest"
    nodes: list[ContractNode] = field(default_factory=list)
    edges: list[ContractEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_node(self, node_id: str, node_type: str, label: str = "", **attrs: Any) -> None:
        if any(node.id == node_id for node in self.nodes):
            return
        self.nodes.append(ContractNode(node_id, node_type, label or node_id, attrs))

    def add_edge(self, src: str, rel: str, dst: str, **attrs: Any) -> None:
        if any(edge.src == src and edge.rel == rel and edge.dst == dst for edge in self.edges):
            return
        self.edges.append(ContractEdge(src, rel, dst, attrs))

    def nodes_by_type(self, node_type: str) -> list[ContractNode]:
        return [node for node in self.nodes if node.type == node_type]

    def to_json(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "repo_root": self.repo_root,
            "test_dir": self.test_dir,
            "runner": self.runner,
            "nodes": [asdict(node) for node in self.nodes],
            "edges": [asdict(edge) for edge in self.edges],
            "metadata": self.metadata,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "EnvironmentContractGraph":
        return cls(
            instance_id=str(data.get("instance_id", "")),
            repo_root=str(data.get("repo_root", "")),
            test_dir=str(data.get("test_dir", "")),
            runner=str(data.get("runner", "pytest")),
            nodes=[ContractNode.from_json(item) for item in data.get("nodes", [])],
            edges=[ContractEdge.from_json(item) for item in data.get("edges", [])],
            metadata=dict(data.get("metadata", {})),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=2, ensure_ascii=False))

    @classmethod
    def load(cls, path: Path) -> "EnvironmentContractGraph":
        return cls.from_json(json.loads(path.read_text()))


@dataclass
class ContractValidationReport:
    passed: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ContractValidationReport":
        return cls(
            passed=bool(data.get("passed", False)),
            violations=list(data.get("violations", [])),
            warnings=list(data.get("warnings", [])),
            details=dict(data.get("details", {})),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=2, ensure_ascii=False))
