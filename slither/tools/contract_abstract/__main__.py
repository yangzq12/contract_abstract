"""
Tool to get the business logic for a deployed contract with source code
"""
import argparse
import logging
from crytic_compile import cryticparser, CryticCompile
import json
from slither import Slither
from slither.exceptions import SlitherError
from slither.tools.contract_abstract.onchain.contract_info import ContractInfo
from slither.tools.contract_abstract.contract.entity import Entity
import os

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def parse_args() -> argparse.Namespace:
    """Parse the underlying arguments for the program.
    Returns:
        The arguments for the program.
    """
    parser = argparse.ArgumentParser(
        description="Get the business logic for a deployed contract with source code",
        usage=(
            "\nTo get a contract's abstarct with address and source code:\n"
            + "\tcontract-abstract $ADDRESS $SOURCE\n"
        ),
    )

    parser.add_argument(
        "contract_source",
        help="The deployed contract address if verified on etherscan. Prepend project directory for unverified contracts.",
        nargs="+",
    )

    parser.add_argument("--rpc-url", help="An endpoint for web3 requests.")

    parser.add_argument(
        "--output-path",
        action="store",
        help="Save the result in the output path.",
    )

    parser.add_argument(
        "--silent",
        action="store_true",
        help="Silence log outputs",
    )

    cryticparser.init(parser)

    return parser.parse_args()

# def get_primary_contract(slither, target):
#     # 确认主合约
#     primary_contracts = []
#     for contract in slither.compilation_units[0].contracts:
#         # 抽象合约、接口、libray、未实现的都不是主合约，同时主合约应该是最外层的合约，也就是没被继承的那个
#         if not contract.is_abstract and not contract.is_interface and not contract.is_library and contract.is_fully_implemented and len(contract.derived_contracts) == 0: 
#             primary_contracts.append(contract)
#     if len(primary_contracts) == 0:
#         raise SlitherError(f"No primary contract found for {target}")
#     elif len(primary_contracts) > 1:
#         raise SlitherError(f"Multiple primary contracts found for {target}")
#     return primary_contracts[0]

def get_primary_contract(slither, target, args):
    # 检查主合约是否是代理，如果是代理合约，应该分析的是代理合约所指向的逻辑合约
    if slither.compilation_units[0].crytic_compile_compilation_unit.implementation_address:
        logger.info(f"Proxy mode find for {target}, get logic contract: {slither.compilation_units[0].crytic_compile_compilation_unit.implementation_address}")
        target = slither.compilation_units[0].crytic_compile_compilation_unit.implementation_address
        slither = Slither(target, **vars(args))
        return get_primary_contract(slither, target, args)

    primary_contract_name = slither.compilation_units[0].crytic_compile_compilation_unit.unique_id
    for contract in slither.compilation_units[0].contracts:
        if contract.name == primary_contract_name:
            logger.info(f"Get Primary contract: {contract.name}, for target: {target}")
            return contract, slither, target
    raise SlitherError(f"Primary contract not found for {target}")

def main() -> None:
    args = parse_args()

    if len(args.contract_source) == 2:
        target, source_code = args.contract_source
        slither = Slither(source_code, **vars(args))
    else:
        target = args.contract_source[0]
        slither = Slither(target, **vars(args))

    if args.rpc_url:
        contract_info = ContractInfo(args.rpc_url, slither.contracts)
    else:
        raise SlitherError("RPC url is required")

    # 获取主合约
    primary_contract, slither, target = get_primary_contract(slither, target, args)

    # 获取合约链上的字节码
    # bytecode = contract_info.get_contract_bytecode(target)

    # 获取合约的storage信息
    entity = Entity(target, primary_contract)
    storage_meta_json =entity.get_storage_meta() 

    result = {}
    result[primary_contract.name]={"entities" : storage_meta_json, "address": args.contract_source[0]}

    output_file_name = primary_contract.name + "_meta.json"
    if args.output_path:
        output_file_name = os.path.join(args.output_path, output_file_name)
    # 将storage_meta_json写入到文件中
    with open(output_file_name, "w") as f:
        json.dump(result, f, indent=4)

    logger.info(f"------------END------------")

    
if __name__ == "__main__":
    main()
