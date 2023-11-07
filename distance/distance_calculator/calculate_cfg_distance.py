#!/usr/bin/env python3

import argparse
import networkx as nx
from calculator_headers import (
    memoize,
    is_path_to_filepath,
    MAX_DISTANCE,
    SMALL_MAX_DISTANCE,
    INTRA_CALL_DIST_COEF,
)

graph = nx.DiGraph()


@memoize
def find_nodes(name: str):
    global graph
    n_name = '"{%s:' % name
    return [n for n, d in graph.nodes(data=True) if n_name in d.get("label", "")]


def calculate_distance(name: str, bb_dist: dict, outfile):
    global graph
    if name in bb_dist.keys():
        if bb_dist[name] < SMALL_MAX_DISTANCE:
            out_str = f"{name},{str(INTRA_CALL_DIST_COEF * bb_dist[name])}" + "\n"
            outfile.write(out_str)
            return

    distance = -1
    for node in find_nodes(name):
        d = 0.0
        i = 0
        for t_name, bb_d in bb_dist.items():
            di = 0.0
            ii = 0
            if bb_d > SMALL_MAX_DISTANCE:
                distance = -2
            else:
                for target in find_nodes(t_name):
                    try:
                        shortest = nx.dijkstra_path_length(graph, node, target)
                        di += 1.0 / (1.0 + INTRA_CALL_DIST_COEF * bb_d + shortest)
                        ii += 1
                    except nx.NetworkXNoPath:
                        distance = -2
                        pass
            if ii != 0:
                d += di / ii
                i += 1

        if d != 0 and (distance < 0 or distance > i / d):
            distance = i / d
        if not bb_dist:
            distance = -2

    if distance == -2:
        distance = MAX_DISTANCE
    if distance != -1:
        outfile.write(f"{name},{distance}" + "\n")


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
        "-b",
        "--bbcalls",
        type=is_path_to_filepath,
        required=True,
        help="The file containing BB calls",
    )
    parser.add_argument(
        "-c",
        "--cgdistance",
        type=is_path_to_filepath,
        required=True,
        help="The file containing call graph distances",
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

    ## load distances for call graph
    cg_dist = {}
    with open(args.cgdistance, "r") as file:
        for line in file.readlines():
            chunks = line.strip().split(",")
            cg_dist[chunks[0]] = float(chunks[-1])

    ## find the BB in this CFG which calls other functions
    ## add the function distance to BB distance
    bb_dist = {}
    with open(args.bbcalls, "r") as file:
        for line in file.readlines():
            chunks = line.strip().split(",")
            if find_nodes(chunks[0]):  ## BB in bbcalls
                if chunks[-1] in cg_dist.keys():  ## function in bbcalls
                    if chunks[0] in bb_dist.keys():
                        if bb_dist[chunks[0]] > cg_dist[chunks[-1]]:
                            bb_dist[chunks[0]] = cg_dist[chunks[-1]]
                    else:
                        bb_dist[chunks[0]] = cg_dist[chunks[-1]]

    ## find the BB in this CFG which is target BB
    with open(args.targets, "r") as file:
        for line in file.readlines():
            line = line.strip()
            if find_nodes(line):
                bb_dist[line] = 0

    with open(args.outfile, "w") as outfile, open(args.names, "r") as infile:
        for line in infile.readlines():
            calculate_distance(line.strip(), bb_dist, outfile)


if __name__ == "__main__":
    main()
