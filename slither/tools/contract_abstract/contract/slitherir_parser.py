from slither.slithir.operations.index import Index
from slither.slithir.operations.init_array import InitArray
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
from slither.slithir.operations.unpack import Unpack
from slither.slithir.operations.event_call import EventCall
from slither.slithir.operations.new_array import NewArray
from slither.slithir.operations.new_elementary_type import NewElementaryType
from slither.slithir.operations.new_contract import NewContract
from slither.slithir.operations.length import Length
from slither.slithir.operations.unary import Unary

from slither.core.variables.state_variable import StateVariable
from slither.core.variables.local_variable import LocalVariable

from slither.core.declarations.solidity_variables import SolidityVariableComposed
from slither.core.declarations.structure import Structure
from slither.core.declarations.structure_contract import StructureContract
from slither.core.declarations.contract import Contract

from slither.slithir.variables.temporary import TemporaryVariable
from slither.slithir.variables.reference import ReferenceVariable
from slither.slithir.variables.tuple import TupleVariable
from slither.slithir.variables.constant import Constant

from slither.tools.contract_abstract.contract.context import AbstractContext

from slither.core.solidity_types.user_defined_type import UserDefinedType



class SlitherIRParser:
    def __init__(self, ir, contract_walker):
        self.ir = ir
        self.contract_walker = contract_walker
        self.lvalues = []

    def parse(self):
        if isinstance(self.ir, Index):
            left_context = self._deal_with_read(self.ir.variable_left)
            right_context = self._deal_with_read(self.ir.variable_right)
            all_context = AbstractContext(None, None, set(), set(), None)
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
            input_taints = set()
            if left_context.input_taints is not None:   
                if isinstance(left_context.input_taints, list):
                    input_taints = left_context.input_taints[index]
                else:
                    for input_taint in left_context.input_taints:
                        input_taints.add(input_taint)
            all_context.input_taints = input_taints| right_context.input_taints
            storage_taints = set()
            if left_context.storage_taints is not None:
                if isinstance(left_context.storage_taints, list):
                    storage_taints = left_context.storage_taints[index]
                else:
                    for storage_taint in left_context.storage_taints:
                        storage_taints.add(storage_taint+"["+right_context.value+"]")
            all_context.storage_taints = storage_taints| right_context.storage_taints
            self._deal_with_write(self.ir.lvalue, all_context)
        elif isinstance(self.ir, InternalCall) or isinstance(self.ir, LibraryCall):
            function = self.ir.function
            arguments_contexts = []
            for argument in self.ir.arguments:
                argument_context = self._deal_with_read(argument)
                arguments_contexts.append(argument_context)
            all_paths = self.contract_walker.enter_function(function, arguments_contexts)
            return all_paths
        elif isinstance(self.ir, Return):
            pass
        elif isinstance(self.ir, NewStructure):
            context = AbstractContext([], [], [], [], [])
            for argument in self.ir.arguments:
                argument_context = self._deal_with_read(argument)
                context.input.append(argument_context.input)
                context.storage.append(argument_context.storage)
                context.input_taints.append(argument_context.input_taints)
                context.storage_taints.append(argument_context.storage_taints)
                context.value.append(argument_context.value)
            self._deal_with_write(self.ir.lvalue, context)
        elif isinstance(self.ir, Member):
            if isinstance(self.ir.variable_left, Contract):
                context = AbstractContext(None, None, set(), set(), None)
                context_left = self._deal_with_read(self.ir.variable_left)
                context_right = self._deal_with_read(self.ir.variable_right)
                if context_left.input is not None:
                    if isinstance(context_left.input, str):
                        context.input = context_left.input+"."+self.ir.variable_right.name
                    else:
                        raise Exception("Contract context left input is not a string")
                if context_left.storage is not None:
                    if isinstance(context_left.storage, str):
                        context.storage = context_left.storage+"."+self.ir.variable_right.name
                    else:
                        raise Exception("Contract context left strorage is not a string")
                if isinstance(context_left.input_taints, set):
                    for e in context_left.input_taints:
                        context.input_taints.add(e)
                else:
                    raise Exception("Contract context left input_taints is not a set")
                if isinstance(context_left.storage_taints, set):
                    for e in context_left.storage_taints:
                        context.storage_taints.add(e)
                else:
                    raise Exception("Contract context left storage_taints is not a set")
                if context_left.value is not None:
                    context.value = context_left.value+"."+self.ir.variable_right.name
                self._deal_with_write(self.ir.lvalue, context)
            elif isinstance(self.ir.variable_left.type, UserDefinedType):
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
                            for input_taint in left_context.input_taints:
                                input_taints.add(input_taint)
                    storage_taints = set()
                    if left_context.storage_taints is not None:
                        if isinstance(left_context.storage_taints, list):
                            storage_taints = left_context.storage_taints[index]
                        else:
                            for storage_taint in left_context.storage_taints:
                                storage_taints.add(storage_taint+"."+self.ir.variable_right.name)
                    value = None
                    if left_context.value is not None:
                        if isinstance(left_context.value, list):
                            value = left_context.value[index]
                        else:
                            value = left_context.value+"."+self.ir.variable_right.name
                    context = AbstractContext(input_context, storage_context, input_taints, storage_taints, value)
                    self._deal_with_write(self.ir.lvalue, context)
                    # 如果是reference，需要对reference所指向的也进行处理，因为指向的可能不一定是字段级别，因此需要特别处理
                    lvalue = self.ir.lvalue
                    if isinstance(lvalue, ReferenceVariable) and lvalue.points_to is not None:
                        points_to = lvalue.points_to
                        points_to_origin = lvalue.points_to_origin
                        if points_to == points_to_origin: # 说明只有一层引用
                            if isinstance(points_to.type, UserDefinedType):
                                if isinstance(points_to.type.type, Structure):
                                    for i, elem in enumerate(points_to.type.type.elems_ordered):
                                        if elem.name == self.ir.variable_right.name:
                                            lvalue.context["points_to"] = i # 说明是结构体中的第i个字段
                                else:
                                    raise Exception(f"Points to is not Structure: {points_to.name}")
                            else:
                                raise Exception(f"Points to is not UserDefinedType: {points_to.name}")
                        else:
                            raise Exception(f"ReferenceVariable has more than one layer of reference: {lvalue.name}")
                elif isinstance(self.ir.variable_left.type.type, Contract):
                    context = AbstractContext(None, None, set(), set(), None)
                    context_left = self._deal_with_read(self.ir.variable_left)
                    context_right = self._deal_with_read(self.ir.variable_right)
                    if context_left.input is not None:
                        if isinstance(context_left.input, str):
                            context.input = context_left.input+"."+self.ir.variable_right.name
                        else:
                            raise Exception("Contract context left input is not a string")
                    if context_left.storage is not None:
                        if isinstance(context_left.storage, str):
                            context.storage = context_left.storage+"."+self.ir.variable_right.name
                        else:
                            raise Exception("Contract context left strorage is not a string")
                    if isinstance(context_left.input_taints, set):
                        for e in context_left.input_taints:
                            context.input_taints.add(e)
                    else:
                        raise Exception("Contract context left input_taints is not a set")
                    if isinstance(context_left.storage_taints, set):
                        for e in context_left.storage_taints:
                            context.storage_taints.add(e)
                    else:
                        raise Exception("Contract context left storage_taints is not a set")
                    if context_left.value is not None:
                        context.value = context_left.value+"."+self.ir.variable_right.name
                    self._deal_with_write(self.ir.lvalue, context)
                else:
                    raise Exception(f"Member is not a Structure variable: {self.ir.variable_left.name}")
            else:
                raise Exception(f"Member is not a UserDefinedType variable: {self.ir.variable_left.name}")
        elif isinstance(self.ir, Assignment):
            lvalue = self.ir.lvalue
            context = self._deal_with_read(self.ir.rvalue)
            self._deal_with_write(lvalue, context)
            # 对reference指向的值也进行处理
            if isinstance(lvalue, ReferenceVariable) and lvalue.points_to is not None:
                if "points_to" not in lvalue.context: # 说明是直接指向
                    self._deal_with_write(lvalue.points_to, context)
                else: # 说明是指向字段
                    index = lvalue.context["points_to"]
                    points_to = lvalue.points_to
                    if "abstract" not in points_to.context:
                        points_to.context["abstract"] = AbstractContext(None, None, set(), set(), None)
                    points_to_context = points_to.context["abstract"]
                    if points_to_context.input is not None:
                        if isinstance(points_to_context.input, list):
                            points_to_context.input[index] = context.input
                        else:
                            origin_input = points_to_context.input
                            points_to_context.input = []
                            for i, e in enumerate(points_to.type.type.elems_ordered): #当前只考虑是结构体的情况
                                if i == index:
                                    points_to_context.input.append(context.input)
                                else:
                                    points_to_context.input.append(origin_input+"."+e.name)
                    else:
                        points_to_context.input = []
                        for i, e in enumerate(points_to.type.type.elems_ordered): #当前只考虑是结构体的情况
                            if i == index:
                                points_to_context.input.append(context.input)
                            else:
                                points_to_context.input.append(None)
                    if points_to_context.storage is not None:
                        if isinstance(points_to_context.storage, list):
                            points_to_context.storage[index] = context.storage
                        else:
                            origin_storage = points_to_context.storage
                            points_to_context.storage = []
                            for i, e in enumerate(points_to.type.type.elems_ordered): #当前只考虑是结构体的情况
                                if i == index:
                                    points_to_context.storage.append(context.storage)
                                else:
                                    points_to_context.storage.append(origin_storage+"."+e.name)
                    else:
                        points_to_context.storage = []
                        for i, e in enumerate(points_to.type.type.elems_ordered): #当前只考虑是结构体的情况
                            if i == index:
                                points_to_context.storage.append(context.storage)
                            else:
                                points_to_context.storage.append(None)
                    if points_to_context.input_taints is not None:
                        if isinstance(points_to_context.input_taints, list):
                            points_to_context.input_taints[index] = context.input_taints
                        else:
                            origin_input_taints = points_to_context.input_taints
                            points_to_context.input_taints = []
                            for i, e in enumerate(points_to.type.type.elems_ordered): #当前只考虑是结构体的情况
                                if i == index:
                                    points_to_context.input_taints.append(context.input_taints)
                                else:
                                    points_to_context.input_taints.append(origin_input_taints)
                    else:
                        points_to_context.input_taints = []
                        for i, e in enumerate(points_to.type.type.elems_ordered): #当前只考虑是结构体的情况
                            if i == index:
                                points_to_context.input_taints.append(context.input_taints)
                            else:
                                points_to_context.input_taints.append(None)
                    if points_to_context.storage_taints is not None:
                        if isinstance(points_to_context.storage_taints, list):
                            points_to_context.storage_taints[index] = context.storage_taints
                        else:
                            origin_storage_taints = points_to_context.storage_taints
                            points_to_context.storage_taints = []
                            for i, e in enumerate(points_to.type.type.elems_ordered): #当前只考虑是结构体的情况
                                if i == index:
                                    points_to_context.storage_taints.append(context.storage_taints)
                                else:
                                    points_to_context.storage_taints.append(origin_storage_taints)
                    else:
                        points_to_context.storage_taints = []
                        for i, e in enumerate(points_to.type.type.elems_ordered): #当前只考虑是结构体的情况
                            if i == index:
                                points_to_context.storage_taints.append(context.storage_taints)
                    if points_to_context.value is not None:
                        if isinstance(points_to_context.value, list):
                            points_to_context.value[index] = context.value
                        else:
                            origin_value = points_to_context.value
                            points_to_context.value = []
                            for i, e in enumerate(points_to.type.type.elems_ordered): #当前只考虑是结构体的情况
                                if i == index:
                                    points_to_context.value.append(context.value)
                                else:
                                    points_to_context.value.append(origin_value+"."+e.name)
                    else:
                        points_to_context.value = []
                        for i, e in enumerate(points_to.type.type.elems_ordered): #当前只考虑是结构体的情况
                            if i == index:
                                points_to_context.value.append(context.value)
                            else:
                                points_to_context.value.append(None)
        elif isinstance(self.ir, Binary):
            left_context = self._deal_with_read(self.ir.variable_left)
            right_context = self._deal_with_read(self.ir.variable_right)
            context = AbstractContext(None, None, left_context.input_taints | right_context.input_taints, left_context.storage_taints | right_context.storage_taints, "("+left_context.value+")"+self.ir.type_str+"("+right_context.value+")")
            self._deal_with_write(self.ir.lvalue, context)
        elif isinstance(self.ir, TypeConversion):
            lvalue = self.ir.lvalue
            context = self._deal_with_read(self.ir.variable)
            self._deal_with_write(lvalue, context)
        elif isinstance(self.ir, HighLevelCall):
            context = AbstractContext(None, None, set(), set(), None)
            arguments = ""
            for i, argument in enumerate(self.ir.arguments):
                argument_context = self._deal_with_read(argument)
                if isinstance(argument_context.storage_taints, list): # TODO: 只处理一层list
                    for x in argument_context.storage_taints:
                        context.storage_taints = context.storage_taints | x
                else:
                    context.storage_taints = context.storage_taints | argument_context.storage_taints
                if isinstance(argument_context.input_taints, list): # TODO: 只处理一层list
                    for x in argument_context.input_taints:
                        context.input_taints = context.input_taints | x
                else:
                    context.input_taints = context.input_taints | argument_context.input_taints
                if i == 0:
                    arguments = arguments + str(argument_context.value)
                else:
                    arguments = arguments + "," + str(argument_context.value)

            destination_context = self._deal_with_read(self.ir.destination)
            context.storage_taints = context.storage_taints | destination_context.storage_taints
            context.input_taints = context.input_taints | destination_context.input_taints
            context.value = destination_context.value+"."+self.ir.function_name.name+"("+arguments+")"
            return_context = AbstractContext([], [], [], [], [])
            if isinstance(self.ir.lvalue, TupleVariable):
                for i in self.ir.lvalue.type:
                    return_context.input.append(context.input)
                    return_context.storage.append(context.storage)
                    return_context.input_taints.append(context.input_taints)
                    return_context.storage_taints.append(context.storage_taints)
                    return_context.value.append(context.value)
            else:
                return_context = context
            self._deal_with_write(self.ir.lvalue, return_context)
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
            self._deal_with_write(self.ir.lvalue, context)
        elif isinstance(self.ir, Unpack):
            tuple_context = self._deal_with_read(self.ir.tuple)
            context = AbstractContext(tuple_context.input[self.ir.index], tuple_context.storage[self.ir.index], tuple_context.input_taints[self.ir.index], tuple_context.storage_taints[self.ir.index], tuple_context.value[self.ir.index])
            self._deal_with_write(self.ir.lvalue, context)
        elif isinstance(self.ir, EventCall):
            pass
        elif isinstance(self.ir, Length):
            value_context = self._deal_with_read(self.ir.value)
            input_context = None
            if value_context.input is not None and isinstance(value_context.input, str):
               input_context = value_context.input+".length"
            storage_context = None
            if value_context.storage is not None and isinstance(value_context.storage, str):
                storage_context = value_context.storage+".length"
            value = None
            if value_context.value is not None and isinstance(value_context.value, str):
                value = value_context.value+".length"
            context = AbstractContext(input_context, storage_context, value_context.input_taints, value_context.storage_taints, value)
            self._deal_with_write(self.ir.lvalue, context)
        elif isinstance(self.ir, NewArray):
            pass
        elif isinstance(self.ir, InitArray):
            pass
        elif isinstance(self.ir, NewElementaryType):
            context = AbstractContext(None, None, set(), set(), None)
            self._deal_with_write(self.ir.lvalue, context)
        elif isinstance(self.ir, NewContract):
            pass
        elif isinstance(self.ir, Unary):
            lvalue = self.ir.lvalue
            context = self._deal_with_read(self.ir.rvalue)
            context.value =self.ir.type.value + "(" + context.value + ")"
            self._deal_with_write(lvalue, context)
        else:
            raise Exception(f"IR not supported: {self.ir}")
        return []
            

    def get_index_from_structure(self, variable_name, type):
        for i, elem in enumerate(type.elems_ordered):
            if elem.name == variable_name:
                return i
        raise Exception(f"Index not found for {variable_name} in {type.name}")


    def _deal_with_read(self, variable):
        if "abstract" not in variable.context or variable.context["abstract"] is None:
            if isinstance(variable, SolidityVariableComposed):
                return AbstractContext(variable.name, None, {variable.name}, set(), variable.name)
            elif isinstance(variable, StateVariable) and (variable.is_immutable or variable.is_constant):
                return AbstractContext(None, None, set(), set(), variable.name)
            elif isinstance(variable, LocalVariable) and variable.location == "memory": #临时申请的memroy变量，在没有初始化之前是没有任何值的
                return AbstractContext(None, None, set(), set(), None)
            elif isinstance(variable, Constant):
                return AbstractContext(None, None, set(), set(), variable.name)
            elif isinstance(variable, Contract):
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
            if isinstance(self.ir.lvalue, TupleVariable):
                context = AbstractContext([], [], [], [], [])
                for r in return_variables:
                    return_context = self._deal_with_read(r)
                    context.input.append(return_context.input)
                    context.storage.append(return_context.storage)
                    context.input_taints.append(return_context.input_taints)
                    context.storage_taints.append(return_context.storage_taints)
                    context.value.append(return_context.value)
                self.ir.lvalue.context["abstract"] = context


    def close(self):
        for lvalue in self.lvalues:
            lvalue.context["abstract"] = None