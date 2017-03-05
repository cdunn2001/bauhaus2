__all__ = [ "availableWorkflows" ]

from builtins import object
import shutil, json, os.path as op

from bauhaus2.experiment import *

from bauhaus2.utils import (mkdirp, readFile, renderTemplate,
                            chmodPlusX)

from bauhaus2.scripts import (analysisScriptPath, runShScriptPath,
                              prefixShScriptPath)

from .snakemakeFiles import (snakemakeFilePath,
                             configJsonPath,
                             snakemakeStdlibFiles,
                             runtimeFilePath)

class Workflow(object):
    WORKFLOW_NAME        = None
    CONDITION_TABLE_TYPE = None
    R_SCRIPTS            = ()
    PYTHON_SCRIPTS       = ()
    MATLAB_SCRIPTS       = ()

    @classmethod
    def conditionTableType(cls):
        return cls.CONDITION_TABLE_TYPE

    @staticmethod
    def name(cls):
        return cls.WORKFLOW_NAME

    def _bundleSnakemakeFiles(self, outputDir):
        """
        Simply *concatenate* the constituent scripts
        """
        outFname = op.join(outputDir, "workflow", "Snakefile")
        with open(outFname, "w") as outFile:
            outFile.write(readFile(runtimeFilePath("stub.py")))
            for sf in self.plan():
                sfPath = snakemakeFilePath(sf)
                contents = readFile(sfPath)
                outFile.write(contents)

    def _bundleSnakemakeStdlib(self, outputDir):
        sfDestDir = op.join(outputDir, "workflow")
        for p in snakemakeStdlibFiles():
            shutil.copy(p, sfDestDir)

    def _bundleAnalysisScripts(self, outputDir):
        analysisScripts = self.R_SCRIPTS + self.PYTHON_SCRIPTS + self.MATLAB_SCRIPTS
        for analysisScript in analysisScripts:
            scriptType = op.dirname(analysisScript)
            destDir = op.join(outputDir, "scripts", scriptType)
            shutil.copy(analysisScriptPath(analysisScript), destDir)

    def _bundleConfigJson(self, outputDir):
        acc = { "bh2.workflow_name": self.WORKFLOW_NAME }
        if not self.cliArgs.no_smrtlink:
            acc["bh2.smrtlink.host"] = self.cliArgs.smrtlink_host
            acc["bh2.smrtlink.services_port"] = self.cliArgs.smrtlink_services_port
        for snakeFile in self.plan():
            jsonPath = configJsonPath(snakeFile.replace(".snake", ".json"))
            jsonData = json.load(open(jsonPath))
            acc.update(jsonData)
        with open(op.join(outputDir, "config.json"), "w") as jsonOut:
            json.dump(acc, jsonOut, sort_keys=True, indent=4, separators=(',', ': '))
            jsonOut.write("\n")

    def _bundleRunSh(self, outputDir):
        if self.cliArgs.noGrid:
            clusterOptions="-j 4"
        else:
            clusterOptions=('-j 128 --cluster-sync="qsub -cwd -q {sge_queue} -pe smp {{threads}} -sync y -e log/ -o log/" --latency-wait 60'
                            .format(sge_queue=self.cliArgs.sgeQueue))
        outputPath = op.join(outputDir, "run.sh")
        renderTemplate(runShScriptPath(), outputPath, cluster_options=clusterOptions)
        chmodPlusX(outputPath)

    def _bundlePrefixSh(self, outputDir):
        outputPath = op.join(outputDir, "prefix.sh")
        # TODO: a lot of possibilities... can specify modules separately?
        renderTemplate(prefixShScriptPath(), outputPath)
        chmodPlusX(outputPath)

    def plan(self):
        raise NotImplementedError

    def generate(self, conditionTableCSV, outputDir):
        # Generate workflow dir
        mkdirp(outputDir)
        shutil.copyfile(conditionTableCSV, op.join(outputDir, "condition-table.csv"))
        mkdirp(op.join(outputDir, "workflow"))
        mkdirp(op.join(outputDir, "scripts"))
        if self.R_SCRIPTS:      mkdirp(op.join(outputDir, "scripts/R"))
        if self.PYTHON_SCRIPTS: mkdirp(op.join(outputDir, "scripts/Python"))
        if self.MATLAB_SCRIPTS: mkdirp(op.join(outputDir, "scripts/MATLAB"))
        self._bundleSnakemakeFiles(outputDir)  # Output relevant snakemake files
        self._bundleSnakemakeStdlib(outputDir) # Output our python stdlib for snakemake files
        self._bundleAnalysisScripts(outputDir) # Output relevant scripts
        self._bundleConfigJson(outputDir)      # Generate snakemake config.json
        self._bundleRunSh(outputDir)           # Generate driver "run" script
        self._bundlePrefixSh(outputDir)        # Generate task prefix shell code

    def __init__(self, ct, args):
        self.conditionTable = ct
        self.cliArgs = args # TODO: we should have a real class for this...

# ---

