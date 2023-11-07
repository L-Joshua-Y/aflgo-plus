#!/usr/bin/env python3
"""
Parse call graph and CFGs and calculate distances
"""

import argparse
import os
import sys
import shutil
import atexit
import subprocess
from pathlib import Path
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor

SCRIPT_DIR = Path(__file__).parent

DOTFILES_NAME = "dot-files"
METADATA_NAME = "metadata"
DISTFILES_NAME = "dist-files"
PARSER_DIR_NAME = "bitcode_parser"
CALCULATOR_DIR_NAME = "distance_calculator"
PY_CACHE_DIR_NAME = "__pycache__"

PARSER_NAME = "parse_bitcode"
COM_META_NAME = "complement_metadata.py"
CAL_CG_NAME = "calculate_cg_distance.py"
CAL_CFG_NAME = "calculate_cfg_distance.py"
CAL_SUPPLE_NAME = "calculate_supplement.py"

STEP_LOG_NAME = "steps.log"
CALLGRAPH_NAME = "callgraph.dot"
CG_DISTANCE_NAME = "callgraph.distance.txt"
CFG_DISTANCE_NAME = "cfg.distance.txt"

BBTARGETS_NAME = "BBtargets.txt"
BBTARGETS_NEW_NAME = "BBtargets-new.txt"
BBCALLS_NAME = "BBcalls.txt"
BBNAMES_NAME = "BBnames.txt"
FTARGETS_NAME = "Ftargets.txt"
FNAMES_NAME = "Fnames.txt"
FCALLEDGES_NAME = "FCallEdges.txt"

BIN_DIR = Path()
BIN_NAME = ""
TMP_DIR = Path()
PROJ_ROOT_DIR = Path()
METADATA_DIR = Path()

g_step = -1


def iprint(msg: str):
    print(f"[T] {msg}", file=sys.stdout)


def eprint(msg: str):
    print(f"[E] {msg}", file=sys.stderr)
    sys.exit(1)


def is_path_to_dir(path):
    """Returns Path object when path is an existing directory"""
    p = Path(path)
    if not p.exists():
        raise argparse.ArgumentTypeError(f"'{p}' doesn't exist")
    if not p.is_dir():
        raise argparse.ArgumentTypeError(f"'{p}' is not a directory")
    return p


def merge_dist_files(distfiles_dir: Path, out_file: Path):
    with open(out_file, "w") as ofile:
        for dist_file in distfiles_dir.glob("cfg.*.distance.txt"):
            with open(dist_file, "r") as ifile:
                ofile.write(ifile.read())


def parse_bc():
    ## check parser program binary
    parser_prog = SCRIPT_DIR / PARSER_DIR_NAME / PARSER_NAME
    if parser_prog.exists() is False or parser_prog.is_file() is False:
        eprint(f"Failed to find executable {PARSER_NAME} under {PARSER_DIR_NAME}")
    if not os.access(parser_prog, os.X_OK):
        eprint(f"{parser_prog} is not an executable")

    ## check binaries
    binary = BIN_DIR / f"{BIN_NAME}.0.0.preopt.bc"
    if binary.exists() is False or binary.is_file() is False:
        eprint(f"Failed to find '{binary}'")

    ## check BB target file
    prev_bb_target_file = TMP_DIR / BBTARGETS_NAME
    if prev_bb_target_file.exists() is False or prev_bb_target_file.is_file() is False:
        eprint(f"Failed to find {BBTARGETS_NAME} under {TMP_DIR}")
    if METADATA_DIR.exists():
        shutil.rmtree(METADATA_DIR)
    os.mkdir(METADATA_DIR)

    ## copy BB target file
    new_bb_target_file = METADATA_DIR / BBTARGETS_NAME
    shutil.copy(prev_bb_target_file, new_bb_target_file)

    exe_cmd = [
        f"{parser_prog}",
        "-b",
        f"{binary}",
        "-o",
        f"{METADATA_DIR}",
        "-r",
        f"{os.path.realpath(PROJ_ROOT_DIR)}",
    ]
    err_log_file = TMP_DIR / f"step{get_step()+1}.err.log"
    with open(err_log_file, "w+") as logf:
        try:
            subprocess.run(
                exe_cmd,
                stderr=logf,
                check=True,
                cwd=os.getcwd(),
            )
        except subprocess.CalledProcessError:
            eprint(f"Some errors occurred. Please check the log file {err_log_file}.")


