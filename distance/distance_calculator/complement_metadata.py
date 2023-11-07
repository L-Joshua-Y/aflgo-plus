#!/usr/bin/env python3
"""
Complement metadata using content generated during compilation
"""

import argparse
import random
import networkx as nx
from pathlib import Path
from calculator_headers import memoize, is_path_to_filepath

call_graph = nx.DiGraph()
fnames_set = set()
bb_dict = dict()
node_bits = 24


@memoize
def get_func_name(simple_name: str):
    global fnames_set
    result = []
    for name in fnames_set:
        if simple_name in name:
            result.append(name)
    return result


def find_nodes(name: str):
    global call_graph
    n_name = '"{%s}"' % name
    return [n for n, d in call_graph.nodes(data=True) if n_name in d.get("label", "")]


def generate_node_name():
    global call_graph
    while True:
        random_number_bit = random.getrandbits(node_bits)
        hex_representation = hex(random_number_bit)
        node_name = f"Node{hex_representation}"
        if not call_graph.has_node(node_name):
            return node_name


def load_all_content(ncgdot: Path, nfnames: Path, nbbcalls: Path, nbbnames: Path):
    global call_graph, fnames_set, bb_dict, node_bits

    call_graph = nx.DiGraph(nx.drawing.nx_pydot.read_dot(ncgdot))
    for node in call_graph.nodes:
        if f"{node}".startswith("Node0x"):
            node_bits = 4 * (len(f"{node}") - len("Node0x"))
        else:
            node_bits = 4 * len(f"{node}")
        break

    with open(nfnames, "r") as file:
        for line in file.readlines():
            fnames_set.add(line.strip())

    with open(nbbcalls, "r") as file:
        for line in file.readlines():
            chunks = line.strip().split(",")
            if chunks[0] not in bb_dict.keys():
                bb_dict[chunks[0]] = [chunks[-1]]
            else:
                bb_dict[chunks[0]].append(chunks[-1])

    with open(nbbnames, "r") as file:
        for line in file.readlines():
            bbname = line.strip()
            if bbname not in bb_dict.keys():
                bb_dict[bbname] = []


def add_bb_calls(pbbcalls: Path):
    global call_graph, fnames_set, bb_dict

    with open(pbbcalls, "r") as file:
        for line in file.readlines():
            chunks = line.strip().split(",")
            if chunks[0] in bb_dict.keys():
                if chunks[-1] not in " ".join(bb_dict[chunks[0]]):
                    names = get_func_name(chunks[-1])
                    if len(names) == 1:
                        bb_dict[chunks[0]].extend(names)


def add_call_edges(pcalledges: Path):
    global call_graph, fnames_set, bb_dict

    with open(pcalledges, "r") as file:
        for line in file.readlines():
            chunks = line.strip().split("->")
            u_nodes = find_nodes(chunks[0])
            if len(u_nodes) > 0:
                v_name = ""
                names = get_func_name(chunks[-1])
                if len(names) == 1:
                    v_name = names[0]
                if len(v_name) > 0:
                    if len(find_nodes(v_name)) == 0:
                        call_graph.add_node(
                            generate_node_name(),
                            label=f'"{{{v_name}}}"',
                            shape="record",
                        )
                    for u_node in u_nodes:
                        for v_node in find_nodes(v_name):
                            if not call_graph.has_edge(u_node, v_node):
                                call_graph.add_edge(u_node, v_node)


def write_content(ncgdot: Path, nbbcalls: Path):
    global call_graph, bb_dict
    with open(ncgdot, "w+") as file:
        nx.nx_pydot.write_dot(call_graph, file)

    with open(nbbcalls, "w+") as file:
        for key in bb_dict.keys():
            for func_name in bb_dict[key]:
                file.write(f"{key},{func_name}" + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pbbcalls",
        type=is_path_to_filepath,
        required=True,
        help="The previous file containing BB calls",
    )
    parser.add_argument(
        "--pcalledges",
        type=is_path_to_filepath,
        required=True,
        help="The previous file containing function call edges",
    )
    parser.add_argument(
        "--nfnames",
        type=is_path_to_filepath,
        required=True,
        help="The current file containing function names",
    )
    parser.add_argument(
        "--nbbcalls",
        type=is_path_to_filepath,
        required=True,
        help="The current file containing BB calls",
    )
    parser.add_argument(
        "--nbbnames",
        type=is_path_to_filepath,
        required=True,
        help="The current file containing BB names",
    )
    parser.add_argument(
        "--ncgdot",
        type=is_path_to_filepath,
        required=True,
        help="The current dot file containing call graph",
    )

    args = parser.parse_args()

    load_all_content(args.ncgdot, args.nfnames, args.nbbcalls, args.nbbnames)

    add_bb_calls(args.pbbcalls)

    add_call_edges(args.pcalledges)

    write_content(args.ncgdot, args.nbbcalls)


if __name__ == "__main__":
    main()
