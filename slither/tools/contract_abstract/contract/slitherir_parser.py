from slither.slithir.operations.index import Index
from slither.slithir.operations.init_array import InitArray
from slither.slithir.operations.member import Member
from slither.slithir.operations.new_structure import NewStructure
from slither.slithir.operations.assignment import Assignment
from slither.slithir.operations.binary import Binary, BinaryType
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
from slither.slithir.operations.unary import Unary, UnaryType
from slither.slithir.operations.codesize import CodeSize
from slither.slithir.operations.delete import Delete
from slither.slithir.operations.low_level_call import LowLevelCall

from slither.core.variables.state_variable import StateVariable
from slither.core.variables.local_variable import LocalVariable

from slither.core.declarations.solidity_variables import SolidityVariableComposed
from slither.core.declarations.structure import Structure
from slither.core.declarations.structure_contract import StructureContract
from slither.core.declarations.contract import Contract
from slither.core.declarations.solidity_variables import SolidityVariable
from slither.core.declarations.enum_contract import EnumContract

from slither.slithir.variables.temporary import TemporaryVariable
from slither.slithir.variables.reference import ReferenceVariable
from slither.slithir.variables.tuple import TupleVariable
from slither.slithir.variables.constant import Constant

from slither.tools.contract_abstract.contract.context import AbstractContext

from slither.core.solidity_types.user_defined_type import UserDefinedType
from slither.core.solidity_types.elementary_type import ElementaryType