def complement_metadata():
    ### remove Python cache
    remove_py_cache()

    ## check python script
    com_meta_script = SCRIPT_DIR / CALCULATOR_DIR_NAME / COM_META_NAME
    if com_meta_script.exists() is False or com_meta_script.is_file() is False:
        eprint(
            f"Failed to find Python script {COM_META_NAME} under {CALCULATOR_DIR_NAME}"
        )

    ## check dot file of call graph
    dotfiles_dir = METADATA_DIR / DOTFILES_NAME
    if dotfiles_dir.exists() is False or dotfiles_dir.is_dir() is False:
        eprint(
            f"The dot file directory '{dotfiles_dir}' doesn't exist or is not a directory"
        )
    cg_dot_file = dotfiles_dir / CALLGRAPH_NAME
    if cg_dot_file.exists() is False or cg_dot_file.is_file() is False:
        eprint(
            f"The dot file of call graph '{cg_dot_file}' doesn't exist or is not a file"
        )

    ## check multiple metadata files
    bbnames = METADATA_DIR / BBNAMES_NAME
    bbcalls = METADATA_DIR / BBCALLS_NAME
    fnames = METADATA_DIR / FNAMES_NAME
    if bbnames.exists() is False or bbnames.is_file() is False:
        eprint(f"Failed to find {bbnames}")
    if bbcalls.exists() is False or bbcalls.is_file() is False:
        eprint(f"Failed to find {bbcalls}")
    if fnames.exists() is False or fnames.is_file() is False:
        eprint(f"Failed to find {fnames}")
    p_bbcalls = TMP_DIR / BBCALLS_NAME
    p_calledges = TMP_DIR / FCALLEDGES_NAME
    if p_bbcalls.exists() is False or p_bbcalls.is_file() is False:
        eprint(f"Failed to find {p_bbcalls}")
    if p_calledges.exists() is False or p_calledges.is_file() is False:
        eprint(f"Failed to find {p_calledges}")

    exe_cmd = [
        sys.executable,
        f"{com_meta_script}",
        "--pbbcalls",
        f"{p_bbcalls}",
        "--pcalledges",
        f"{p_calledges}",
        "--nfnames",
        f"{fnames}",
        "--nbbcalls",
        f"{bbcalls}",
        "--nbbnames",
        f"{bbnames}",
        "--ncgdot",
        f"{cg_dot_file}",
    ]
    err_log_file = TMP_DIR / f"step{get_step()+1}.err.log"
    with open(err_log_file, "w+") as logf:
        try:
            subprocess.run(exe_cmd, stderr=logf, check=True, cwd=os.getcwd())
        except subprocess.CalledProcessError:
            eprint(f"Some errors occurred. Please check the log file {err_log_file}.")

    ### remove Python cache
    remove_py_cache()


