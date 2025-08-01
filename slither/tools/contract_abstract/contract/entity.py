from slither.core.solidity_types.elementary_type import ElementaryType
from slither.core.solidity_types.array_type import ArrayType
from slither.core.solidity_types.mapping_type import MappingType
from slither.core.solidity_types.user_defined_type import UserDefinedType
from slither.core.declarations.structure_contract import StructureContract

class Entity:
    def __init__(self, address, contract):
        self.address = address
        self.contract = contract

    def get_address(self):
        return self.address

    def get_storage_meta(self):
        entities= {}

        for storage in self.contract.storage_variables_ordered:
            if self.filter_storage(storage):
                entity= {}
                # 获取其类型信息
                entity["type"] = self._get_type_structure(storage.type)
                # 获取其storage slot信息
                entity["storageInfo"] = self._get_storage_slot(storage)
                entities[storage.name] = entity

        self.storage_meta = entities
        return entities

    def filter_storage(self, storage):
        return True

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

    

    






        


        




    
    