from slither.tools.contract_abstract.contract.node import StartNode, EndNode, RemainNode
import z3
import re
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SlitherIRParser:
    def __init__(self, ir, contract_walker):
        self.ir = ir
        self.walker = contract_walker
        self.lvalues = []

    def parse(self, path, path_index):
        if self.ir.node.function.name == "setReserveFactor":
            pass
        if hasattr(self.ir, "lvalue"):
            # 记录写的storage
            self.record_write_storage(self.ir.lvalue)
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
            if path_index+1 < len(path) and isinstance(path[path_index+1], StartNode): # 说明是已经展开过的函数，那么就跳过
                if path[path_index+1].function.canonical_name == function.canonical_name:
                    return [], self.ir, True
                else:
                    raise Exception(f"Internal function call has no match: {function.canonical_name}")
            all_paths = []
            self.walker.get_all_paths(function.entry_point, [StartNode(function, arguments_contexts)], all_paths, self)
            return all_paths, self.ir, False
        elif isinstance(self.ir, Return):
            self.parse_bitmap(self.ir)
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
            elif isinstance(self.ir.variable_left, EnumContract):
                left_context = self._deal_with_read(self.ir.variable_left)
                context = AbstractContext(None, None, left_context.input_taints, left_context.storage_taints, left_context.value+"."+self.ir.variable_right.name)
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
                        if points_to == points_to_origin or "abstract" in points_to.context: # 说明只有一层引用或者我们只需要处理一层
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

            right_context = self._deal_with_read(self.ir.rvalue)
            if hasattr(lvalue, "location") and lvalue.location == "storage":
                if "abstract" in lvalue.context and lvalue.context["abstract"] is not None:
                    left_context = self._deal_with_read(lvalue)
                    if left_context.storage is not None:
                        right_context.storage = left_context.storage
            elif isinstance(lvalue, ReferenceVariable) and lvalue.points_to is not None and hasattr(lvalue.points_to, "location") and lvalue.points_to.location == "storage":
                left_context = self._deal_with_read(lvalue)
                if left_context.storage is not None:
                    right_context.storage = left_context.storage
            self._deal_with_write(lvalue, right_context)
            self._deal_with_reference(lvalue, right_context)
            self.parse_bitmap(self.ir)
        elif isinstance(self.ir, Binary):
            left_context = self._deal_with_read(self.ir.variable_left)
            right_context = self._deal_with_read(self.ir.variable_right)
            if isinstance(self.ir.lvalue, ReferenceVariable) and self.ir.lvalue == self.ir.variable_left: # 说明是自加、自减等类似的运算
                context = AbstractContext(left_context.input, left_context.storage, left_context.input_taints | right_context.input_taints, left_context.storage_taints | right_context.storage_taints, "("+left_context.value+")"+self.ir.type_str+"("+right_context.value+")")
                # context = AbstractContext(left_context.input, left_context.storage, left_context.input_taints | right_context.input_taints, left_context.storage_taints | right_context.storage_taints, "("+left_context.value[len(left_context.value)-50:]+")"+self.ir.type_str+"("+right_context.value[len(right_context.value)-50:]+")")
            else:
                if left_context.value is None or right_context.value is None:
                    context = AbstractContext(None, None, left_context.input_taints | right_context.input_taints, left_context.storage_taints | right_context.storage_taints, None)
                else:
                    context = AbstractContext(None, None, left_context.input_taints | right_context.input_taints, left_context.storage_taints | right_context.storage_taints, "("+left_context.value+")"+self.ir.type_str+"("+right_context.value+")")
                    # context = AbstractContext(None, None, left_context.input_taints | right_context.input_taints, left_context.storage_taints | right_context.storage_taints, "("+left_context.value[len(left_context.value)-50:]+")"+self.ir.type_str+"("+right_context.value[len(right_context.value)-50:]+")")
            self._deal_with_write(self.ir.lvalue, context)
            self.parse_bitmap(self.ir)
        elif isinstance(self.ir, TypeConversion):
            lvalue = self.ir.lvalue
            context = self._deal_with_read(self.ir.variable)
            self._deal_with_write(lvalue, context)
            # self._parse_address_type(self.ir.variable, lvalue)
        elif isinstance(self.ir, HighLevelCall):
            context = AbstractContext(None, None, set(), set(), None)
            arguments = ""
            destination = None
            if isinstance(self.ir.destination, StateVariable) and (self.ir.destination.is_constant or self.ir.destination.is_immutable):
                destination = self.ir.destination
            elif self.ir.destination.context["abstract"].storage is not None:
                destination = self.ir.destination.context["abstract"].storage
            if destination is not None:
                if destination not in self.walker.all_hight_level_call_functions:
                    self.walker.all_hight_level_call_functions[destination] = set()
                if isinstance(self.ir.function, StateVariable):
                    self.walker.all_hight_level_call_functions[destination].add(self.ir.function.full_name)
                elif self.ir.function.pure or self.ir.function.view:
                    self.walker.all_hight_level_call_functions[destination].add(self.ir.function.full_name)
            # for i, argument in enumerate(self.ir.arguments):
            #     argument_context = self._deal_with_read(argument)
            #     if isinstance(argument_context.storage_taints, list): # TODO: 只处理一层list
            #         for x in argument_context.storage_taints:
            #             context.storage_taints = context.storage_taints | x
            #     else:
            #         context.storage_taints = context.storage_taints | argument_context.storage_taints
            #     if isinstance(argument_context.input_taints, list): # TODO: 只处理一层list
            #         for x in argument_context.input_taints:
            #             context.input_taints = context.input_taints | x
            #     else:
            #         context.input_taints = context.input_taints | argument_context.input_taints
            #     if i == 0:
            #         arguments = arguments + str(argument_context.value)
            #     else:
            #         arguments = arguments + "," + str(argument_context.value)

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
            # for argument in self.ir.arguments:
            #     argument_context = self._deal_with_read(argument)
            #     context.storage_taints = context.storage_taints | argument_context.storage_taints
            #     context.input_taints = context.input_taints | argument_context.input_taints
            #     if argument_context.value is not None:
            #         arguments = arguments + argument_context.value + ","
            #     else:
            #         arguments = arguments + ","
            context.value = self.ir.function.name+"("+arguments+")"
            self._deal_with_write(self.ir.lvalue, context)
        elif isinstance(self.ir, Unpack):
            tuple_context = self._deal_with_read(self.ir.tuple)
            context = AbstractContext(tuple_context.input[self.ir.index], tuple_context.storage[self.ir.index], tuple_context.input_taints[self.ir.index], tuple_context.storage_taints[self.ir.index], tuple_context.value[self.ir.index])
            self._deal_with_write(self.ir.lvalue, context)
            self._deal_with_reference(self.ir.lvalue, context)
        elif isinstance(self.ir, EventCall):
            for i, argument in enumerate(self.ir.arguments):
                argument_context = self._deal_with_read(argument)
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
            context.value = "newArray"+"("+arguments+")"
            self._deal_with_write(self.ir.lvalue, context)
        elif isinstance(self.ir, InitArray):
            init_value_context = self._deal_with_read(self.ir.init_values[0]) # 默认只有一个init_value
            context = init_value_context.copy()
            self._deal_with_write(self.ir.lvalue, context)
        elif isinstance(self.ir, NewElementaryType):
            context = AbstractContext(None, None, set(), set(), None)
            self._deal_with_write(self.ir.lvalue, context)
        elif isinstance(self.ir, NewContract):
            pass
        elif isinstance(self.ir, Unary):
            lvalue = self.ir.lvalue
            context = self._deal_with_read(self.ir.rvalue)
            if context.value is not None:
                context.value =self.ir.type.value + "(" + context.value + ")" 
                # context.value =self.ir.type.value               
            self._deal_with_write(lvalue, context)
            self._deal_with_reference(self.ir.lvalue, context)
            self.parse_bitmap(self.ir)
        elif isinstance(self.ir, CodeSize):
            value_context = self._deal_with_read(self.ir.value)
            context = AbstractContext(None, None, value_context.input_taints, value_context.storage_taints, value_context.value+".codesize")
            self._deal_with_write(self.ir.lvalue, context)
        elif isinstance(self.ir, Delete):
            pass
        elif isinstance(self.ir, LowLevelCall):
            arguments = ""
            context = AbstractContext(None, None, set(), set(), None)
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
        else:
            raise Exception(f"IR not supported: {self.ir}")
        return [], self.ir, False

    def _parse_address_type(self, variable, lvalue):
        if isinstance(variable, Contract):
            pass # TODO:暂时不处理contract的address类型
        elif isinstance(variable.type, ElementaryType) and variable.type.type == "address":
            context = self._deal_with_read(variable)
            if context.storage is not None and isinstance(context.storage, str):
                meta = self.walker.entity.get_field_from_name(context.storage, self.walker.entity.storage_meta)
                if meta["dataType"] == "address" and ("interface" not in meta["dataMeta"] or meta["dataMeta"]["interface"] is None):
                    if isinstance(lvalue.type, UserDefinedType) and isinstance(lvalue.type.type, Contract):
                        interface_name = lvalue.type.type.name
                        self.walker.interfaces[interface_name] = []
                        for function in lvalue.type.type.functions_declared:
                            self.walker.interfaces[interface_name].append(function.signature_str)
                        meta["dataMeta"]["interface"] = interface_name
                

    def record_write_storage(self, lvalue):
        if (hasattr(lvalue, "location") and lvalue.location == "storage") \
            or (isinstance(lvalue, StateVariable) and lvalue.is_stored) \
            or (isinstance(lvalue, ReferenceVariable) and lvalue.points_to_origin is not None and hasattr(lvalue.points_to_origin, "location") and lvalue.points_to_origin.location == "storage") \
             or (isinstance(lvalue, ReferenceVariable) and lvalue.points_to_origin is not None and hasattr(lvalue.points_to_origin, "is_stored") and lvalue.points_to_origin.is_stored):
                if "abstract" in lvalue.context and lvalue.context["abstract"] is not None:
                    left_context = self._deal_with_read(lvalue)
                    self.record_storage(self.walker.write_storages[self.walker.current_function], left_context)
    @staticmethod
    def clear_context(ir, storages):
        if isinstance(ir, Index):
            SlitherIRParser.clear_abstract(ir.lvalue, storages)
        elif isinstance(ir, InternalCall) or isinstance(ir, LibraryCall):
            pass
        elif isinstance(ir, Return):
            for value in ir.values:
                SlitherIRParser.clear_abstract(value, storages)
        elif isinstance(ir, NewStructure):
            SlitherIRParser.clear_abstract(ir.lvalue, storages)
        elif isinstance(ir, Member):
            SlitherIRParser.clear_abstract(ir.lvalue, storages)
        elif isinstance(ir, Assignment):
            SlitherIRParser.clear_abstract(ir.lvalue, storages)
        elif isinstance(ir, Binary):
            SlitherIRParser.clear_abstract(ir.lvalue, storages)
        elif isinstance(ir, TypeConversion):
            SlitherIRParser.clear_abstract(ir.lvalue, storages)
        elif isinstance(ir, HighLevelCall):
            SlitherIRParser.clear_abstract(ir.lvalue, storages)
        elif isinstance(ir, Condition):
            pass
        elif isinstance(ir, SolidityCall):
            SlitherIRParser.clear_abstract(ir.lvalue, storages)
        elif isinstance(ir, Unpack):
            SlitherIRParser.clear_abstract(ir.lvalue, storages)
        elif isinstance(ir, EventCall):
            pass
        elif isinstance(ir, Length):
            SlitherIRParser.clear_abstract(ir.lvalue, storages)
        elif isinstance(ir, NewArray):
            SlitherIRParser.clear_abstract(ir.lvalue, storages)
        elif isinstance(ir, InitArray):
            SlitherIRParser.clear_abstract(ir.lvalue, storages)
        elif isinstance(ir, NewElementaryType):
            SlitherIRParser.clear_abstract(ir.lvalue, storages)
        elif isinstance(ir, NewContract):
            pass
        elif isinstance(ir, Unary):
            SlitherIRParser.clear_abstract(ir.lvalue, storages)
        elif isinstance(ir, CodeSize):
            SlitherIRParser.clear_abstract(ir.lvalue, storages)
        elif isinstance(ir, Delete):
            pass
        elif isinstance(ir, LowLevelCall):
            SlitherIRParser.clear_abstract(ir.lvalue, storages)
        else:
            raise Exception(f"IR not supported: {ir}")

    @staticmethod
    def clear_abstract(value, storages):
        if value is None or (isinstance(value, StateVariable) and value in storages):
            pass
        else:
            value.context["abstract"] = None

        

    def parse_bitmap(self, ir):
        if isinstance(ir, Binary):
            if ir.type in {BinaryType.AND, BinaryType.OR, BinaryType.LEFT_SHIFT, BinaryType.RIGHT_SHIFT}: # 说明是位运算
                self._deal_with_constant_bitmap(ir.variable_left)
                self._deal_with_constant_bitmap(ir.variable_right)
                if "bitmap" in ir.variable_left.context and "bitmap" in ir.variable_right.context:
                    if ir.type == BinaryType.AND:
                        ir.lvalue.context["bitmap"] = ir.variable_left.context["bitmap"] & ir.variable_right.context["bitmap"]
                    elif ir.type == BinaryType.OR:
                        ir.lvalue.context["bitmap"] = ir.variable_left.context["bitmap"] | ir.variable_right.context["bitmap"]
                    elif ir.type == BinaryType.LEFT_SHIFT:
                        ir.lvalue.context["bitmap"] = ir.variable_left.context["bitmap"] << ir.variable_right.context["bitmap"]
                    elif ir.type == BinaryType.RIGHT_SHIFT:
                        ir.lvalue.context["bitmap"] = ir.variable_left.context["bitmap"] >> ir.variable_right.context["bitmap"]
            elif ir.type == BinaryType.EQUAL or ir.type == BinaryType.NOT_EQUAL:
                self._deal_with_constant_bitmap(ir.variable_left)
                self._deal_with_constant_bitmap(ir.variable_right)
                if "bitmap" in ir.variable_left.context and "bitmap" in ir.variable_right.context:
                    if ir.type == BinaryType.EQUAL:
                        ir.lvalue.context["bitmap"] = ir.variable_left.context["bitmap"] == ir.variable_right.context["bitmap"]
                    elif ir.type == BinaryType.NOT_EQUAL:
                        ir.lvalue.context["bitmap"] = ir.variable_left.context["bitmap"] != ir.variable_right.context["bitmap"]
            else:
                self._deal_with_constant_bitmap(ir.variable_left)
                self._deal_with_constant_bitmap(ir.variable_right)
                if "bitmap" in ir.variable_left.context and "bitmap" in ir.variable_right.context:
                    if ir.type == BinaryType.ADDITION:
                        ir.lvalue.context["bitmap"] = ir.variable_left.context["bitmap"] + ir.variable_right.context["bitmap"]
            if "bitmap" in ir.lvalue.context and ir.lvalue.context["abstract"].storage is not None and isinstance(ir.lvalue.context["abstract"].storage, str) and isinstance(ir.lvalue.type, ElementaryType):
                self.walker.bitmaps.add((ir.node.function.full_name, z3.simplify(ir.lvalue.context["bitmap"]))) # 用ir.node.function.full_name来记录
        elif isinstance(ir, Unary):
            if ir.type == UnaryType.TILD:
                self._deal_with_constant_bitmap(ir.rvalue)
                if "bitmap" in ir.rvalue.context:
                    ir.lvalue.context["bitmap"] = ~ir.rvalue.context["bitmap"]
                if "bitmap" in ir.lvalue.context and ir.lvalue.context["abstract"].storage is not None and isinstance(ir.lvalue.context["abstract"].storage, str) and isinstance(ir.lvalue.type, ElementaryType):
                    self.walker.bitmaps.add((ir.node.function.full_name, z3.simplify(ir.lvalue.context["bitmap"])))
        elif isinstance(ir, Return):
            for value in ir.values:
                if "bitmap" in  value.context:
                    name = ""
                    if isinstance(value.context["abstract"].value, str):
                        if "MASK" in value.context["abstract"].value: #TODO: 硬编码
                            masks = re.split('[()]', value.context["abstract"].value)
                            for mask in masks:
                                if "MASK" in mask:
                                    name = mask.replace("MASK", "")
                        self.walker.bitmaps.add((name, z3.simplify(value.context["bitmap"]))) #用valualbe的value带mask的情况
        elif isinstance(ir, Assignment):
            if "bitmap" in ir.rvalue.context:
                ir.lvalue.context["bitmap"] = ir.rvalue.context["bitmap"]
                if ir.lvalue.context["abstract"].storage is not None and isinstance(ir.lvalue.context["abstract"].storage, str) and isinstance(ir.lvalue.type, ElementaryType):
                    self.walker.bitmaps.add((ir.node.function.full_name, z3.simplify(ir.lvalue.context["bitmap"])))

                
    
    def _deal_with_constant_bitmap(self, variable):
        if "bitmap" in variable.context:
            return
        elif isinstance(variable, StateVariable) and (variable.is_immutable or variable.is_constant):
            if variable.initialized:
                ir = variable.node_initialization.irs[0] #只处理直接赋值常量的形式
                if isinstance(ir, Assignment) and isinstance(ir.rvalue, Constant) and isinstance(ir.rvalue.type, ElementaryType):
                    ir.lvalue.context["bitmap"] = z3.BitVecVal(ir.rvalue.value, 256) # 默认ir.rvalue.type.size都是256
        elif "abstract" in variable.context and variable.context["abstract"].storage is not None and isinstance(variable.context["abstract"].storage, str) and isinstance(variable.type, ElementaryType):
            variable.context["bitmap"] = z3.BitVec(variable.context["abstract"].storage, 256)
        elif isinstance(variable, Constant) and isinstance(variable.type, ElementaryType):
            variable.context["bitmap"] = z3.BitVecVal(variable.value, 256)


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
                self._record_constant(variable)
                return AbstractContext(None, None, set(), set(), variable.name)               
            elif isinstance(variable, LocalVariable) and variable.location == "memory": #临时申请的memroy变量，在没有初始化之前是没有任何值的
                return AbstractContext(None, None, set(), set(), "$unknown$")
            elif isinstance(variable, Constant):
                return AbstractContext(None, None, set(), set(), variable.name)
            elif isinstance(variable, Contract):
                return AbstractContext(None, None, set(), set(), variable.name)
            elif isinstance(variable, SolidityVariable):
                return AbstractContext(None, None, set(), set(), variable.name)
            elif isinstance(variable, LocalVariable) and variable.location == "default" and isinstance(variable.type, ElementaryType):
                return AbstractContext(None, None, set(), set(), "0")
            elif isinstance(variable, EnumContract):
                return AbstractContext(None, None, set(), set(), variable.name)
            elif isinstance(variable, TemporaryVariable):
                return AbstractContext(None, None, set(), set(), "$unknown$")
            else:
                # return AbstractContext(None, None, set(), set(), "$unknown$")
                raise Exception(f"Abstract context not found for {variable.name}")
        # 记录读的storage
        self.record_storage(self.walker.read_storages[self.walker.current_function], variable.context["abstract"])
        return variable.context["abstract"]

    def _record_constant(self, variable):
        if self._filter_constant(variable):
            return
        canonical_name = variable.canonical_name
        function_name = canonical_name.split(".")[0]
        constant_name = canonical_name.split(".")[1]  
        interface = None
        if isinstance(variable.type.type, Contract):
            constant_type = "address"
            constant_size = 160
            interface = variable.type.type.name
            self.walker.interfaces[variable.type.type.name] = []
            for function in variable.type.type.functions_declared:
                self.walker.interfaces[variable.type.type.name].append(function.signature_str)
        elif isinstance(variable.type, ElementaryType):
            constant_type = variable.type.type
            constant_size = variable.type.size
        else:
            raise Exception(f"Constant type not supported for {variable.name}")
        constant_value = None
        if variable.initialized:
            ir = variable.node_initialization.irs[0] #只处理直接赋值常量的形式
            if isinstance(ir, Assignment) and isinstance(ir.rvalue, Constant) and isinstance(ir.rvalue.type, ElementaryType):   
                constant_value = ir.rvalue.value
        if function_name not in self.walker.constants:
            self.walker.constants[function_name] = []
        for constant in self.walker.constants[function_name]:
            if constant["name"] == constant_name:
                return
        self.walker.constants[function_name].append({"name": constant_name, "value": constant_value, "type": {"dataType": constant_type, "dataMeta": {"size": constant_size, "interface": interface}}})

    def _filter_constant(self, variable): # TODO: 先简单进行过滤不必要的用于内部服务的constant
        if "MASK" in variable.name or "BIT_POSITION" in variable.name:
            return True
        else:
            return False

    def _deal_with_write(self, lvalue, context):
        if isinstance(lvalue, StateVariable) and (lvalue.is_immutable or lvalue.is_constant):
            self._record_constant(lvalue)
        if lvalue is not None:
            lvalue.context["abstract"] = context
            self.lvalues.append(lvalue)
            


    def record_storage(self, collect, context):
        self._recursive_add_storage(collect, context.storage)

    def _recursive_add_storage(self, collect, storage):
        if storage is not None and isinstance(storage, str):
            collect.add(storage)
        elif isinstance(storage, list):
            for e in storage:
                self._recursive_add_storage(collect, e)

    def _deal_with_reference(self, lvalue, context):
        # 对reference指向的值也进行处理
        if isinstance(lvalue, ReferenceVariable) and lvalue.points_to is not None:
            if "points_to" not in lvalue.context: # 说明是直接指向
                self._deal_with_write(lvalue.points_to, context)
            else: # 说明是指向字段
                index = lvalue.context["points_to"]
                points_to = lvalue.points_to
                if "abstract" not in points_to.context or points_to.context["abstract"] is None:
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
                # self.ir.lvalue.context["abstract"] = context
                self._deal_with_write(self.ir.lvalue, context)
                self._deal_with_reference(self.ir.lvalue, context)


    def close(self):
        for lvalue in self.lvalues:
            lvalue.context["abstract"] = None