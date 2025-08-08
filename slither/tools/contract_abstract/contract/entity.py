from slither.core.solidity_types.elementary_type import ElementaryType
from slither.core.solidity_types.array_type import ArrayType
from slither.core.solidity_types.mapping_type import MappingType
from slither.core.solidity_types.user_defined_type import UserDefinedType
from slither.core.declarations.structure_contract import StructureContract
import re


class Entity:
    def __init__(self, address, contract):
        self.address = address
        self.contract = contract
        self.storage_name_to_statevariable = {}
        self.statevariable_to_storage_name = {}

    def get_address(self):
        return self.address

    def get_storage_meta(self):
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
    def get_storage_slot(self, storage):
        pass

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
                return self.get_field_from_expr(parsed_expr["field"], meta["dataMeta"]["value"])
            elif meta["dataType"] == "struct":
                for field in meta["dataMeta"]["fields"]:
                    if field["name"] == parsed_expr["name"]:
                        return self.get_field_from_expr(parsed_expr["field"], field["type"])
            else:
                raise Exception(f"Unknown type: {meta['dataType']}")
        else:
            return meta
            
    @staticmethod
    def parse_expr(expr: str):
        expr = expr.strip()
        
        # 如果是字段访问 a.b.c
        dot_pos = Entity.find_top_level_dot(expr)
        if dot_pos != -1:
            name_part = expr[:dot_pos]
            field_part = expr[dot_pos+1:]
            return {
                "name": Entity.get_name(name_part),
                "index": Entity.get_index(name_part),
                "field": Entity.parse_expr(field_part)
            }
        
        # 如果是数组访问 a[b]
        if "[" in expr and expr.endswith("]"):
            name_part = expr[:expr.index("[")]
            index_part = expr[expr.index("[")+1:-1]  # 去掉外层 []
            return {
                "name": name_part,
                "index": Entity.parse_expr(index_part),
                "field": None
            }
        
        # 普通标识符
        return {
            "name": expr,
            "index": None,
            "field": None
        }

    @staticmethod
    def get_name(part):
        """获取数组访问前的名字"""
        if "[" in part:
            return part[:part.index("[")]
        return part

    @staticmethod
    def get_index(part):
        """获取数组访问的 index 表达式（递归解析）"""
        if "[" in part:
            index_part = part[part.index("[")+1:-1]
            return Entity.parse_expr(index_part)
        return None

    @staticmethod
    def find_top_level_dot(s):
        """查找不在 [] 内的顶层 . 位置"""
        depth = 0
        for i, ch in enumerate(s):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
            elif ch == "." and depth == 0:
                return i
        return -1

    def get_storage_slot_from_name(self, name):
        parsed_expr = Entity.parse_expr(name)
        pass
    

    

    






        


        




    
    