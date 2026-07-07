from dataclasses import dataclass, field
# dataclass: simple, clean representation of the class
# field: new structure everytime. NO combined structure usage across all class instances
from typing import Optional
# either [data-type] or '= data-type'; one of the two options

@dataclass      # no need to __init__ yourself
class CommandIR:
    action:    Optional[str]       = None                           # task to be performed
    target:    Optional[list]      = None                           # the object of the task
    params:    dict                = field(default_factory=dict)    
    # default_factory: the default type of data structure
    errors:    list                = field(default_factory=list)    # fatal! must stop execution
    warnings:  list                = field(default_factory=list)    # ignorable! only notify