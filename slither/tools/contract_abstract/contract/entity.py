from slither.core.solidity_types.elementary_type import ElementaryType
from slither.core.solidity_types.array_type import ArrayType
from slither.core.solidity_types.mapping_type import MappingType
from slither.core.solidity_types.user_defined_type import UserDefinedType
from slither.core.declarations.structure_contract import StructureContract
from eth_abi import decode, encode
from eth_utils import keccak
from slither.tools.read_storage.utils import coerce_type
from slither.tools.read_storage.read_storage import SlitherReadStorage


class Entity:
    def __init__(self, address, contract, contract_info, storage_meta={}):
        self.address = address
        self.contract = contract
        self.storage_name_to_statevariable = {}
        self.statevariable_to_storage_name = {}
        self.contract_info = contract_info
        self.storage_meta = storage_meta
        if self.storage_meta == {}:
            self.get_storage_meta() 

    def get_address(self):
        return self.address

    def get_storage_meta(self):
        if self.storage_meta != {}:
            return self.storage_meta
        entities= {}

        for storage in self.contract.storage_variables_ordered:
            entity= {}
            # 获取其类型信息
            type_structure = self._get_type_structure(storage.type)
            for x in type_structure:
                entity[x] = type_structure[x]
            # 获取其storage slot信息
            entity["storageInfo"] = self._get_storage_slot(storage)
            entities[storage.name] = entity
            self.storage_name_to_statevariable[storage.name] = storage
            self.statevariable_to_storage_name[storage] = storage.name
            

        self.storage_meta = entities
        return entities

    # 获取storage的slot信息, storage_name使用基于storage_meta的表示
    def get_storage_slot_info(self, storage):
        parsed_expr = Entity.parse_expr(storage)
        if parsed_expr["name"] not in self.storage_meta:
            raise Exception(f"Field {parsed_expr['name']} not found in meta: {self.storage_meta}")
        else:
            slot_info = self.storage_meta[parsed_expr["name"]]["storageInfo"]
            slot_info, type_info = self.get_storage_slot_info_from_expr(parsed_expr, slot_info, self.storage_meta[parsed_expr["name"]])
            return slot_info, type_info

    def get_storage_value(self, slot_info, type):
        slot = slot_info["slot"]
        offset = slot_info["offset"]
        slot = int.to_bytes(slot,32,byteorder="big")
        value_bytes = bytes(self.contract_info.w3.eth.get_storage_at(self.address, slot)).rjust(32, bytes(1))
        value = self.contract_info.read_storage.convert_value_to_type(value_bytes, type["dataMeta"]["size"]*8, offset, type["dataType"])
        return value


    @staticmethod
    def get_storage_slot_info_from_expr(parsed_expr, slot_info, meta): 
        if meta["dataType"] == "struct":
            base_slot = slot_info["slot"] 
            if slot_info["offset"] > 0:
                base_slot += 1     
            field_name = parsed_expr["field"]["name"]
            add_slot, offset, index = Entity.get_slot_info_for_structure(meta, field_name)
            slot = base_slot + add_slot
            if index != -1:
                return Entity.get_storage_slot_info_from_expr(parsed_expr["field"], {"slot": slot, "offset": offset}, meta["dataMeta"]["fields"][index]["type"])
            else:
                raise Exception(f"Field {field_name} not found in struct {meta['dataMeta']['name']}")
        elif meta["dataType"] == "staticArray" or meta["dataType"] == "dynamicArray":
            array_index = int(parsed_expr["index"]["name"])
            if array_index < 0 or array_index >= meta["dataMeta"]["length"]:
                raise Exception(f"Array index {array_index} out of range for array {meta['dataMeta']['name']}")
            else:
                base_slot = slot_info["slot"] 
                if slot_info["offset"] > 0:
                    base_slot += 1 
                slot = keccak(base_slot)
                element_type = meta["dataMeta"]["elementType"]
                if element_type["dataType"] == "struct":
                    struct_slot, struct_offset, struct_index = Entity.get_slot_info_for_structure(element_type, "")
                    slot_int = int.from_bytes(slot, "big") + array_index*struct_slot
                    return Entity.get_storage_slot_info_from_expr(parsed_expr["index"], {"slot": slot_int, "offset": 0}, meta["dataMeta"]["elementType"])
                elif element_type["dataType"] == "staticArray":
                    raise Exception(f"Unimplemented type: {element_type['dataType']} in staticArray")
                elif element_type["dataType"] == "dynamicArray":
                    raise Exception(f"Unimplemented type: {element_type['dataType']} in dynamicArray")
                elif element_type["dataType"] == "mapping":
                    raise Exception(f"Unimplemented type: {element_type['dataType']} in mapping")
                else:
                    slot_int = int.from_bytes(slot, "big") + array_index #TODO: 先不考虑bytes、string或者其他的当元素少于256位从而在本slot中的情况
                    return {"slot": slot_int, "offset": 0}, meta["dataMeta"]["elementType"]      
        elif meta["dataType"] == "mapping":
            key = parsed_expr["index"]["name"]
            key_type = meta["dataMeta"]["key"]["dataType"]
            assert key_type not in ["struct", "mapping", "dynamicArray", "staticArray"]
            if "int" in key_type:  # without this eth_utils encoding fails
                key = int(key)
            key = coerce_type(key_type, key)

            base_slot = slot_info["slot"] 
            if slot_info["offset"] > 0:
                base_slot += 1 
            slot_bytes = keccak(encode([key_type, "uint256"], [key, base_slot]))
            slot_int = int.from_bytes(slot_bytes, "big")
            return Entity.get_storage_slot_info_from_expr(parsed_expr["index"], {"slot": slot_int, "offset": 0}, meta["dataMeta"]["value"])
        else:
            return slot_info, meta

    @staticmethod
    def get_slot_info_for_structure(meta, field_name):
        slot = 0
        offset = 0
        start_offset = 0
        assert meta["dataType"] == "struct"
        index = -1
        for field in meta["dataMeta"]["fields"]:
            index += 1
            field_type =field["type"]["dataType"]
            if field_type == "struct":
                if field["name"] == field_name:
                    if offset > 0:
                        return (slot+1, 0, index)
                    else:
                        return (slot, 0, index)
                else:
                    add_slot, _, _ = Entity.get_slot_info_for_structure(field["type"], "")
                    slot = slot + add_slot
                    offset = 0
            elif field_type == "staticArray" or field_type == "dynamicArray" or field_type == "mapping":
                if field["name"] == field_name:
                    if offset > 0:
                        return (slot+1, 0, index)
                    else:
                        return (slot, 0, index)
                else:
                    slot = slot + 1
                    offset = 0
            else:
                size = field["type"]["dataMeta"]["size"]*8
                if size > (256 - offset):
                    slot += 1
                    if field["name"] == field_name:
                        return (slot, 0, index) 
                    offset = size                            
                else:
                    if field["name"] == field_name:
                        return (slot, offset, index)
                    offset += size 
        if offset > 0:
            return (slot+1, 0, -1)
        else:
            return (slot, 0, -1)

            
    def _deal_with_bitmap_type(self, type):
        pass

    def _get_type_structure(self, type):
        if isinstance(type, ElementaryType):
            return {"dataType": type.type, "dataMeta": {"size": type.storage_size[0]}}
            
        elif isinstance(type, ArrayType):
            if type.is_dynamic_array:
                #TODO: 动态数组
                raise Exception(f"Dynamic array type: {type}")
            elif type.is_fixed_array:
                type_json = {}
                type_json["dataType"] = "staticArray"
                data_meta = {}
                data_meta["length"] = int(type.length.value)
                element_type = self._get_type_structure(type.type)
                data_meta["elementType"] = element_type
                type_json["dataMeta"] = data_meta
                return type_json
            else:
                raise Exception(f"Unknown array type: {type}")
        elif isinstance(type, MappingType):
            type_json = {}
            type_json["dataType"] = "mapping"
            data_meta = {}
            data_meta["key"] = self._get_type_structure(type.type_from)
            data_meta["value"] = self._get_type_structure(type.type_to)
            type_json["dataMeta"] = data_meta
            return type_json
        elif isinstance(type, UserDefinedType):
            return self._get_type_structure(type.type)
        elif isinstance(type, StructureContract):
            type_json = {}
            type_json["dataType"]  = "struct"
            data_meta = {}
            data_meta["name"] = type.name
            fields = []
            for field in type.elems_ordered:
                field_json = {}
                field_json["name"] = field.name
                field_json["type"] = self._get_type_structure(field.type)
                fields.append(field_json)
            data_meta["fields"] = fields
            type_json["dataMeta"] = data_meta
            return type_json
        else:
            raise Exception(f"Unknown type: {type}")
    
    def _get_storage_slot(self, storage):
        slot_info = self.contract.compilation_unit.storage_layout_of(self.contract, storage) 
        slot = slot_info[0]
        offset = slot_info[1]
        return {"slot": slot, "offset": offset}

    def get_field_from_name(self, name, meta):
        parsed_expr = Entity.parse_expr(name)
        if parsed_expr["name"] not in meta:
            raise Exception(f"Field {parsed_expr['name']} not found in meta: {meta}")
        else:
            return self.get_field_from_expr(parsed_expr, meta[parsed_expr["name"]])

    def get_field_from_expr(self, parsed_expr, meta):
        if parsed_expr is not None:
            if meta["dataType"] == "mapping":
                if parsed_expr["index"] is not None:
                    return self.get_field_from_expr(parsed_expr["index"], meta["dataMeta"]["value"])
                else:
                    return meta
            elif meta["dataType"] == "struct":
                if parsed_expr["field"] is not None:
                    for field in meta["dataMeta"]["fields"]:
                        if field["name"] == parsed_expr["field"]["name"]:
                            return self.get_field_from_expr(parsed_expr["field"], field["type"])
                else:
                    return meta
            elif meta["dataType"] == "staticArray":
                raise Exception(f"Unimplemented type: {meta['dataType']}")
            elif meta["dataType"] == "dynamicArray":
                raise Exception(f"Unimplemented type: {meta['dataType']}")
            else:
                return meta
        else:
            return meta
            
    @staticmethod
    def parse_expr(expr: str):
        if expr.startswith(".") or expr.startswith("["):
            raise Exception(f"Invalid expression: {expr}")
        is_brack, is_dot, next_start = Entity.find_next_elem(expr, 0)
        if is_brack:
            return {"name": expr[0:next_start], "index": Entity.parse_expr_internal(expr[next_start:]), "field": None}
        elif is_dot:
            return {"name": expr[0:next_start], "index": None, "field": Entity.parse_expr_internal(expr[next_start:])}
        else:
            return {"name": expr[0:next_start], "index": None, "field": None}
    
    @staticmethod
    def expr_to_string(expr_obj):
        """
        将解析出的表达式对象转换回字符串
        Args:
            expr_obj: 由parse_expr解析出的表达式对象，格式为{"name": str, "index": object, "field": object}
        Returns:
            str: 转换后的字符串表达式
        """
        if expr_obj is None:
            return ""
        
        # 如果expr_obj是字符串（简单字段名），直接返回
        if isinstance(expr_obj, str):
            return expr_obj
        
        # 如果expr_obj是字典，按照parse_expr的结构处理
        if isinstance(expr_obj, dict):
            result = expr_obj["name"]
            
            # 处理index部分
            if expr_obj["index"] is not None:
                index_str = Entity.expr_to_string(expr_obj["index"])
                result += f"[{index_str}]"
            
            # 处理field部分
            if expr_obj["field"] is not None:
                field_str = Entity.expr_to_string(expr_obj["field"])
                result += f".{field_str}"
            
            return result
        
        # 其他类型直接转换为字符串
        return str(expr_obj)
    
    @staticmethod
    def parse_expr_internal(expr: str):
        if expr == "":
            return None
        if expr.startswith("."):
            is_brack, is_dot, next_start = Entity.find_next_elem(expr, 1)
            if is_brack:
                return {"name": expr[1:next_start], "index": Entity.parse_expr_internal(expr[next_start:]), "field": None}
            elif is_dot:
                return {"name": expr[1:next_start], "index": None, "field": Entity.parse_expr_internal(expr[next_start:])}
            else:
                return {"name": expr[1:next_start], "index": None, "field": None}
        elif expr.startswith("["):
            closing_pos = Entity.find_matching_bracket(expr, 0)
            name_entity = Entity.parse_expr(expr[1:closing_pos])
            if name_entity["index"] is None and name_entity["field"] is None:
                name_entity = name_entity["name"]
            is_brack, is_dot, next_start = Entity.find_next_elem(expr, closing_pos + 1)
            if is_brack:
                return {"name": name_entity, "index": Entity.parse_expr_internal(expr[next_start:]), "field": None}
            elif is_dot:
                return {"name": name_entity, "index": None, "field": Entity.parse_expr_internal(expr[next_start:])}
            else:
                return {"name": name_entity, "index": None, "field": None}
        else:
            raise Exception(f"Invalid expression: {expr}")

    @staticmethod
    def find_next_elem(expr: str, open_pos=0):
        is_bracket = False
        is_dot = False
        elem_start = len(expr)
        for i in range(open_pos, len(expr)):
            if expr[i] == "[":
                is_bracket = True
                elem_start = i
                break
            elif expr[i] == ".":
                is_dot = True
                elem_start = i
                break
        return is_bracket, is_dot, elem_start

    @staticmethod
    def find_matching_bracket(expr: str, open_pos: int):
        depth = 0
        for i in range(open_pos, len(expr)):
            if expr[i] == "[":
                depth += 1
            elif expr[i] == "]":
                depth -= 1
                if depth == 0:
                    return i
        raise ValueError("Unmatched bracket")

    def get_storage_slot_from_name(self, name):
        parsed_expr = Entity.parse_expr(name)
        pass


    

    






        


        




    
    