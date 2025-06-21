# Import workflow implementations to trigger registration
from .krishna_mini import KrishnaMiniWorkflow
from .krishna import KrishnaWorkflow

__all__ = ["KrishnaMiniWorkflow", "KrishnaWorkflow"]
