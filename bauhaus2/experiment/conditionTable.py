from builtins import str
from builtins import object
__all__ = [ "InputType",
            "ConditionTable",
            "ResequencingConditionTable",
            "CoverageTitrationConditionTable",
            "UnrolledMappingConditionTable",
            "TableValidationError",
            "InputResolutionError" ]

import csv, os.path as op, sys
import eztable
import io,codecs

from bauhaus2.pbls2 import DataNotFound, InvalidDataset

# TODO: we are using the non-public method ._get_columns on
# eztable.Table objects.  That method should really be public--maybe
# ask the maintainer?

class TableValidationError(Exception): pass
class InputResolutionError(Exception): pass

class InputType(object):
    SubreadSet            = 1
    AlignmentSet          = 2
    ConsensusReadSet      = 3
    ConsensusAlignmentSet = 4
    TraceH5File           = 5

def _pVariables(tbl):
    return [ k for k in tbl.column_names if k.startswith("p_") ]

def _unique(lst):
    return sorted(set(lst))

class ConditionTable(object):
    """
    Base class for representing Milhouse-style condition tables

    Columns required: Condition, some encoding of input

    There is *no* column encoding secondary protocol; that's the way
    things work in Milhouse but not here.  The "protocol" is specified
    separately from the condition table, which is meant only to encode
    variables and their associated inputs.
    """
    def __init__(self, inputCsv, resolver):
        if not op.isfile(inputCsv):
            raise ValueError("Missing input file: %s" % inputCsv)
        nbytes = min(32, op.getsize(inputCsv))
        raw= open(inputCsv, 'rb').read(nbytes)
        if raw.startswith(codecs.BOM_UTF8):
            raise TableValidationError("Input CSV file is in UTF-8 format. Please convert to ASCII or remove Byte Order Mark (BOM)")
        try:
            with open(inputCsv) as f:
                cr = csv.reader(f)
                allRows = list(cr)
                columnNames, rows = \
                    allRows[0], allRows[1:]
                self.tbl = eztable.Table(columnNames, rows)
        except:
            raise TableValidationError("Input CSV file can't be read/parsed:" + str(sys.exc_info()[0]))
        self._validateTable()
        self._resolveInputs(resolver)

    def _validateTable(self):
        """
        Validate the input CSV file
        Exception on invalid input.

        The intention here is that this can quickly run (by a local
        "validate" rule) to spot errors in the input CSV, before we
        attempt to run the workflow.

        Possible errors that are checked for:
          - Malformed CSV input (can't be parsed)
          - Incorrect header row
          - Too few/many p_ conditions
          - Varying covariate levels under a single condition name
        """
        self._validateConditionsAreHomogeneous()
        self._validateSingleInputEncoding()

    def _validateConditionsAreHomogeneous(self):
        for c in self.conditions:
            condition = self.condition(c)
            for variable in self.variables:
                if len(set(condition._get_column(variable))) != 1:
                    raise TableValidationError(
                        "Conditions must be homogeneous--no variation allowed in variables/settings within a condition.  " +
                        "(Offending condition: \"%s\"; offending column: \"%s\")" % (c, variable)
                    )

    def _validateSingleInputEncoding(self):
        cols = self.tbl.column_names
        inputEncodings = 0
        if {"ReportsPath"}.issubset(cols):
            inputEncodings += 1
        if {"RunCode", "ReportsFolder"}.issubset(cols):
            inputEncodings += 1
        if {"SMRTLinkServer", "JobId"}.issubset(cols):
            inputEncodings += 1
        if {"JobPath"}.issubset(cols):
            inputEncodings += 1
        if {"SubreadSet"}.issubset(cols):
            inputEncodings += 1
        if {"AlignmentSet"}.issubset(cols):
            inputEncodings += 1
        if {"TraceH5File"}.issubset(cols):
            inputEncodings += 1
        if inputEncodings == 0:
          raise TableValidationError("Input data not encoded in condition table. Table requires one and only one column (or pair of columns) as follows: ReportsPath, RunCode+ReportsFolder, SMRTLinkServer+JobId, JobPath, SubreadSet, AlignmentSet")
        if inputEncodings > 1:
            raise TableValidationError("Condition table can only represent input data in one way")

    def _resolveInput(self, resolver, rowRecord):
        cols = self.tbl.column_names
        if {"ReportsPath"}.issubset(cols):
            return resolver.findSubreadSet(rowRecord.ReportsPath)
        elif {"RunCode", "ReportsFolder"}.issubset(cols):
            return resolver.resolveSubreadSet(rowRecord.RunCode, rowRecord.ReportsFolder)
        elif {"SMRTLinkServer", "JobId"}.issubset(cols):
            return resolver.resolveAlignmentSet(rowRecord.SMRTLinkServer, rowRecord.JobId)
        elif {"JobPath"}.issubset(cols):
            return resolver.findAlignmentSet(rowRecord.JobPath)
        elif {"SubreadSet"}.issubset(cols):
            return resolver.ensureSubreadSet(rowRecord.SubreadSet)
        elif {"AlignmentSet"}.issubset(cols):
            return resolver.ensureAlignmentSet(rowRecord.AlignmentSet)
        elif {"TraceH5File"}.issubset(cols):
            return resolver.ensureTraceH5File(rowRecord.TraceH5File)


    def _resolveInputs(self, resolver):
        self._inputsByCondition = {}
        for condition in self.conditions:
            subDf = self.condition(condition)
            inputs = []
            for row in subDf:
                try:
                    inputs.append(self._resolveInput(resolver, row))
                except DataNotFound as e:
                    raise InputResolutionError(str(e))
            self._inputsByCondition[condition] = inputs

    @property
    def conditions(self):
        return _unique(self.tbl.Condition)

    def condition(self, condition):
        # Get subtable for condition
        return self.tbl.restrict(("Condition",), lambda x: x == condition)

    @property
    def pVariables(self):
        """
        "p variables" encoded in the condition table using column names "p_*"
        """
        return _pVariables(self.tbl)

    @property
    def variables(self):
        """
        "Covariates" are the "p_" variables           -
        """
        return self.pVariables

    def variable(self, condition, variableName):
        """
        Get the value of a variable within a condition

        # TODO: we are using a non-public API method in eztable!
        """
        vals = _unique(self.condition(condition)._get_column(variableName))
        assert len(vals) == 1
        return vals[0]

    @property
    def inputType(self):
        cols = self.tbl.column_names
        if {"ReportsPath"}.issubset(cols) or \
           {"RunCode", "ReportsFolder"}.issubset(cols) or \
           {"SubreadSet"}.issubset(cols):
            return InputType.SubreadSet
        if {"SMRTLinkServer", "JobId"}.issubset(cols) or \
           {"JobPath"}.issubset(cols) or \
           {"AlignmentSet"}.issubset(cols):
            return InputType.AlignmentSet
        if {"TraceH5File"}.issubset(cols) :
            return InputType.TraceH5File
        raise NotImplementedError("Input type not recognized/supported")

    @property
    def inputsAreMapped(self):
        return self.inputType == InputType.AlignmentSet

    def inputs(self, condition):
        return self._inputsByCondition[condition]


