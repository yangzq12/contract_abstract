import logging
from slither.tools.contract_abstract.contract.slitherir_parser import SlitherIRParser
from slither.tools.contract_abstract.contract.context import AbstractContext
from slither.slithir.operations.return_operation import Return

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class ContractWalker:
    def __init__(self, contract, entity):
        self.contract = contract
        self.entity = entity

    def walk(self):
        for function in self.contract.functions_entry_points:
            arguments_contexts = []
            for parameter in function.parameters:
                arguments_contexts.append(AbstractContext(parameter.name, None, {parameter.name}, set(), parameter.name))
            # 给每个storage的context标记上input和storage，{"input": parmeterName, "storage": storageName, "input_taint": set(parmeterName), "storage_taint": set(storageName)}
            for storage in self.contract.storage_variables_ordered:
                storage.context["abstract"] = AbstractContext(None, storage.name, set(), {storage.name}, storage.name)

            logger.info(f"Walking function: {function.canonical_name}")
            all_paths = ContractWalker.enter_function(function, arguments_contexts)
            # walk a path
            for path in all_paths:
                ContractWalker.walk_function_path(function, path, [], self)

             # 清除每个storage的context
            for storage in self.contract.storage_variables_ordered:
                storage.context["abstract"] = None
              
    
    @staticmethod
    def enter_function(function, arguments_contexts):
        logger.debug(f"Enter function: {function.canonical_name}")
        ContractWalker.deal_with_context_enter(function.parameters, arguments_contexts)
        # get all paths
        all_paths = []
        if function.entry_point is not None:
            ContractWalker.get_all_paths(function.entry_point, [], all_paths)

        return all_paths
    
    @staticmethod
    def walk_function_path(function, path, old_remain_irs, walker):
        irs = []
        child_paths = []
        remain_irs = []
        remain_path = []
        # 处理之前path的old_remain_irs中剩余的irs
        for i, ir in enumerate(old_remain_irs):
            slitherir_parser = SlitherIRParser(ir, walker)
            child_paths, child_function = slitherir_parser.parse()
            if len(child_paths) > 0: # 有新的分支路径需要加入，来自于internalCall和libraryCall
                if i+1 < len(old_remain_irs):
                    remain_irs = old_remain_irs[i+1:]
                else:
                    remain_irs = []
                remain_path = path
                irs.append(slitherir_parser)
                break
            irs.append(slitherir_parser)
        # 再接着处理path
        if len(child_paths) == 0:
            for i,node in enumerate(path):
                for j, ir in enumerate(node.irs):
                    slitherir_parser = SlitherIRParser(ir, walker)
                    child_paths, child_function = slitherir_parser.parse()
                    if len(child_paths) > 0: # 有新的分支路径需要加入，来自于internalCall和libraryCall
                        if j+1 < len(node.irs):
                            remain_irs = node.irs[j+1:]
                        else:
                            remain_irs = []
                        if i+1 < len(path):
                            remain_path = path[i+1:]
                        else:
                            remain_path = []
                        irs.append(slitherir_parser)
                        break
                    irs.append(slitherir_parser)
                if len(child_paths) > 0:
                    break
        # 处理当前产生的child_paths
        for child_path in child_paths:
            # walk a child path
            return_variables = ContractWalker.walk_function_path(child_function, child_path, [], walker) 
            # deal with the last SlitherIRParse, it must be internalCall or libraryCall
            ir = irs[-1]
            ir.contintue_internal_call(return_variables)
            # continue the parent path
            return_variables = ContractWalker.walk_function_path(function, remain_path, remain_irs, walker)
            return return_variables

        if len(irs) > 0 and isinstance(irs[-1].ir, Return):
            return irs[-1].ir.values
        else:
            return None

    @staticmethod
    def get_all_paths(node, path,all_paths):
        path.append(node)
        if len(node.sons) > 0:
            for son in node.sons:
                if son not in path:
                    ContractWalker.get_all_paths(son, path.copy(), all_paths)
        else:
            all_paths.append(path)

    # 给每个parament的context标记上input和storage，{"input": [parmeterName], "storage": [storageName]}
    @staticmethod
    def deal_with_context_enter(parameters, arguments_contexts):
        for i, parameter in enumerate(parameters):
            parameter.context["abstract"] = arguments_contexts[i]
            





