from bauhaus2.experiment import UnrolledMappingConditionTable
from bauhaus2 import Workflow

from .subreads import subreadsPlan

def UnrolledNoHQMappingPlan(ct, args):
    if ct.inputsAreMapped:
        # Mapping already happened, link it.
        return [ "collect-mappings.snake",
                 "collect-references.snake",
                 "scatter-subreads.snake" ]
    elif not args.no_smrtlink:
        # Use SMRTLink for mapping
        return [ "map-unrolledNoHQ-smrtlink.snake",
                 "smrtlink-job-status.snake",
                 "collect-references.snake",
                 "scatter-subreads.snake" ] + \
                 subreadsPlan(ct, args)
    else:
        # Do our own unrolledNoHQ mapping
        return [ "map-unrolledNoHQ.snake",
                 "collect-references.snake",
                 "scatter-subreads.snake" ] + \
                 subreadsPlan(ct, args)

class UnrolledNoHQMappingWorkflow(Workflow):
    """
    Map "unrolled" ZMW reads to an unrolled reference.

    Note that this implies that the HQ region designation is
    *ignored*, and the entire read sequence from the ZMW is used as a
    mapping query.  (We will add an unrolled mapping workflow which
    maps just the HQ region, as soon as BLASR supports it directly).
    """
    WORKFLOW_NAME        = "UnrolledNoHQMapping"
    CONDITION_TABLE_TYPE = UnrolledMappingConditionTable
    SMRTPIPE_PRESETS     = ("extras/pbsmrtpipe-unrolled-mappings-preset.xml",)

    def plan(self):
        return UnrolledNoHQMappingPlan(self.conditionTable, self.cliArgs)
