import yaml
import os
from pathlib import Path
from typing import Dict, Any, List

class SecurityPolicyEngine:
    def __init__(self, policy_file: str = "policy.yaml"):
        self.policy_file = Path(policy_file)
        self.policy: Dict[str, Any] = {
            "network": {"allowed_domains": [], "blocked_domains": []},
            "filesystem": {"allowed_paths": [], "read_only_paths": []},
            "process": {"blocked_commands": []}
        }
        self.load_policy()

    def load_policy(self):
        if self.policy_file.exists():
            with open(self.policy_file, "r") as f:
                loaded = yaml.safe_load(f)
                if loaded:
                    self.policy.update(loaded)

    def is_command_allowed(self, command: str) -> bool:
        blocked = self.policy.get("process", {}).get("blocked_commands", [])
        for b in blocked:
            if b in command:
                return False
        return True

    def is_domain_allowed(self, domain: str) -> bool:
        network = self.policy.get("network", {})
        allowed = network.get("allowed_domains", [])
        blocked = network.get("blocked_domains", [])
        
        for b in blocked:
            if b in domain:
                return False
        
        # If allowed list is empty, default is allow-all. If not empty, it's default-deny.
        if allowed:
            for a in allowed:
                if a in domain:
                    return True
            return False
            
        return True

policy_engine = SecurityPolicyEngine()

def get_policy_engine() -> SecurityPolicyEngine:
    return policy_engine