def calculate_cg():
    ### remove Python cache
    remove_py_cache()

    ## check python script
    cal_cg_script = SCRIPT_DIR / CALCULATOR_DIR_NAME / CAL_CG_NAME
    if cal_cg_script.exists() is False or cal_cg_script.is_file() is False:
        eprint(
            f"Failed to find Python script {CAL_CG_NAME} under {CALCULATOR_DIR_NAME}"
        )

    ## check dot file of call graph
    dotfiles_dir = METADATA_DIR / DOTFILES_NAME
    if dotfiles_dir.exists() is False or dotfiles_dir.is_dir() is False:
        eprint(
            f"The dot file directory '{dotfiles_dir}' doesn't exist or is not a directory"
        )
    cg_dot_file = dotfiles_dir / CALLGRAPH_NAME
    if cg_dot_file.exists() is False or cg_dot_file.is_file() is False:
        eprint(
            f"The dot file of call graph '{cg_dot_file}' doesn't exist or is not a file"
        )

    ## check multiple metadata files
    ftargets = METADATA_DIR / FTARGETS_NAME
    fnames = METADATA_DIR / FNAMES_NAME
    if ftargets.exists() is False or ftargets.is_file() is False:
        eprint(f"Failed to find {ftargets}")
    if fnames.exists() is False or fnames.is_file() is False:
        eprint(f"Failed to find {fnames}")

    ## check distance file for call graph
    distfiles_dir = METADATA_DIR / DISTFILES_NAME
    if distfiles_dir.exists() is False:
        os.mkdir(distfiles_dir)
    cg_dist_file = distfiles_dir / CG_DISTANCE_NAME

    exe_cmd = [
        sys.executable,
        f"{cal_cg_script}",
        "-d",
        f"{cg_dot_file}",
        "-t",
        f"{ftargets}",
        "-n",
        f"{fnames}",
        "-o",
        f"{cg_dist_file}",
    ]
    err_log_file = TMP_DIR / f"step{get_step()+1}.err.log"
    with open(err_log_file, "w+") as logf:
        try:
            subprocess.run(exe_cmd, stderr=logf, check=True, cwd=os.getcwd())
        except subprocess.CalledProcessError:
            eprint(f"Some errors occurred. Please check the log file {err_log_file}.")

    ### remove Python cache
    remove_py_cache()


