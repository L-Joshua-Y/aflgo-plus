/**
 * AFLGo-Plus
 *
 * Written by Joshua Yao <joshuayao13@gmail.com>
 */

#ifndef INSTRUMENT_INFO_H_
#define INSTRUMENT_INFO_H_

/* Env specifying the project root directory */
#define AFLGO_PLUS_PROJ_ENV "AFLGO_PLUS_PROJ_ROOT_PATH"

/* Edges in call graph */
#define AFLGO_PLUS_FUNC_EDGES_FILE "FCallEdges.txt"

/* Function names */
#define AFLGO_FUNC_NAMES_FILE "Fnames.txt"

/* Target function(s) */
#define AFLGO_FUNC_TARGETS_FILE "Ftargets.txt"

/* BB names */
#define AFLGO_BB_NAMES_FILE "BBnames.txt"

/* BB names along with callee */
#define AFLGO_BB_CALLS_FILE "BBcalls.txt"

/* Target BB(s) */
#define AFLGO_BB_TARGETS_FILE "BBtargets.txt"

/* New target BB(s) */
#define AFLGO_BB_TARGETS_NEW_FILE "BBtargets-new.txt"

/* File name of call graph */
#define AFLGO_CALLGRAPH_FILE "callgraph.dot"

/* Directory containing dot files */
#define AFLGO_DOTFILES_DIR "dot-files"

#define MAX_DISTANCE double(__INT32_MAX__)

#define SMALL_MAX_DISTANCE double(__INT32_MAX__ - 2)

#define UNSURE_DISTANCE double(-1.0)

#define MAX_DISTANCE_INT __INT32_MAX__

#endif