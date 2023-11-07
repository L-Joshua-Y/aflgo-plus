#!/usr/bin/env python3

import argparse
import networkx as nx
from pathlib import Path
from calculator_headers import (
    is_path_to_dir,
    is_path_to_filepath,
    MAX_DISTANCE,
    SMALL_MAX_DISTANCE,
    UNSURE_DISTANCE,
    INNER_CALL_DIST_DELTA,
    INTRA_CALL_DIST_COEF,
)

bb_dict = {}
cfg_dict = {}
call_graph = nx.DiGraph()
visited_nodes = set()


def get_func_name_from_label(label: str):
    result = label.strip()
    if result.startswith('"'):
        result = result[1:]
    if result.startswith("{"):
        result = result[1:]
    if result.endswith('"'):
        result = result[:-1]
    if result.endswith("}"):
        result = result[:-1]
    return result


def get_bbname_from_label(label: str):
    result = label.strip()
    if result.startswith('"'):
        result = result[1:]
    if result.startswith("{"):
        result = result[1:]
    if result.endswith('"'):
        result = result[:-1]
    if result.endswith("}"):
        result = result[:-1]
    chunks = result.split(":")
    chunks = chunks[:-1]
    return ":".join(chunks)


def check_if_entry_func(node):
    global call_graph
    if not call_graph.has_node(node) or "label" not in call_graph.nodes[node]:
        return False
    func_name = get_func_name_from_label(f'{call_graph.nodes[node]["label"]}')
    chunks = func_name.split(";")
    if "main" not in chunks[-1]:
        return False
    if chunks[-1] in ["main", "wmain", "_tmain"]:
        return True
    return False


def load_pure_callgraph(fnames: Path, cgdot: Path):
    global call_graph
    call_graph = nx.DiGraph(nx.drawing.nx_pydot.read_dot(cgdot))
    nodes_to_remove = [
        node
        for node, data in call_graph.nodes(data=True)
        if "(unknown)" in get_func_name_from_label(data.get("label", ""))
    ]
    call_graph.remove_nodes_from(nodes_to_remove)


def load_basic_blocks(bbnames: Path, bbcalls: Path, cfg_dist: Path):
    global bb_dict
    with open(bbnames, "r") as file:
        for line in file.readlines():
            bbname = line.strip()
            bb_dict[bbname] = {"dist": UNSURE_DISTANCE, "call": []}

    with open(bbcalls, "r") as file:
        for line in file.readlines():
            chunks = line.strip().split(",")
            if chunks[0] in bb_dict.keys():
                bb_dict[chunks[0]]["call"].append(chunks[-1])
            else:
                bb_dict[chunks[0]] = {"dist": UNSURE_DISTANCE, "call": [chunks[-1]]}

    with open(cfg_dist, "r") as file:
        for line in file.readlines():
            chunks = line.strip().split(",")
            if chunks[0] in bb_dict.keys():
                bb_dict[chunks[0]]["dist"] = float(chunks[-1])
            else:
                bb_dict[chunks[0]] = {"dist": float(chunks[-1]), "call": []}


def find_bb_dist_after_call(call_func_name: str, func_name: str):
    global cfg_dict, bb_dict

    ### unexpected error: the function CFG is lost
    if call_func_name not in cfg_dict.keys() or func_name not in cfg_dict.keys():
        return UNSURE_DISTANCE

    call_func_cfg = nx.DiGraph(cfg_dict[call_func_name])
    result = MAX_DISTANCE
    has_unsure_dist = False
    ### traverse the BB nodes in caller CFG
    for node, data in call_func_cfg.nodes(data=True):
        bbname = get_bbname_from_label(data.get("label", ""))
        ### Find the BB that calls the callee
        if bbname in bb_dict.keys() and func_name in bb_dict[bbname]["call"]:
            cur_bb_dist = MAX_DISTANCE
            ### the caller BB
            if bb_dict[bbname]["dist"] == UNSURE_DISTANCE:
                has_unsure_dist = True
            elif (
                bb_dict[bbname]["dist"] != UNSURE_DISTANCE
                and bb_dict[bbname]["dist"] < SMALL_MAX_DISTANCE
                and result > bb_dict[bbname]["dist"]
            ):
                result = float(bb_dict[bbname]["dist"])
            ### find the neighbors of the caller BB
            for c_node in call_func_cfg.neighbors(node):
                tmp_bbname = get_bbname_from_label(
                    f'{call_func_cfg.nodes[c_node]["label"]}'
                )
                if tmp_bbname != bbname and tmp_bbname in bb_dict.keys():
                    if bb_dict[tmp_bbname]["dist"] == UNSURE_DISTANCE:
                        has_unsure_dist = True
                    else:
                        if result > bb_dict[tmp_bbname]["dist"]:
                            result = float(bb_dict[tmp_bbname]["dist"])
                        if cur_bb_dist > bb_dict[tmp_bbname]["dist"]:
                            cur_bb_dist = float(bb_dict[tmp_bbname]["dist"])
            if (
                bb_dict[bbname]["dist"] == UNSURE_DISTANCE
                or bb_dict[bbname]["dist"] > SMALL_MAX_DISTANCE
            ) and cur_bb_dist < SMALL_MAX_DISTANCE:
                bb_dict[bbname]["dist"] = cur_bb_dist + INNER_CALL_DIST_DELTA
    if result > SMALL_MAX_DISTANCE and has_unsure_dist:
        return UNSURE_DISTANCE
    else:
        return result


