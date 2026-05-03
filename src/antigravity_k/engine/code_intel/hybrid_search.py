import logging
from typing import List, Dict

logger = logging.getLogger("antigravity_k.engine.code_intel.hybrid_search")

class HybridSearchEngine:
    def __init__(self, graph):
        self.graph = graph
        self.index_built = False
        
    def build_index(self):
        # Mock index building
        self.index_built = True
        logger.info("Hybrid search index built.")
        
    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        if not self.index_built:
            self.build_index()
            
        results = []
        q_lower = query.lower()
        
        # Simple substring match over node names and properties
        for node_id, node in self.graph.nodes.items():
            name = node.get("name", "").lower()
            if q_lower in name:
                results.append(node)
                
            # Stop if we have enough
            if len(results) >= top_k:
                break
                
        return results
