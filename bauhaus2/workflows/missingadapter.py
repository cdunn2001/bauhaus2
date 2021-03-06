from bauhaus2.experiment import ResequencingConditionTable
from bauhaus2 import Workflow

from .mapping import subreadsMappingPlan

class MissingAdapterWorkflow(Workflow):
    """
    Generate alignment based heatmaps.
    """
    WORKFLOW_NAME        = "MissingAdapter"
    CONDITION_TABLE_TYPE = ResequencingConditionTable
    SMRTPIPE_PRESETS     = ("extras/pbsmrtpipe-mappings-preset.xml",)
    R_SCRIPTS            = ("R/Bauhaus2.R", 
                            "R/missingAdapter.R")
    PYTHON_SCRIPTS       = ("Python/generateJsonReport.py",)
                            
    def plan(self):
        return ["detect-missing-adapters.snake", "collect-smrtlink-subreads.snake"] + \
            subreadsMappingPlan(self.conditionTable, self.cliArgs)
