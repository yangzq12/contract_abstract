import logging
from slither.tools.contract_abstract.contract.slitherir_parser import SlitherIRParser
from slither.tools.contract_abstract.contract.context import AbstractContext
from slither.slithir.operations.return_operation import Return

logging.basicConfig()
logger = logging.getLogger(__name__)

class ContractWalker:
    def __init__(self, contract, entity):
        self.contract = contract
        self.entity = entity

    def walk(self):
        for function in self.contract.functions_entry_points:
            arguments_contexts = []
            for i, parameter in enumerate(function.parameters):
                arguments_contexts[i] = AbstractContext(parameter.name, None, set(parameter.name), set(), parameter.name)
            # 给每个storage的context标记上input和storage，{"input": parmeterName, "storage": storageName, "input_taint": set(parmeterName), "storage_taint": set(storageName)}
            for storage in self.contract.storage_variables:
                storage.context["abstract"] = AbstractContext(None, storage.name, set(), set(storage.name), storage.name)

            logger.debug(f"Walking function: {function.canonical_name}")
            all_paths = ContractWalker.enter_function(function, arguments_contexts)
            # walk a path
            for path in all_paths:
                ContractWalker.walk_function_path(function, path, [])

             # 清除每个storage的context
            for storage in self.contract.storage_variables:
                storage.context["abstract"] = None
              
    
    @staticmethod
    def enter_function(function, arguments_contexts):
        ContractWalker.deal_with_context_enter(function.parameters, arguments_contexts)
        # get all paths
        all_paths = []
        ContractWalker.get_all_paths(function.entry_point, all_paths)

        return all_paths
    
    @staticmethod
    def walk_function_path(function, path, old_remain_irs):
        irs = []
        for ir in old_remain_irs:
            slitherir_parser = SlitherIRParser(ir)
            child_paths = slitherir_parser.parse()
            if len(child_paths) > 0: # 有新的分支路径需要加入，来自于internalCall和libraryCall
                remain_irs = ir.irs[j+1:]
                remain_path = path[i+1:]
                irs.append(slitherir_parser)
                break
            irs.append(slitherir_parser)

        if len(child_paths) == 0:
            remain_irs = []
            remain_path = []
            for i,node in enumerate(path):
                for j, ir in enumerate(node.irs):
                    slitherir_parser = SlitherIRParser(ir)
                    child_paths = slitherir_parser.parse()
                    if len(child_paths) > 0: # 有新的分支路径需要加入，来自于internalCall和libraryCall
                        remain_irs = node.irs[j+1:]
                        remain_path = path[i+1:]
                        irs.append(slitherir_parser)
                        break
                    irs.append(slitherir_parser)
                if len(child_paths) > 0:
                    break

        for child_path in child_paths:
            # walk a child path
            return_variables = ContractWalker.walk_function_path(function, child_path, [])
            # deal with the last SlitherIRParse, it must be internalCall or libraryCall
            ir = irs[-1]
            ir.contintue_internal_call(return_variables)
            # continue the parent path
            return_variables = ContractWalker.walk_function_path(function, remain_path, remain_irs)
            return return_variables

        if isinstance(irs[-1].ir, Return):
            return irs[-1].ir.values
        else:
            return None

    @staticmethod
    def get_all_paths(node, path,all_paths):
        path.append(node)
        for son in enumerate(node.sons):
            ContractWalker.get_all_paths(son, path.copy(), all_paths)
        all_paths.append(path)

    # 给每个parament的context标记上input和storage，{"input": [parmeterName], "storage": [storageName]}
    @staticmethod
    def deal_with_context_enter(parameters, arguments_contexts):
        for i, parameter in enumerate(parameters):
            parameter.context["abstract"] = arguments_contexts[i]
            





