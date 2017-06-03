from .arrow     import *
from .ccs       import *
from .consensus import *
from .hmm       import *
from .mapping   import *
from .subreads  import *
from .unrolled  import *
from .unrolledArrowByReference import *
from .hqrf      import *
from .isoseq_rc0      import *

from bauhaus2 import Workflow

availableWorkflows = \
 { wf.name() : wf
   for wf in Workflow.__subclasses__() }
