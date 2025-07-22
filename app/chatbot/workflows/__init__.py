# Import workflow implementations to trigger registration
from .krishna_mini import KrishnaMiniWorkflow
from .krishna import KrishnaWorkflow
from .krishna_advance import KrishnaAdvanceWorkflow

__all__ = ["KrishnaMiniWorkflow", "KrishnaWorkflow", "KrishnaAdvanceWorkflow"]
