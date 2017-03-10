from bauhaus2.experiment import ResequencingConditionTable
from bauhaus2 import Workflow

from .mapping import subreadsMappingPlan

class ConstantArrowWorkflow(Workflow):
    """
    Align subreads to the reference and run constant arrow model,
    generate csv file of errormode.
    """
    WORKFLOW_NAME        = "ConstantArrow"
    CONDITION_TABLE_TYPE = ResequencingConditionTable
    R_SCRIPTS            = ( "R/constant_arrow.R",
                             "R/FishbonePlots.R",
                             "R/Bauhaus2.R" )

    def plan(self):
        return ["constant-arrow.snake"] + \
            subreadsMappingPlan(self.conditionTable, self.cliArgs)