class ResequencingConditionTable(ConditionTable):
    """
    Base class for representing Milhouse-style condition tables for
    resequencing-bases analyses (require a reference, use mapping)
    """
    def _validateGenomeColumnPresent(self):
        if "Genome" not in self.tbl.column_names:
            raise TableValidationError("'Genome' column must be present")

    def _validateTable(self):
        """
        Additional validation: "Genome" column required
        """
        super(ResequencingConditionTable, self)._validateTable()
        self._validateGenomeColumnPresent()

    def _resolveInputs(self, resolver):
        super(ResequencingConditionTable, self)._resolveInputs(resolver)
        self._referenceByCondition = {}
        self._referenceSetByCondition = {}
        for condition in self.conditions:
            genome = self.genome(condition)
            try:
                self._referenceByCondition[condition] = resolver.resolveReference(genome)
                self._referenceSetByCondition[condition] = resolver.resolveReferenceSet(genome)
            except DataNotFound as e:
                raise InputResolutionError(str(e))

    @property
    def variables(self):
        """
        In addition to the "p_" variables, "Genome" is considered an implicit
        variable in resequencing experiments
        """
        return [ "Genome" ] + self.pVariables

    def genome(self, condition):
        """
        Use the condition table to look up the correct "Genome" based on
        the condition name
        """
        genomes = _unique(self.condition(condition).Genome)
        assert len(genomes) == 1
        return genomes[0]

    def reference(self, condition):
        return self._referenceByCondition[condition]

    def referenceSet(self, condition):
        return self._referenceSetByCondition[condition]


class CoverageTitrationConditionTable(ResequencingConditionTable):

    def _validateAtLeastOnePVariable(self):
        if len(_pVariables(self.tbl)) < 1:
            raise TableValidationError(
                'For CoverageTitration, there must be at least one covariate ("p_" variable) in the condition table')

    def _validateTable(self):
        super(CoverageTitrationConditionTable, self)._validateTable()
        self._validateAtLeastOnePVariable()

    def referenceMask(self, condition):
        return self._referenceMaskByCondition[condition]

    def _resolveInputs(self, resolver):
        super(CoverageTitrationConditionTable, self)._resolveInputs(resolver)
        self._referenceMaskByCondition = {}
        for condition in self.conditions:
            genome = self.genome(condition)
            try:
                self._referenceMaskByCondition[condition] = resolver.resolveReferenceMask(genome)
            except DataNotFound as e:
                raise InputResolutionError(str(e))


class UnrolledMappingConditionTable(ResequencingConditionTable):
    """
    Unrolled mapping requires an unrolled reference.  Ideally we would
    like some kind of flag in the reference information to indicate
    whether this holds or not.  For now, just look for "circular" or
    "unrolled" in the reference name.

    This workflow requires unmapped inputs.
    """
    def _validateTable(self):
        super(UnrolledMappingConditionTable, self)._validateTable()

        if self.inputsAreMapped:
            raise TableValidationError("Unrolled mapping workflow requires unmapped inputs.")

        for genome in self.tbl.Genome:
            if "unrolled" in genome.lower() or "circular" in genome.lower():
                continue
            else:
                raise TableValidationError("Unrolled mapping requires an unrolled reference")