# A *plan* is a list of snakemake files that will be assembled to make
# the overall workflow.  The main entry point comes first in the list.
# A plan is in general generated dynamically depending on the input
# type, workflow type, and options provided to bauhaus2.
#
# For example: the *plan* to get mapped data depends on:
#   - whether the input already specifies mapped data (in which case
#     we just "link" to it) or if it specifies subreadsets, in which
#     case we must perform the mapping ourself;
#   - whether the bauhaus user has explicitly specified not to use
#     scatter/gather, in which case we will use naive unchunked
#     mapping


def subreadsPlan(ct, args):
    # In greater generality, this could include a bax2bam conversion
    # possibility to enable integration of RSII data; or we could even
    # run the basecaller, if we have trace input specified; or we
    # could re-call adapters... lots of possibilities.
    assert not ct.inputsAreMapped
    return [ "collect-subreads.snake" ]

def subreadsMappingPlan(ct, args):
    if ct.inputsAreMapped:
        # Mapping already happened, link it.
        return [ "collect-mappings.snake",
                 "collect-references.snake" ]
    elif not args.no_smrtlink:
        # Use SMRTLink for mapping
        return [ "map-subreads-smrtlink.snake",
                 "collect-references.snake" ] + \
                 subreadsPlan(ct, args)
    elif args.chunks > 0:
        # Do our own mapping using scatter/gather
        return [ "map-subreads.snake",
                 "scatter-subreads.snake",
                 "collect-references.snake" ] + \
                subreadsPlan(ct, args)
    else:
        # Do our own mapping, naively
        return [ "map-subreads.snake",
                 "collect-references.snake" ] + \
                subreadsPlan(ct, args)


class MappingWorkflow(Workflow):
    """
    Align subreads to the reference.
    """
    WORKFLOW_NAME        = "Mapping"
    CONDITION_TABLE_TYPE = ResequencingConditionTable

    def plan(self):
        return subreadsMappingPlan(self.conditionTable, self.cliArgs)

class MappingReportsWorkflow(Workflow):
    """
    Align subreads to the reference and generate comprehensive
    analysis plots and tables.
    """
    WORKFLOW_NAME        = "MappingReports"
    CONDITION_TABLE_TYPE = ResequencingConditionTable
    R_SCRIPTS            = ( "R/PbiSampledPlots.R",
                             "R/PbiPlots.R",
                             "R/LibDiagnosticPlots.R",
                             "R/ReadPlots.R",
                             "R/ConstantArrowFishbonePlots.R",
                             "R/Bauhaus2.R" )

    def plan(self):
        return ["summarize-mappings.snake"] + \
            subreadsMappingPlan(self.conditionTable, self.cliArgs)


class CCSMappingReportsWorkflow(Workflow):
    """
    Map CCS reads to the reference and generate comprehensive analysis
    plots and tables, including analysis of consensus accuracy by
    numpasses and yield of CCS reads by quality.
    """
    WORKFLOW_NAME        = "CCSMappingReports"
    CONDITION_TABLE_TYPE = ResequencingConditionTable
    R_SCRIPTS = ("R/ccsMappingPlots.R", "R/Bauhaus2.R")

    def plan(self):
        return [ "map-ccs.snake",
                 "ccs-subreads.snake",
                 "collect-references.snake",
                 "scatter-subreads.snake",
                 "collect-subreads.snake" ]


class CoverageTitrationWorkflow(Workflow):
    """
    Map subreads to the reference and call consensus using arrow (or
    quiver, if selected) at different coverage cuts.  Masks regions
    known to be untrustworthy in the reference.  Generate plots and
    tables of these results.

    This workflow will only work for references that have been curated
    by the consensus team.
    """
    WORKFLOW_NAME        = "CoverageTitration"
    CONDITION_TABLE_TYPE = CoverageTitrationConditionTable
    R_SCRIPTS = ("R/coverageTitrationPlots.R", "R/Bauhaus2.R")

    def plan(self):
        return [ "consensus-coverage-titration.snake" ] + \
            subreadsMappingPlan(self.conditionTable, self.cliArgs)


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

    def plan(self):
        return [ "map-unrolledNoHQ.snake",
                 "collect-references.snake",
                 "scatter-subreads.snake",
                 "collect-subreads.snake" ]

class ConstantArrowWorkflow(Workflow):
    """
    Align subreads to the reference and run constant arrow model, generate csv file of errormode.
    """
    WORKFLOW_NAME        = "ConstantArrow"
    CONDITION_TABLE_TYPE = ResequencingConditionTable
    R_SCRIPTS            = ( "R/constant_arrow.R",
                             "R/FishbonePlots.R",
                             "R/Bauhaus2.R" )

    def plan(self):
        return ["constant-arrow.snake"] + \
            subreadsMappingPlan(self.conditionTable, self.cliArgs)


# ---

availableWorkflows = {}

for wfc in (MappingWorkflow,
            MappingReportsWorkflow,
            CCSMappingReportsWorkflow,
            CoverageTitrationWorkflow,
            UnrolledNoHQMappingWorkflow,
            ConstantArrowWorkflow):
    assert wfc.WORKFLOW_NAME not in availableWorkflows, "Workflow name collision"
    assert wfc.__doc__ is not None, "All workflows require descriptive docstrings"
    availableWorkflows[wfc.WORKFLOW_NAME] = wfc
