"""Knowledge Graph module."""

from enum import Enum
from typing import Any


class NodeType(str, Enum):
    """Nodetype.

    Bases: str, Enum
    """

    FILE = "File"
    FUNCTION = "Function"
    CLASS = "Class"
    VARIABLE = "Variable"
    MODULE = "Module"


class KnowledgeGraph:
    """Knowledgegraph."""

    def __init__(self):
        """Initialize the KnowledgeGraph."""
        self.nodes = {}
        self.edges = []

    def add_node(self, node_id: str, node_type: NodeType, properties: dict[str, Any]):
        """Add node.

        Args:
            node_id (str): str node id.
            node_type (NodeType): NodeType node type.
            properties (dict[str, Any]): dict[str, Any] properties.

        """
        properties["id"] = node_id
        properties["node_type"] = node_type
        self.nodes[node_id] = properties

    def add_edge(self, source_id: str, target_id: str, relationship: str):
        """Add edge.

        Args:
            source_id (str): str source id.
            target_id (str): str target id.
            relationship (str): str relationship.

        """
        self.edges.append({"source": source_id, "target": target_id, "relationship": relationship})

    def get_nodes_by_type(self, node_type: NodeType) -> list[dict]:
        """Retrieve nodes by type.

        Args:
            node_type (NodeType): NodeType node type.

        Returns:
            list[dict]: The list[dict] result.

        """
        return [n for n in self.nodes.values() if n["node_type"] == node_type]

    def stats(self) -> dict:
        """Stats.

        Returns:
            dict: The dict result.

        """
        node_types: dict[NodeType, int] = {}
        for node in self.nodes.values():
            nt = node["node_type"]
            node_types[nt] = node_types.get(nt, 0) + 1

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": node_types,
        }
