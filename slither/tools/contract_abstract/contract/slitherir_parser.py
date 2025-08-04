
from slither.slithir.operations.index import Index
from slither.slithir.operations.member import Member
from slither.slithir.operations.new_structure import NewStructure
from slither.slithir.operations.assignment import Assignment
from slither.slithir.operations.binary import Binary
from slither.slithir.operations.internal_call import InternalCall
from slither.slithir.operations.library_call import LibraryCall
from slither.slithir.operations.return_operation import Return
from slither.slithir.operations.type_conversion import TypeConversion
from slither.slithir.operations.high_level_call import HighLevelCall
from slither.slithir.operations.condition import Condition
from slither.slithir.operations.solidity_call import SolidityCall

from slither.core.variables.state_variable import StateVariable
from slither.core.variables.local_variable import LocalVariable

from slither.core.declarations.solidity_variables import SolidityVariableComposed
from slither.core.declarations.structure import Structure
from slither.core.declarations.structure_contract import StructureContract

from slither.slithir.variables.temporary import TemporaryVariable
from slither.slithir.variables.reference import ReferenceVariable
from slither.slithir.variables.tuple import TupleVariable

from slither.tools.contract_abstract.contract.context import AbstractContext
from slither.tools.contract_abstract.contract.contract_walker import ContractWalker

from slither.core.solidity_types.user_defined_type import UserDefinedType



