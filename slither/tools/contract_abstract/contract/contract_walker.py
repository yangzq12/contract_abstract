import logging
from signal import raise_signal
from slither.tools.contract_abstract.contract.slitherir_parser import SlitherIRParser
from slither.tools.contract_abstract.contract.context import AbstractContext
from slither.slithir.operations.return_operation import Return
from slither.tools.contract_abstract.contract.node import RemainNode, StartNode, EndNode
from slither.core.cfg.node import Node
from slither.core.variables.state_variable import StateVariable
from slither.slithir.variables.constant import Constant
from slither.core.solidity_types.elementary_type import ElementaryType
from slither.slithir.operations.assignment import Assignment
from slither.core.solidity_types.user_defined_type import UserDefinedType
import os
import psutil
import z3
import re
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ContractWalker:
    def __init__(self, contract, entity):
        self.contract = contract
        self.entity = entity
        self.bitmaps = set()
        self.parse_functions = set()
        self.parse_irs = set()
        self.read_storages = {} # 某个function所有的读的storage，key是function的name，value是set(storage_name)
        self.write_storages = {} # 某个function所有的写的storage，key是function的name，value是set(storage_name)
        self.function_write_storage = {} # 某个function所有的写的storage，key是function的name，value是set(storage_name), storage_name精确到字段
        self.constants = {} # 某个合约的常量，key是合约，value是数组，每个元素是{"name": name, "value": value, "type": {"dataType": "uint256", "dataMeta": {"size": 256}}}

        self.current_function = None
        self.interfaces = {} # 某个合约的interface，key是合约，value是interfaces
        self.all_hight_level_call_functions = {} # 是一个detination到funcitons的映射
        self.library_call_functions = {} # 记录所有library call的function
        self.function_returns = {} # 记录所有view类型函数的返回值，key是function的full_name，value是set(storage_name)

        self.utilities = []

    def walk(self):
        for function in self.contract.functions:
            if function in self.contract.functions_entry_points or function.pure:
                self.read_storages[function] = set()
                self.write_storages[function] = set()
                self.current_function = function

                arguments_contexts = []
                arguments_names = ""
                for parameter in function.parameters:
                    arguments_contexts.append(AbstractContext(parameter.name, None, {parameter.name}, set(), parameter.name))
                    arguments_names += parameter.name + ","
                # 给每个storage的context标记上input和storage，{"input": parmeterName, "storage": storageName, "input_taint": set(parmeterName), "storage_taint": set(storageName)}
                for storage in self.contract.storage_variables_ordered:
                    storage.context["abstract"] = AbstractContext(None, storage.name, set(), {storage.name}, storage.name)

                logger.info(f"Walking function: {function.canonical_name}")
                if function.canonical_name == "Pool.setConfiguration(address,DataTypes.ReserveConfigurationMap)" or "flashLoan(" in function.canonical_name:
                    pass
                all_paths = []
                ContractWalker.get_all_paths(function.entry_point, [StartNode(function, arguments_contexts)], all_paths)
                # walk a path
                path_id = 0
                all_paths_with_index = []
                for i, path in enumerate(all_paths):
                    all_paths_with_index.append((0, path))
                while path_id < len(all_paths_with_index):
                    all_paths_with_index, new_path_id = self.walk_path(all_paths_with_index[path_id], self, all_paths_with_index, path_id)
                    if new_path_id > path_id:
                        # 如果是纯函数获取本次的返回值
                        if function.pure or function.view:
                            return_flag = False
                            for node in all_paths_with_index[path_id][1][::-1]:
                                if isinstance(node, Node) or isinstance(node, RemainNode):
                                    ir = node.irs[-1]
                                    if isinstance(ir, Return):
                                        function_name = function.full_name
                                        function_name += "#" + arguments_names + "#"
                                        if function_name not in self.function_returns:
                                            self.function_returns[function_name] = set()
                                        for value in ir.values:
                                            if isinstance(value, StateVariable) and (value.is_constant or value.is_immutable):
                                                self.function_returns[function_name].add(value)
                                            elif "abstract" in value.context and value.context["abstract"].storage is not None:
                                                if isinstance(value.context["abstract"].storage, list):
                                                    for s in value.context["abstract"].storage:
                                                        if s is not None:
                                                            self.function_returns[function_name].add(s)
                                                elif isinstance(value.context["abstract"].storage, str):
                                                    self.function_returns[function_name].add(value.context["abstract"].storage)
                                    return_flag = True
                                    break
                            if not return_flag:
                                if function.entry_point is None:
                                    function_name = function.full_name
                                    function_name += "#" + arguments_names + "#"
                                    if function_name not in self.function_returns:
                                        self.function_returns[function_name] = set()
                                        if isinstance(function.return_type[0], ElementaryType):
                                            self.function_returns[function_name].add("$"+function.name+"$"+function.return_type[0].name) #用$开头标记是public变量的返回值
                                        else:
                                            self.function_returns[function_name].add("$"+function.name+"$"+function.return_type[0].type.name) #用$开头标记是public变量的返回值
                        # 清除本次路径产生的abstract context
                        for node in all_paths_with_index[path_id][1]:
                            if not isinstance(node, StartNode) and not isinstance(node, EndNode):
                                for ir in node.irs:
                                    SlitherIRParser.clear_context(ir, [])
                        # 由于是不同路径，需要对storage重新更新
                        for storage in self.contract.storage_variables_ordered:
                            storage.context["abstract"] = AbstractContext(None, storage.name, set(), {storage.name}, storage.name)
                    path_id = new_path_id
                # 清除函数间可能互相影响的相关状态
            self.parse_irs = set()
        # self.parse_dependencies()
        self.analyse_bitmap()
        self.filter_storage()
        self.parse_utilities()
        self.collect_function_write_storage()
        return

    def walk_path(self, path_with_index, walker, all_paths_with_index, path_id):
        start_index = path_with_index[0]
        path = path_with_index[1]
        irs = []
        child_paths = []
        next_start_index = 0
        remain_irs = []
        call_ir = None
        hop = False

        # 再接着处理path
        for i,node in enumerate(path):
            next_start_index = i+1
            if i < start_index:
                continue
            if isinstance(node, StartNode):
                self.enter_function(node)
            elif isinstance(node, EndNode):
                if len(irs) > 0 and isinstance(irs[-1].ir, Return):
                    self.exit_function(path, i, node, irs[-1].ir.values)
                else:
                    self.exit_function(path, i, node)
            else:
                for j, ir in enumerate(node.irs):
                    slitherir_parser = SlitherIRParser(ir, walker)
                    if j+1 < len(node.irs):
                        remain_irs = node.irs[j+1:]
                    else:
                        remain_irs = []
                    before_memory = ContractWalker.get_current_memory_usage()
                    child_paths, call_ir, hop = slitherir_parser.parse(path, i)
                    after_memory = ContractWalker.get_current_memory_usage()
                    if after_memory-before_memory > 100:
                        logger.info(f"Memory usage: {after_memory-before_memory} MB for {type(ir)}")
                    # 先判断是不是需要跳过后续irs
                    if hop:
                        irs.append(slitherir_parser)
                        break
                    if len(child_paths) > 0: # 有新的分支路径需要加入，来自于internalCall和libraryCall
                        irs.append(slitherir_parser)
                        break
                    irs.append(slitherir_parser)
                if hop:
                    continue
                if len(child_paths) > 0:
                    break
        # 处理当前产生的child_paths,将其加入到现有的all_paths中
        if len(child_paths) > 0 and call_ir is not None:
            new_all_paths_with_index = []
            # 先将之前的所有path加入
            for i in range(0, path_id):
                new_all_paths_with_index.append(all_paths_with_index[i])
            # 将child_paths和当前的path合并
            went_path = []
            for i in range(0, next_start_index):
                went_path.append(path[i])
            filtered_child_paths = []
            if walker.record_ir(call_ir): # 如果child_function被记录过，则只保留child_paths[0], 否则保留所有child_paths
                filtered_child_paths.append(child_paths[0])
            else:
                filtered_child_paths = child_paths
            for child_path in filtered_child_paths:
                new_path = went_path.copy()
                for child_node in child_path:
                    new_path.append(child_node)
                # 将remain_irs加入new_path
                if len(remain_irs) > 0:
                    new_path.append(RemainNode(remain_irs))
                # 将path之后需要继续遍历的node加入new_path
                for i in range(next_start_index, len(path)):
                    new_path.append(path[i])
                if len(new_all_paths_with_index) == path_id:
                    new_all_paths_with_index.append((next_start_index, new_path))
                else:
                    new_all_paths_with_index.append((0, new_path))
            # 将之后的所有path加入
            if path_id < len(all_paths_with_index):
                for i in range(path_id+1, len(all_paths_with_index)):
                    new_all_paths_with_index.append(all_paths_with_index[i])
            return new_all_paths_with_index, path_id
        else:
            return all_paths_with_index, path_id+1

    def parse_utilities(self):
        for function_str in self.function_returns:
            parts = re.split(r'[()]', function_str.split("#")[0])
            function_name = parts[0]
            parameters_types = parts[1].split(",")
            parameters_names = function_str.split("#")[1].split(",")
            parameters = {}
            for i, parameter_type in enumerate(parameters_types):
                if parameter_type != "":
                    parameters[parameters_names[i]] = parameter_type
            returns = []
            for return_value in self.function_returns[function_str]:
                return_info = None
                if isinstance(return_value, StateVariable) and (return_value.is_constant):
                    ir = return_value.node_initialization.irs[0] #只处理直接赋值常量的形式
                    if isinstance(ir, Assignment) and isinstance(ir.rvalue, Constant) and isinstance(ir.rvalue.type, ElementaryType):
                        return_info = {}
                        return_info["value"] = ir.rvalue.value
                        return_info["type"] = ir.rvalue.type.name
                elif isinstance(return_value, str) and return_value.startswith("$"):
                    return_info = {}
                    return_info["value"] = return_value.split("$")[1]
                    return_info["type"] = return_value.split("$")[2]
                elif isinstance(return_value, str):
                    return_info = {}
                    return_info["value"] = return_value
                    meta = self.entity.get_field_from_name(return_value, self.entity.storage_meta)
                    return_info["type"] = meta["dataType"]
                if return_info is not None:
                    returns.append(return_info)
            utility = {
                "function": function_name,
                "parameters": parameters,
                "returns": returns
            }
            self.utilities.append(utility)

    def parse_dependencies(self):
        w3 = self.entity.contract_info.w3
        contract_address = self.entity.address
        for destination in self.all_hight_level_call_functions:
            if isinstance(destination, StateVariable) and destination.is_immutable and destination.node_initialization is None and destination.visibility == "public": # 识别是public的immutatble变量
                return_type = None
                if isinstance(destination.type, UserDefinedType):
                    return_type = "address"
                elif isinstance(destination.type, ElementaryType):
                    return_type = destination.type.name
                else:
                    raise Exception(f"Unsupported return type: {destination.type}")
                # 请求链上数据
                # 配置abi
                abi = [{
                        "inputs": [],
                        "name": destination.name,
                        "outputs": [{"internalType": return_type, "name": "", "type": return_type}],
                        "stateMutability": "view",
                        "type": "function"
                    }]
                # 创建合约对象
                contract = w3.eth.contract(address=contract_address, abi=abi)
                # 调用函数
                return_value = getattr(contract.functions, destination.name)().call()
            elif isinstance(destination, str):
                pass # TODO: 处理


    def analyse_bitmap(self):
        for named_bitmap in self.bitmaps:
            name = self.format_name(named_bitmap[0])
            if name != "":
                bitmap = named_bitmap[1]
                patterns = []
                vars = self.get_vars(bitmap)
                if len(vars) == 1:
                    self.get_bit_pattern_extract(bitmap, patterns)
                    if len(patterns) == 1:
                        var = str(list(vars)[0])
                        meta = self.entity.get_field_from_name(var, self.entity.storage_meta)
                        if "bitmap" not in meta:
                            added_bitmap = {"dataType": "struct", "dataMeta": {"fields": []}}
                            meta["bitmap"] = added_bitmap
                        meta["bitmap"]["dataMeta"]["fields"].append({"name": name, "type": {"dataType": "uint256", "dataMeta": {"size": 256, "offset": (patterns[0])}}})
                    else:
                        logger.debug(f"Unsupported bitmap: {bitmap}")
                elif len(vars) == 2:
                    self.get_bit_pattern_shift(bitmap, patterns)
                    pattern_mode = self.get_pattern_mode(patterns)
                    if pattern_mode == 1:
                        raise Exception("Unsupported bitmap: {bitmap}")
                    elif pattern_mode == 2:
                        var = str(list(vars)[0])
                        meta = self.entity.get_field_from_name(var, self.entity.storage_meta)
                        if "bitmap" not in meta:
                            added_bitmap = {"dataType": "staticArray", "dataMeta": {"length": 128, "elementType": {"dataType": "struct", "dataMeta": {"fields": []}}}}
                            meta["bitmap"] = added_bitmap
                        meta["bitmap"]["dataMeta"]["elementType"]["dataMeta"]["fields"].append({"name": name, "type": {"dataType": "bool", "dataMeta": {"size": 1, "offset": (0)}}})
                    elif pattern_mode == 3:
                        var = str(list(vars)[0])
                        meta = self.entity.get_field_from_name(var, self.entity.storage_meta)
                        if "bitmap" not in meta:
                            added_bitmap = {"dataType": "staticArray", "dataMeta": {"length": 128, "elementType": {"dataType": "struct", "dataMeta": {"fields": []}}}}
                            meta["bitmap"] = added_bitmap
                        meta["bitmap"]["dataMeta"]["elementType"]["dataMeta"]["fields"].append({"name": name, "type": {"dataType": "bool", "dataMeta": {"size": 1, "offset": (1)}}})
                else:
                    raise Exception("Unsupported bitmap: {bitmap}")    
                # print(patterns)

    def filter_storage(self):
        for function in self.read_storages:
            for storage in self.read_storages[function]:
                meta = self.entity.get_field_from_name(storage, self.entity.storage_meta)
                if meta["dataType"] not in ["struct", "staticArray", "mapping"]:
                    meta["read"] = True

    def collect_function_write_storage(self):
        for function in self.write_storages:
            parameters = []
            for parameter in function.parameters:
                parameters.append(parameter.name)
            storage_writes = set()
            for storage in self.write_storages[function]:
                meta = self.entity.get_field_from_name(storage, self.entity.storage_meta)
                # if meta["dataType"] not in ["struct", "staticArray", "mapping", "dynamicArray"]:
                storage_writes.add(storage)
            self.function_write_storage[function.solidity_signature] = {"parameters": parameters, "write_storages": list(storage_writes)}


    @staticmethod
    def get_pattern_mode(patterns):
        pattern_mode = 0 # 记录patter mode， 0表示未识别，1就是连续，2就是隔两个取第一个，3就是隔两个取第二个
        # 识别连续的pattern
        n = len(patterns[1]) # 每连续n个是一个基本元素
        if n > 0:
            for pattern in patterns:
                if len(pattern[1]) == n:
                    pattern_mode = 1
                else:
                    pattern_mode = 0
                    break
        if pattern_mode == 1:
            return pattern_mode
        # 识别隔两个取第一个的pattern
        for pattern in patterns:
            if len(pattern[1]) == 1:
                if pattern[1][0] == pattern[0]*2: #识别0， 2， 4，6， 8
                    pattern_mode = 2
                else:
                    pattern_mode = 0
                    break
        if pattern_mode == 2:
            return pattern_mode
        # 识别隔两个取第二个的pattern
        for pattern in patterns:
            if len(pattern[1]) == 1:
                if pattern[1][0] == pattern[0]*2+1: #识别1， 3， 5， 7， 9
                    pattern_mode = 3
                else:
                    pattern_mode = 0
                    break
        return pattern_mode

    @staticmethod
    def format_name(name):
        formatted_name = ""
        if name.startswith("set"):
            formatted_name = name.replace("set", "").split("(")[0]
        elif name.endswith("_"):
            parts = name.strip('_').lower().split('_')
            formatted_name = parts[0] + ''.join(word.capitalize() for word in parts[1:])
        return formatted_name
    
    def get_bit_pattern_extract(self, expr, bit_patterns):
        new_expr = z3.simplify(expr)
        if new_expr.decl().kind() != z3.Z3_OP_EXTRACT:
            for child in new_expr.children():
                self.get_bit_pattern_extract(child, bit_patterns) 
        else:
            params = new_expr.params()
            bit_patterns.append(params)
    
    def get_bit_pattern_shift(self, expr, bit_patterns):
        data = z3.BitVecVal(0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF, 256)
        shift = 0
        for shift in range(0, 256):
            pattern = []
            shift_var = z3.BitVecVal(shift, 256)
            vars = self.get_vars(expr)
            new_expr = z3.substitute(expr, ((list(vars)[0]), data), ((list(vars)[1]), shift_var))
            result = z3.simplify(new_expr)
            result_str = bin(result.as_long())[2:][::-1]
            for i, char in enumerate(result_str):
                if char == '0':
                   pattern.append(i)
            bit_patterns.append((shift, pattern))

    @staticmethod
    def get_vars(expr):
        result = set()
        def collect(e):
            if z3.is_const(e) and e.decl().kind() == z3.Z3_OP_UNINTERPRETED:
                result.add(e)
            # 否则，如果是表达式，则递归地处理它的每个子节点
            elif z3.is_expr(e):
                for ch in e.children():
                    collect(ch)
        collect(expr)
        return result

    def enter_function(self,start_node):
        logger.debug(f"Enter function: {start_node.function.canonical_name}")
        ContractWalker.deal_with_context_enter(start_node.function.parameters, start_node.arguments_contexts)
        return
    
   
    def exit_function(self,path, index, end_node, return_variables=None):
        logger.debug(f"Exit function: {end_node.function.canonical_name}")
        if end_node.call_operation is not None and return_variables is not None:
            end_node.call_operation.contintue_internal_call(return_variables)
        return    
    
    def record_function(self, function):
        if function.canonical_name not in self.parse_functions:
            self.parse_functions.add(function.canonical_name)
            return False
        return True

    def record_ir(self, ir):
        if ir not in self.parse_irs:
            self.parse_irs.add(ir)
            return False
        return True
    
        
    def get_current_memory_usage():
        """
        获取当前 Python 进程的内存使用量。
        """
        # 获取当前进程的PID
        pid = os.getpid()
        # 通过 PID 获取进程对象
        process = psutil.Process(pid)
        # 获取内存信息
        mem_info = process.memory_info()

        # mem_info.rss 是进程实际使用的物理内存量（常驻内存集）
        # 单位是字节，通常转换为 MB 更易读
        memory_mb = round(mem_info.rss / (1024**2), 2)

        return memory_mb


    @staticmethod
    def get_all_paths(node, path, all_paths, call_operation=None):
        if node is not None:
            path.append(node)
            if len(node.sons) > 0:
                for son in node.sons:
                    if son not in path:
                        ContractWalker.get_all_paths(son, path.copy(), all_paths, call_operation)
                    else:
                        if len(son.sons) > 0: #说明是循环，那么就选择false条件跳出循环，继续遍历
                            path.append(son)
                            ContractWalker.get_all_paths(son.sons[1], path.copy(), all_paths, call_operation)
            else:
                path.append(EndNode(node.function, call_operation))
                all_paths.append(path)
        else:
            path.append(EndNode(path[0].function, None))
            all_paths.append(path)
    
    # 给每个parament的context标记上input和storage，{"input": [parmeterName], "storage": [storageName]}
    @staticmethod
    def deal_with_context_enter(parameters, arguments_contexts):
        for i, parameter in enumerate(parameters):
            parameter.context["abstract"] = arguments_contexts[i].copy()


            