def add_single_call(node, dotfiles_dir: Path):
    """Handle a node in call graph within a BFS process"""
    global call_graph, cfg_dict, bb_dict

    ### add CFG to dict
    if not call_graph.has_node(node) or "label" not in call_graph.nodes[node]:
        return False
    func_name = get_func_name_from_label(f'{call_graph.nodes[node]["label"]}')
    if func_name not in cfg_dict.keys():
        cfg_file = dotfiles_dir / f"cfg.{func_name.replace('/', ')')}.dot"
        if cfg_file.exists() is False or cfg_file.is_file() is False:
            ## print(f" Warning: failed to find {cfg_file}")
            return False
        else:
            cfg_dict[func_name] = nx.DiGraph(nx.drawing.nx_pydot.read_dot(cfg_file))

    ### find parent nodes
    min_distance = MAX_DISTANCE
    has_predecessor = False
    has_unsure_dist = False
    for p_node in call_graph.predecessors(node):
        if p_node in visited_nodes:
            has_predecessor = True
            call_func_name = get_func_name_from_label(
                f'{call_graph.nodes[p_node]["label"]}'
            )
            tmp_distance = find_bb_dist_after_call(call_func_name, func_name)
            if tmp_distance == UNSURE_DISTANCE:
                has_unsure_dist = True
            elif min_distance > tmp_distance:
                min_distance = tmp_distance

    ### entry function
    if has_predecessor is False and check_if_entry_func(node):
        return True
    ### unreachable distance
    if has_predecessor is True and min_distance > SMALL_MAX_DISTANCE:
        return True

    ### add distances to current CFG
    func_cfg = nx.DiGraph(cfg_dict[func_name])
    for node, data in func_cfg.nodes(data=True):
        bbname = get_bbname_from_label(f'{data.get("label", "")}')
        if bbname in bb_dict.keys():
            ### modify the previous distance only when the previous distance is special value
            if (
                bb_dict[bbname]["dist"] == UNSURE_DISTANCE
                or bb_dict[bbname]["dist"] > SMALL_MAX_DISTANCE
            ):
                if not has_predecessor:
                    bb_dict[bbname]["dist"] = UNSURE_DISTANCE
                elif min_distance > SMALL_MAX_DISTANCE:
                    if has_unsure_dist:
                        bb_dict[bbname]["dist"] = UNSURE_DISTANCE
                else:
                    bb_dict[bbname]["dist"] = min_distance + INTRA_CALL_DIST_COEF
    return True


def bfs_call_graph(source, dotfiles_dir: Path):
    global call_graph, visited_nodes, bb_dict, cfg_dict
    queue = [source]
    while queue:
        node = queue.pop(0)
        if node not in visited_nodes:
            if add_single_call(node, dotfiles_dir):
                visited_nodes.add(node)
                neighbors = list(call_graph.neighbors(node))
                queue.extend(neighbors)


def add_distances(dotfiles_dir: Path):
    global call_graph, visited_nodes, bb_dict, cfg_dict
    for node, in_degree in call_graph.in_degree():
        if in_degree == 0:
            if check_if_entry_func(node):
                bfs_call_graph(node, dotfiles_dir)


def write_cfg_distances(cfg_dist: Path):
    global bb_dict
    with open(cfg_dist, "w+") as file:
        for key in bb_dict.keys():
            file.write(f'{key},{float(bb_dict[key]["dist"])}' + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cfgdir",
        required=True,
        type=is_path_to_dir,
        help="The directory containing CFG dot files",
    )
    parser.add_argument(
        "--cgdot",
        required=True,
        type=is_path_to_filepath,
        help="The dot file of call graph",
    )
    parser.add_argument(
        "--cgdistance",
        required=True,
        type=is_path_to_filepath,
        help="The distance file of call graph",
    )
    parser.add_argument(
        "--cfgdistance",
        required=True,
        type=is_path_to_filepath,
        help="The distance file for CFGs",
    )
    parser.add_argument(
        "--fnames",
        required=True,
        type=is_path_to_filepath,
        help="The file containing function names",
    )
    parser.add_argument(
        "--bbnames",
        required=True,
        type=is_path_to_filepath,
        help="The file containing BB names",
    )
    parser.add_argument(
        "--bbcalls",
        required=True,
        type=is_path_to_filepath,
        help="The file containing BB calls",
    )

    args = parser.parse_args()

    load_pure_callgraph(args.fnames, args.cgdot)

    load_basic_blocks(args.bbnames, args.bbcalls, args.cfgdistance)

    add_distances(args.cfgdir)

    write_cfg_distances(args.cfgdistance)


if __name__ == "__main__":
    main()