def calculate_cfg():
    ### remove Python cache
    remove_py_cache()

    ## check python script
    cal_cfg_script = SCRIPT_DIR / CALCULATOR_DIR_NAME / CAL_CFG_NAME
    if cal_cfg_script.exists() is False or cal_cfg_script.is_file() is False:
        eprint(
            f"Failed to find Python script {CAL_CFG_NAME} under {CALCULATOR_DIR_NAME}"
        )

    ## directory containing distance files
    distfiles_dir = METADATA_DIR / DISTFILES_NAME
    if distfiles_dir.exists() is False or distfiles_dir.is_dir() is False:
        eprint(
            f"The distance file directory '{distfiles_dir}' doesn't exist or is not a directory"
        )
    cg_dist_file = distfiles_dir / CG_DISTANCE_NAME
    if cg_dist_file.exists() is False or cg_dist_file.is_file() is False:
        eprint(f"Failed to find call distance file {cg_dist_file}")

    ## check multiple metadata files
    bbtargets_new = METADATA_DIR / BBTARGETS_NEW_NAME
    bbnames = METADATA_DIR / BBNAMES_NAME
    bbcalls = METADATA_DIR / BBCALLS_NAME
    if bbtargets_new.exists() is False or bbtargets_new.is_file() is False:
        eprint(f"Failed to find {bbtargets_new}")
    if bbnames.exists() is False or bbnames.is_file() is False:
        eprint(f"Failed to find {bbnames}")
    if bbcalls.exists() is False or bbcalls.is_file() is False:
        eprint(f"Failed to find {bbcalls}")

    ## directory containing dot files
    dotfiles_dir = METADATA_DIR / DOTFILES_NAME
    if dotfiles_dir.exists() is False or dotfiles_dir.is_dir() is False:
        eprint(
            f"The dot file directory '{dotfiles_dir}' doesn't exist or is not a directory"
        )
    cg_dot_file = dotfiles_dir / CALLGRAPH_NAME
    if cg_dot_file.exists() is False or cg_dot_file.is_file() is False:
        eprint(
            f"The dot file of call graph '{cg_dot_file}' doesn't exist or is not a file"
        )
    with open(cg_dot_file, "r") as file:
        cg_dot_content = file.read()

    ## thread method
    def calculate_cfg_from_file(cfg_file: Path):
        """Calculate CFG distances in each thread"""
        if cfg_file.exists() is False or cfg_file.is_file() is False:
            return
        if cfg_file.stat().st_size == 0:
            return
        chunks = cfg_file.name.split(".")
        if chunks[-1] != "dot" or chunks[0] != "cfg":
            return
        chunks = chunks[1 : (len(chunks) - 1)]
        func_path_name = ".".join(chunks)
        func_loc_name = func_path_name.replace(")", "/")
        if func_loc_name not in cg_dot_content:
            return
        out_dist_file = distfiles_dir / f"cfg.{func_path_name}.distance.txt"
        executable = sys.executable
        exe_cmd = [
            executable,
            f"{cal_cfg_script}",
            "-d",
            f"{cfg_file}",
            "-t",
            f"{bbtargets_new}",
            "-n",
            f"{bbnames}",
            "-b",
            f"{bbcalls}",
            "-c",
            f"{cg_dist_file}",
            "-o",
            f"{out_dist_file}",
        ]
        r = subprocess.run(
            exe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
        return r

    ## multi-thread
    with ThreadPoolExecutor(max_workers=mp.cpu_count()) as executor:
        results = executor.map(calculate_cfg_from_file, dotfiles_dir.glob("cfg.*.dot"))

    ## check results
    try:
        for r in results:
            pass
    except subprocess.CalledProcessError as err:
        err_log_file = TMP_DIR / f"step{get_step()+1}.err.log"
        with open(err_log_file, "w") as file:
            file.write(err.stderr.decode())
        eprint(f"Some errors occurred. Please check the log file {err_log_file}.")

    ## merge distance files
    merge_dist_files(distfiles_dir, distfiles_dir / CFG_DISTANCE_NAME)

    ## remove Python cache
    remove_py_cache()


def calculate_supplement():
    ## check python script
    cal_supp_script = SCRIPT_DIR / CALCULATOR_DIR_NAME / CAL_SUPPLE_NAME
    if cal_supp_script.exists() is False or cal_supp_script.is_file() is False:
        eprint(
            f"Failed to find Python script {CAL_SUPPLE_NAME} under {CALCULATOR_DIR_NAME}"
        )

    ## directory containing distance files
    distfiles_dir = METADATA_DIR / DISTFILES_NAME
    if distfiles_dir.exists() is False or distfiles_dir.is_dir() is False:
        eprint(
            f"The distance file directory '{distfiles_dir}' doesn't exist or is not a directory"
        )
    cfg_dist_file = distfiles_dir / CFG_DISTANCE_NAME
    if cfg_dist_file.exists() is False or cfg_dist_file.is_file() is False:
        eprint(f"Failed to find call distance file {cfg_dist_file}")
    cg_dist_file = distfiles_dir / CG_DISTANCE_NAME
    if cg_dist_file.exists() is False or cg_dist_file.is_file() is False:
        eprint(f"Failed to find call distance file {cg_dist_file}")

    ## check multiple metadata files
    bbnames = METADATA_DIR / BBNAMES_NAME
    bbcalls = METADATA_DIR / BBCALLS_NAME
    fnames = METADATA_DIR / FNAMES_NAME
    if bbnames.exists() is False or bbnames.is_file() is False:
        eprint(f"Failed to find {bbnames}")
    if bbcalls.exists() is False or bbcalls.is_file() is False:
        eprint(f"Failed to find {bbcalls}")
    if fnames.exists() is False or fnames.is_file() is False:
        eprint(f"Failed to find {fnames}")

    ## directory containing dot files
    dotfiles_dir = METADATA_DIR / DOTFILES_NAME
    if dotfiles_dir.exists() is False or dotfiles_dir.is_dir() is False:
        eprint(
            f"The dot file directory '{dotfiles_dir}' doesn't exist or is not a directory"
        )
    cg_dot_file = dotfiles_dir / CALLGRAPH_NAME
    if cg_dot_file.exists() is False or cg_dot_file.is_file() is False:
        eprint(
            f"The dot file of call graph '{cg_dot_file}' doesn't exist or is not a file"
        )

    exe_cmd = [
        sys.executable,
        f"{cal_supp_script}",
        "--cfgdir",
        f"{dotfiles_dir}",
        "--cgdot",
        f"{cg_dot_file}",
        "--cgdistance",
        f"{cg_dist_file}",
        "--cfgdistance",
        f"{cfg_dist_file}",
        "--fnames",
        f"{fnames}",
        "--bbnames",
        f"{bbnames}",
        "--bbcalls",
        f"{bbcalls}",
    ]
    err_log_file = TMP_DIR / f"step{get_step()+1}.err.log"
    with open(err_log_file, "w+") as logf:
        try:
            subprocess.run(exe_cmd, stderr=logf, check=True, cwd=os.getcwd())
        except subprocess.CalledProcessError:
            eprint(f"Some errors occurred. Please check the log file {err_log_file}.")


def get_step():
    global g_step
    if g_step == -1:
        step_log = TMP_DIR / STEP_LOG_NAME
        if not step_log.exists():
            g_step = 0
        else:
            tmp_step = 0
            with open(step_log, "r") as file:
                for line in file:
                    if line.strip().startswith("Step:"):
                        tmp_step = int(line.strip().split(":")[-1].strip())
            g_step = tmp_step
    return g_step


def next_step():
    global g_step
    g_step += 1
    step_log = TMP_DIR / STEP_LOG_NAME
    with open(step_log, "a") as file:
        file.write("Step:%d\n" % g_step)


def info_step(msg: str):
    iprint(f"[Step:{g_step + 1}] {msg}")


def restore_step():
    files_to_remove = list(TMP_DIR.glob("step*.err.log"))
    files_to_remove.append(TMP_DIR / STEP_LOG_NAME)
    for file in files_to_remove:
        if file.exists() and file.is_file():
            os.remove(file)


def remove_py_cache():
    py_cache_dir = SCRIPT_DIR / CALCULATOR_DIR_NAME / PY_CACHE_DIR_NAME
    if py_cache_dir.exists():
        shutil.rmtree(py_cache_dir)


def exit_handler():
    remove_py_cache()


def main():
    global BIN_DIR, BIN_NAME, TMP_DIR, PROJ_ROOT_DIR, METADATA_DIR

    atexit.register(exit_handler)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--directory",
        required=True,
        type=is_path_to_dir,
        help="The directory where program binaries locate",
    )
    parser.add_argument(
        "-t",
        "--tmpdir",
        required=True,
        type=is_path_to_dir,
        help="The temporary directory",
    )
    parser.add_argument(
        "-b",
        "--binary",
        required=True,
        help="The program binary name",
    )
    parser.add_argument(
        "-r",
        "--rootdir",
        type=str,
        nargs="?",
        const="",
        default="",
        help="The project root directory",
    )
    parser.add_argument(
        "-re",
        "--restore",
        action="store_true",
        help="Restore the steps and re-calculate distances",
    )

    args = parser.parse_args()

    if args.rootdir is None or len(args.rootdir) == 0:
        rdir = os.getenv("AFLGO_PLUS_PROJ_ROOT_PATH")
        if rdir is None:
            raise argparse.ArgumentError(
                message="Failed to find project root directory"
            )
        args.rootdir = rdir

    PROJ_ROOT_DIR = is_path_to_dir(args.rootdir)
    BIN_NAME = args.binary
    BIN_DIR = Path(args.directory)
    TMP_DIR = Path(args.tmpdir)
    METADATA_DIR = TMP_DIR / METADATA_NAME

    ### restore steps and re-calculate distances
    if hasattr(args, "restore") and args.restore is not None and args.restore:
        restore_step()

    if get_step() == 0:
        info_step(f"Parsing bitcode file for '{BIN_NAME}'")
        parse_bc()
        next_step()
    if get_step() == 1:
        info_step(f"Complementing some metadata")
        complement_metadata()
        next_step()
    if get_step() == 2:
        info_step(f"Calculating distances for call graph")
        calculate_cg()
        next_step()
    if get_step() == 3:
        info_step(f"Calculating distances for CFGs (this may take a while)")
        calculate_cfg()
        next_step()
    if get_step() == 4:
        info_step(f"Calculating supplemental distances")
        calculate_supplement()
        next_step()
    if get_step() >= 5:
        iprint("All the things were done!")


if __name__ == "__main__":
    main()