class SlitherIRParser:
    def __init__(self, ir):
        self.ir = ir
        self.lvalues = []

    def parse(self):
        if isinstance(self.ir, Index):
            left_context = self._deal_with_read(self.ir.variable_left)
            right_context = self._deal_with_read(self.ir.variable_right)
            all_context = AbstractContext(None, None, left_context.input_taints | right_context.input_taints, left_context.storage_taints | right_context.storage_taints, None)
            if left_context.input is not None and left_context.storage is None:
                all_context.input = left_context.input+"["+right_context.value+"]" 
                all_context.value = all_context.input
            elif left_context.input is None and left_context.storage is not None:
                all_context.storage = left_context.storage+"["+right_context.value+"]"
                all_context.value = all_context.storage
            elif left_context.input is None and left_context.storage is None:
                pass
            else:
                raise Exception("input and storage are both not None for {self.ir}")
            self._deal_with_write(self.ir.lvalue, all_context)
        elif isinstance(self.ir, InternalCall) or isinstance(self.ir, LibraryCall):
            function = self.ir.function
            arguments_contexts = []
            for i, argument in enumerate(self.ir.arguments):
                arguments_contexts[i] = argument.context["abstract"]
            all_paths = ContractWalker.enter_function(function, arguments_contexts)
            return all_paths
        elif isinstance(self.ir, Return):
            pass
        elif isinstance(self.ir, NewStructure):
            context = AbstractContext([], [], [], [], [])
            for argument in self.ir.arguments:
                context.input.append(argument["abstract"].input)
                context.storage.append(argument["abstract"].storage)
                context.input_taints.append(argument["abstract"].input_taints)
                context.storage_taints.append(argument["abstract"].storage_taints)
                context.value.append(argument["abstract"].value)
            self._deal_with_write(self.ir.lvalue, context)
        elif isinstance(self.ir, Member):
            if isinstance(self.ir.variable_left.type, UserDefinedType):
                if isinstance(self.ir.variable_left.type.type, Structure):
                    left_context = self._deal_with_read(self.ir.variable_left)
                    index = self.get_index_from_structure(self.ir.variable_right.name, self.ir.variable_left.type.type)
                    # 处理结构体变量可能之前没展开的情况
                    input_context = None
                    if left_context.input is not None:
                        if isinstance(left_context.input, list):
                            input_context = left_context.input[index]
                        else:
                            input_context = left_context.input+"."+self.ir.variable_right.name
                    storage_context = None
                    if left_context.storage is not None:
                        if isinstance(left_context.storage, list):
                            storage_context = left_context.storage[index]
                        else:
                            storage_context = left_context.storage+"."+self.ir.variable_right.name
                    input_taints = set()
                    if left_context.input_taints is not None:   
                        if isinstance(left_context.input_taints, list):
                            input_taints = left_context.input_taints[index]
                        else:
                            input_taints = left_context.input_taints
                    storage_taints = set()
                    if left_context.storage_taints is not None:
                        if isinstance(left_context.storage_taints, list):
                            storage_taints = left_context.storage_taints[index]
                        else:
                            storage_taints = left_context.storage_taints
                    value = None
                    if left_context.value is not None:
                        if isinstance(left_context.value, list):
                            value = left_context.value[index]
                        else:
                            value = left_context.value+"."+self.ir.variable_right.name
                    context = AbstractContext(input_context, storage_context, input_taints, storage_taints, value)
                    self._deal_with_write(self.ir.lvalue, context)
            else:
                raise Exception(f"Member is not a structure variable: {self.ir.variable_left.name}")
        elif isinstance(self.ir, Assignment):
            context = self._deal_with_read(self.ir.rvalue)
            self._deal_with_write(self.ir.lvalue, context)
        elif isinstance(self.ir, Binary):
            left_context = self._deal_with_read(self.ir.variable_left)
            right_context = self._deal_with_read(self.ir.variable_right)
            context = AbstractContext(None, None, left_context.input_taints | right_context.input_taints, left_context.storage_taints | right_context.storage_taints, left_context.value+self.ir.type_str+right_context.value)
            self._deal_with_write(self.ir.lvalue, context)
        elif isinstance(self.ir, TypeConversion):
            pass
        elif isinstance(self.ir, HighLevelCall):
            context = AbstractContext(None, None, set(), set(), None)
            arguments = ""
            for argument in self.ir.arguments:
                argument_context = self._deal_with_read(argument)
                context.storage_taints = context.storage_taints | argument_context.storage_taints
                context.input_taints = context.input_taints | argument_context.input_taints
                arguments = arguments + argument_context.value + ","

            destination_context = self._deal_with_read(self.ir.destination)
            context.storage_taints = context.storage_taints | destination_context.storage_taints
            context.input_taints = context.input_taints | destination_context.input_taints
            context.value = destination_context.value+"."+self.ir.function_name.name+"("+arguments+")"
            self._deal_with_write(self.ir.lvalue, context)
        elif isinstance(self.ir, Condition):
            pass
        elif isinstance(self.ir, SolidityCall):
            context = AbstractContext(None, None, set(), set(), None)
            arguments = ""
            for argument in self.ir.arguments:
                argument_context = self._deal_with_read(argument)
                context.storage_taints = context.storage_taints | argument_context.storage_taints
                context.input_taints = context.input_taints | argument_context.input_taints
                arguments = arguments + argument_context.value + ","
            context.value = self.ir.function.name+"("+arguments+")"



        return []
            

    def get_index_from_structure(self, variable_name, type):
        for i, elem in enumerate(type.elems_ordered):
            if elem.name == variable_name:
                return i
        raise Exception(f"Index not found for {variable_name} in {type.name}")


    def _deal_with_read(self, variable):
        if "abstract" not in variable.context or variable.context["abstract"] is None:
            if isinstance(variable, SolidityVariableComposed):
                return AbstractContext(variable.name, None, set(variable.name), set(), variable.name)
            elif isinstance(variable, StateVariable) and (variable.is_immutable or variable.is_constant):
                return AbstractContext(None, None, set(), set(), variable.name)
            else:
                raise Exception(f"Abstract context not found for {variable.name}")
        return variable.context["abstract"]
        


    def _deal_with_read_of_solidityvariablevomposed(self):
        pass

    def _deal_with_read_of_rvalue(self, rvalue, context):
        pass


    def _deal_with_write(self, lvalue, context):
        lvalue.context["abstract"] = context
        self.lvalues.append(lvalue)
        
    def contintue_internal_call(self, return_variables):
        if return_variables is not None:
            if isinstance(self.ir.lvalue, TemporaryVariable):
                return_context = self._deal_with_read(return_variables[0])
                self.ir.lvalue.context["abstract"]  = return_context

    def close(self):
        for lvalue in self.lvalues:
            lvalue.context["abstract"] = None