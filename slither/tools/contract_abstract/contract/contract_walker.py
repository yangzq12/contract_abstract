import logging
from slither.tools.contract_abstract.contract.slitherir_parser import SlitherIRParser
from slither.tools.contract_abstract.contract.context import AbstractContext
from slither.slithir.operations.return_operation import Return
from slither.tools.contract_abstract.contract.node import RemainNode, StartNode, EndNode

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ContractWalker:
    def __init__(self, contract, entity):
        self.contract = contract
        self.entity = entity
        self.bitmaps = set()
        self.parse_functions = set()

    def walk(self):
        for function in self.contract.functions_entry_points:
            arguments_contexts = []
            for parameter in function.parameters:
                arguments_contexts.append(AbstractContext(parameter.name, None, {parameter.name}, set(), parameter.name))
            # 给每个storage的context标记上input和storage，{"input": parmeterName, "storage": storageName, "input_taint": set(parmeterName), "storage_taint": set(storageName)}
            for storage in self.contract.storage_variables_ordered:
                storage.context["abstract"] = AbstractContext(None, storage.name, set(), {storage.name}, storage.name)

            logger.info(f"Walking function: {function.canonical_name}")
            all_paths = []
            ContractWalker.get_all_paths(function.entry_point, [StartNode(function, arguments_contexts)], all_paths)
            # walk a path
            path_id = 0
            all_paths_with_index = []
            for i, path in enumerate(all_paths):
                all_paths_with_index.append((0, path))

            while path_id < len(all_paths_with_index):
                all_paths_with_index, path_id = ContractWalker.walk_path(all_paths_with_index[path_id], self, all_paths_with_index, path_id)
             # 清除每个storage的context
            for storage in self.contract.storage_variables_ordered:
                storage.context["abstract"] = None
        return
        for path_with_index in all_paths_with_index:
            path = path_with_index[1]
            function_path = self.print_function_path(path)
            for i, stack in enumerate(function_path):
                function_set = set()
                for function in stack:
                    function_set.add(function)
                if len(function_set) != len(stack):
                    return stack
        return []
        
    @staticmethod
    def enter_function(start_node):
        logger.debug(f"Enter function: {start_node.function.canonical_name}")
        ContractWalker.deal_with_context_enter(start_node.function.parameters, start_node.arguments_contexts)
        return
    
    @staticmethod
    def exit_function(end_node, return_variables=None):
        logger.debug(f"Exit function: {end_node.function.canonical_name}")
        if end_node.call_operation is not None and return_variables is not None:
            end_node.call_operation.contintue_internal_call(return_variables)
        return
    
    @staticmethod
    def walk_path(path_with_index, walker, all_paths_with_index, path_id):
        start_index = path_with_index[0]
        path = path_with_index[1]
        irs = []
        child_paths = []
        next_start_index = 0
        remain_irs = []
        child_function = None
        # 再接着处理path
        if len(child_paths) == 0:
            for i,node in enumerate(path):
                next_start_index = i+1
                if i < start_index:
                    continue
                if isinstance(node, StartNode):
                    ContractWalker.enter_function(node)
                elif isinstance(node, EndNode):
                    if len(irs) > 0 and isinstance(irs[-1].ir, Return):
                        ContractWalker.exit_function(node, irs[-1].ir.values)
                    else:
                        ContractWalker.exit_function(node)
                else:
                    for j, ir in enumerate(node.irs):
                        slitherir_parser = SlitherIRParser(ir, walker)
                        if j+1 < len(node.irs):
                            remain_irs = node.irs[j+1:]
                        else:
                            remain_irs = []
                        child_paths, child_function = slitherir_parser.parse()
                        if len(child_paths) > 0: # 有新的分支路径需要加入，来自于internalCall和libraryCall
                            irs.append(slitherir_parser)
                            break
                        irs.append(slitherir_parser)
                    if len(child_paths) > 0:
                        break
        # 处理当前产生的child_paths,将其加入到现有的all_paths中
        if len(child_paths) > 0 and child_function is not None:
            new_all_paths_with_index = []
            # 先将之前的所有path加入
            for i in range(0, path_id):
                new_all_paths_with_index.append(all_paths_with_index[i])
            # 将child_paths和当前的path合并
            went_path = []
            for i in range(0, next_start_index):
                went_path.append(path[i])
            filtered_child_paths = []
            if walker.record_function(child_function): # 如果child_function被记录过，则只保留child_paths[0], 否则保留所有child_paths
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
                new_all_paths_with_index.append((next_start_index, new_path))
            # 将之后的所有path加入
            if path_id < len(all_paths_with_index):
                for i in range(path_id+1, len(all_paths_with_index)):
                    new_all_paths_with_index.append(all_paths_with_index[i])
            return new_all_paths_with_index, path_id
        else:
            return all_paths_with_index, path_id+1
    
    def has_repete_function(self, path):
        function_stack = []
        for node in path:
            if isinstance(node, StartNode):
                function_stack.append(node.function.canonical_name)
            elif isinstance(node, EndNode):
                if node.function.canonical_name != function_stack[-1]:
                    raise Exception("Function path is not correct")
                function_stack.pop()
            function_set = set()
            for function in function_stack:
                function_set.add(function)
            if len(function_set) != len(function_stack):
                return function_stack
        return []
            
    
    def record_function(self, function):
        if function.canonical_name not in self.parse_functions:
            self.parse_functions.add(function.canonical_name)
            return False
        return True
        


    @staticmethod
    def get_all_paths(node, path, all_paths, call_operation=None):
        if node is not None:
            path.append(node)
            if len(node.sons) > 0:
                for son in node.sons:
                    if son not in path:
                        ContractWalker.get_all_paths(son, path.copy(), all_paths, call_operation)
            else:
                path.append(EndNode(node.function, call_operation))
                all_paths.append(path)

    # 给每个parament的context标记上input和storage，{"input": [parmeterName], "storage": [storageName]}
    @staticmethod
    def deal_with_context_enter(parameters, arguments_contexts):
        for i, parameter in enumerate(parameters):
            parameter.context["abstract"] = arguments_contexts[i]
            





