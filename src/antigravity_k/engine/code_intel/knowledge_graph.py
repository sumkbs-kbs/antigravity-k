import uuid
from enum import Enum
from typing import Dict, List, Any

class NodeType(str, Enum):
    FILE = "File"
    FUNCTION = "Function"
    CLASS = "Class"
    VARIABLE = "Variable"
    MODULE = "Module"

class KnowledgeGraph:
    def __init__(self):
        self.nodes = {}
        self.edges = []
        
    def add_node(self, node_id: str, node_type: NodeType, properties: Dict[str, Any]):
        properties["id"] = node_id
        properties["node_type"] = node_type
        self.nodes[node_id] = properties
        
    def add_edge(self, source_id: str, target_id: str, relationship: str):
        self.edges.append({
            "source": source_id,
            "target": target_id,
            "relationship": relationship
        })
        
    def get_nodes_by_type(self, node_type: NodeType) -> List[Dict]:
        return [n for n in self.nodes.values() if n["node_type"] == node_type]
        
    def stats(self) -> Dict:
        node_types = {}
        for node in self.nodes.values():
            nt = node["node_type"]
            node_types[nt] = node_types.get(nt, 0) + 1
            
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": node_types
        }
