#!/usr/bin/env python3

import argparse
import sys
import networkx as nx
from calculator_headers import memoize, is_path_to_filepath, MAX_DISTANCE

graph = nx.DiGraph()


@memoize
def find_nodes(name: str):
    global graph
    n_name = '"{%s}"' % name
    return [n for n, d in graph.nodes(data=True) if n_name in d.get("label", "")]


def calculate_distance(name: str, targets: list, outfile):
    global graph
    distance = -1
    for node in find_nodes(name):
        d = 0.0
        i = 0
        for target in targets:
            try:
                shortest = nx.dijkstra_path_length(graph, node, target)
                d += 1.0 / (1.0 + shortest)
                i += 1
            except nx.NetworkXNoPath:
                distance = -2
                pass
        if d != 0 and (distance < 0 or distance > i / d):
            distance = i / d

    if distance == -2:
        distance = MAX_DISTANCE
    if distance != -1:
        outfile.write(name)
        outfile.write(",")
        outfile.write(str(distance))
        outfile.write("\n")


def main():
    global graph
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--dotfile",
        type=is_path_to_filepath,
        required=True,
        help="The dot file of call graph",
    )
    parser.add_argument(
        "-t",
        "--targets",
        type=is_path_to_filepath,
        required=True,
        help="The file containing target functions",
    )
    parser.add_argument(
        "-n",
        "--names",
        type=is_path_to_filepath,
        required=True,
        help="The file containing function names",
    )
    parser.add_argument(
        "-o",
        "--outfile",
        type=str,
        required=True,
        help="The output file containing call graph distances",
    )

    args = parser.parse_args()

    graph = nx.DiGraph(nx.drawing.nx_pydot.read_dot(args.dotfile))

    targets = []
    with open(args.targets, "r") as file:
        for line in file.readlines():
            line = line.strip()
            for target in find_nodes(line):
                targets.append(target)

    if len(targets) == 0:
        print("There is no target function", file=sys.stderr)
        sys.exit(1)

    with open(args.outfile, "w") as outfile, open(args.names, "r") as infile:
        for line in infile.readlines():
            calculate_distance(line.strip(), targets, outfile)


if __name__ == "__main__":
    main()
