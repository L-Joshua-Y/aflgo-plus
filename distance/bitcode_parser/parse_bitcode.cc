/**
 *
 */

#include "../../instrument/info.h"

#include <iostream>
#include <fstream>
#include <vector>
#include <list>
#include <unordered_set>

#include "llvm/ADT/Statistic.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/Module.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/Support/GraphWriter.h"
#include "llvm/Analysis/CallGraph.h"
#include "llvm/Analysis/CallPrinter.h"
#include "llvm/Analysis/CFGPrinter.h"
#include "llvm/Bitcode/BitcodeReader.h"
#include "llvm/Support/MemoryBuffer.h"

#if defined(LLVM34)
#include "llvm/DebugInfo.h"
#else
#include "llvm/IR/DebugInfo.h"
#endif

#if defined(LLVM34) || defined(LLVM35) || defined(LLVM36)
#define LLVM_OLD_DEBUG_API
#endif

using namespace llvm;

namespace llvm
{
    template <>
    struct DOTGraphTraits<Function *> : public DefaultDOTGraphTraits
    {
        DOTGraphTraits(bool isSimple = true) : DefaultDOTGraphTraits(isSimple) {}

        static std::string getGraphName(Function *F)
        {
            return "Control Flow Graph for '" + F->getName().str() + "' function";
        }

        std::string getNodeLabel(BasicBlock *Node, Function *Graph)
        {
            if (!Node->getName().empty())
            {
                return Node->getName().str();
            }

            std::string Str;
            raw_string_ostream OS(Str);

            Node->printAsOperand(OS, false);
            return OS.str();
        }
    };

    template <>
    struct DOTGraphTraits<CallGraph *> : public DefaultDOTGraphTraits
    {
        DOTGraphTraits(bool isSimple = true) : DefaultDOTGraphTraits(isSimple) {}

        static std::string getGraphName(CallGraph *cg)
        {
            return "Call Graph for '" + cg->getModule().getName().str() + "'";
        }

        std::string getNodeLabel(CallGraphNode *Node, CallGraph *Graph)
        {
            if (Function *F = Node->getFunction())
            {
                return F->getName().str();
            }
            else
            {
                return "(unknown)";
            }
        }
    };

} // namespace llvm

static bool isBlacklisted(const Function *F)
{
    static const SmallVector<std::string, 8> Blacklist = {
        "asan.",
        "llvm.",
        "sancov.",
        "__ubsan_handle_",
        "free",
        "malloc",
        "calloc",
        "realloc"};

    for (auto const &BlacklistFunc : Blacklist)
    {
        if (F->getName().startswith(BlacklistFunc))
        {
            return true;
        }
    }

    return false;
}

static void getDebugLocWithColAndPath(
    const Instruction *I,
    std::string &Filepath,
    unsigned &Line,
    unsigned &Column,
    const std::string &pathPrefix)
{
    Filepath = "";
    Line = 0;
    Column = 0;
#ifdef LLVM_OLD_DEBUG_API
    DebugLoc Loc = I->getDebugLoc();
    if (!Loc.isUnknown())
    {
        DILocation cDILoc(Loc.getAsMDNode(M.getContext()));
        DILocation oDILoc = cDILoc.getOrigLocation();

        Line = oDILoc.getLineNumber();
        std::string Directory = oDILoc.getDirectory().str();
        std::string Filename = oDILoc.getFilename().str();

        if (Filename.empty())
        {
            Line = cDILoc.getLineNumber();
            Directory = cDILoc.getDirectory().str();
            Filename = cDILoc.getFilename().str();
        }

        if (!Filename.empty())
        {
            SmallString<512> AbsPath;
            if (Filename.front() == '/')
            {
                Filepath = Filename;
            }
            else
            {
                Filepath = Directory.empty() ? Filename : (Directory + std::string("/") + Filename);
                auto ec = sys::fs::real_path(Filepath, AbsPath);
                if (!ec)
                {
                    Filepath = AbsPath.str().str();
                    if (!pathPrefix.empty() && Filepath.size() >= pathPrefix.size())
                    {
                        if (!Filepath.compare(0, pathPrefix.size(), pathPrefix))
                        {
                            Filepath = Filepath.substr(pathPrefix.size());
                            if (!Filepath.empty() && Filepath.front() == '/')
                                Filepath = Filepath.substr(1);
                        }
                    }
                }
            }
        }
    }
#else
    if (DILocation *Loc = I->getDebugLoc())
    {
        Line = Loc->getLine();
        Column = Loc->getColumn();
        std::string Directory = Loc->getDirectory().str();
        std::string Filename = Loc->getFilename().str();

        if (Filename.empty())
        {
            DILocation *oDILoc = Loc->getInlinedAt();
            if (oDILoc)
            {
                Line = oDILoc->getLine();
                Column = oDILoc->getColumn();
                Directory = oDILoc->getDirectory().str();
                Filename = oDILoc->getFilename().str();
            }
        }

        if (!Filename.empty())
        {
            SmallString<512> AbsPath;
            if (Filename.front() == '/')
            {
                Filepath = Filename;
            }
            else
            {
                Filepath = Directory.empty() ? Filename : (Directory + std::string("/") + Filename);
                auto ec = sys::fs::real_path(Filepath, AbsPath);
                if (!ec)
                {
                    Filepath = AbsPath.str().str();
                    if (!pathPrefix.empty() && Filepath.size() >= pathPrefix.size())
                    {
                        if (!Filepath.compare(0, pathPrefix.size(), pathPrefix))
                        {
                            Filepath = Filepath.substr(pathPrefix.size());
                            if (!Filepath.empty() && Filepath.front() == '/')
                                Filepath = Filepath.substr(1);
                        }
                    }
                }
            }
        }
    }
#endif
}

// Get debug location for an input instruction. The location
// contains the real path of the source file.
static void getDebugLocWithPath(const Instruction *I, std::string &Filepath, unsigned &Line, const std::string &pathPrefix)
{
    Filepath = "";
    Line = 0;
    unsigned Column = 0;
    getDebugLocWithColAndPath(I, Filepath, Line, Column, pathPrefix);
}

// Get function name along with function location
static std::string getFuncLocName(const Function *F, const std::string &pathPrefix)
{
    std::string funcLoc = "";
    std::string filename = "";
    unsigned line = 0;
    for (auto &BB : *F)
    {
        for (auto &I : BB)
        {
            getDebugLocWithPath(&I, filename, line, pathPrefix);
            if (!filename.empty())
                break;
        }
        if (!filename.empty())
            break;
    }
    if (!filename.empty())
        funcLoc = filename + std::string(":") + itostr(line);
    else
    {
        funcLoc = "0x" + utohexstr(F->getGUID());
    }

    return funcLoc + std::string(";") + F->getName().str();
}

static std::string trimStr(const std::string &_str)
{
    std::unordered_set<char> whiteSpaces({' ', '\t', '\n', '\r'});

    // Left
    size_t left = 0;
    while (left < _str.size())
    {
        if (whiteSpaces.find(_str[left]) == whiteSpaces.end())
            break;
        left++;
    }
    if (left >= _str.size())
        return "";

    // Right
    size_t right = _str.size() - 1;
    while (right > left)
    {
        if (whiteSpaces.find(_str[right]) == whiteSpaces.end())
            break;
        right--;
    }

    if (left <= right)
        return _str.substr(left, right - left + 1);
    else
        return "";
}

static bool removeDupLines(const std::string &fileName)
{
    std::ifstream file(fileName);
    if (!file.is_open())
    {
        std::cerr << "Error: failed to open the generated file " << fileName << std::endl;
        return false;
    }

    std::unordered_set<std::string> lineSet;
    std::list<std::string> lineList;
    std::string line;
    while (std::getline(file, line))
    {
        auto trimmedStr = trimStr(line);
        if (trimmedStr.empty())
            lineList.push_back("");
        else if (lineSet.find(trimmedStr) == lineSet.end())
        {
            lineSet.emplace(trimmedStr);
            lineList.push_back(line);
        }
    }
    file.close();

    std::ofstream ofile(fileName, std::ios::out | std::ios::trunc);
    if (!ofile.is_open())
    {
        std::cerr << "Error: failed to open the generated file " << fileName << std::endl;
        return false;
    }
    for (const auto &line : lineList)
    {
        ofile << line << std::endl;
    }
    ofile.close();

    return true;
}

static std::string repSepStr(const std::string &prevStr)
{
    auto result = prevStr;
    for (size_t i = 0; i < prevStr.size(); i++)
    {
        if (prevStr[i] == '/')
            result[i] = ')';
    }

    return result;
}

int main(int argc, char **argv)
{
    // Find output directory from the arguments
    std::string outDirectory = "";
    std::string projRootDir = "";
    std::string bcFile = "";
    int index = 1;
    while (index < argc)
    {
        if (!strncmp(argv[index], "-h", 2) || !strncmp(argv[index], "--help", 6))
        {
            if (argc != 2)
            {
                std::cerr << "Error: the option `-h` was used mistakenly" << std::endl;
                return 1;
            }
            else
            {
                std::cout << "Generate function and BB content for distance calculation...\n"
                             "usage: "
                          << argv[0] << " [-h] -b BITCODE -o OUTDIR [-r ROOTDIR]\n"
                                        "\noptional arguments:\n"
                                        "\t-b BITCODE, --bitcode BITCODE\t\tbitcode file\n"
                                        "\t-o OUTDIR, --outdir OUTDIR\t\toutput directory\n"
                                        "\t[-r ROOTDIR, --root ROOTDIR]\t\tproject root directory\n"
                          << std::endl;
                return 0;
            }
        }
        else if (!strncmp(argv[index], "-b", 2) || !strncmp(argv[index], "--bitcode", 8))
        {
            ++index;
            if (index >= argc)
            {
                std::cerr << "Error: no specified `bitcode` option" << std::endl;
                return 1;
            }
            bcFile = argv[index];
        }
        else if (!strncmp(argv[index], "-o", 2) || !strncmp(argv[index], "--outdir", 8))
        {
            ++index;
            if (index >= argc)
            {
                std::cerr << "Error: no specified `outdir` option" << std::endl;
                return 1;
            }
            outDirectory = argv[index];
        }
        else if (!strncmp(argv[index], "-r", 2) || !strncmp(argv[index], "--root", 6))
        {
            ++index;
            if (index >= argc)
            {
                std::cerr << "Error: no specified `root` option" << std::endl;
                return 1;
            }
            projRootDir = argv[index];
        }
        else
        {
            std::cerr << "Error: unknown argument '" << argv[index] << "'" << std::endl;
            return 1;
        }
        ++index;
    }

    // Check bitcode file
    if (bcFile.empty())
    {
        std::cerr << "Error: no specified `bitcode` option" << std::endl;
        return 1;
    }
    if (!sys::fs::exists(bcFile) || !sys::fs::is_regular_file(bcFile))
    {
        std::cerr << "Error: " << bcFile << " doesn't exist or is not a file" << std::endl;
        return 1;
    }

    // Check output directory
    if (outDirectory.empty())
    {
        std::cerr << "Error: no specified `outdir` option" << std::endl;
        return 1;
    }
    if (!sys::fs::exists(outDirectory) || !sys::fs::is_directory(outDirectory))
    {
        std::cerr << "Error: " << outDirectory << " doesn't exist or is not a directory" << std::endl;
        return 1;
    }

    // Check env project root directory
    if (projRootDir.empty())
        if (getenv(AFLGO_PLUS_PROJ_ENV))
            projRootDir = getenv(AFLGO_PLUS_PROJ_ENV);
    if (projRootDir.empty())
    {
        std::cerr << "Error: env '" AFLGO_PLUS_PROJ_ENV "' is not found or is empty" << std::endl;
        return 1;
    }
    if (!sys::fs::exists(projRootDir) || !sys::fs::is_directory(projRootDir))
    {
        std::cerr << "Error: " << projRootDir << " doesn't exist or is not a directory" << std::endl;
        return 1;
    }
    if (projRootDir.front() != '/')
    {
        SmallString<512> AbsPath;
        auto ec = sys::fs::real_path(projRootDir, AbsPath);
        if (ec)
        {
            std::cerr << "Error: failed to parse project root directory '" << projRootDir << "'" << std::endl;
            return 1;
        }
        projRootDir = AbsPath.str().str();
    }
    if (projRootDir.back() == '/')
        projRootDir.pop_back();

    // Check option files
    if (outDirectory.back() != '/')
        outDirectory += "/";
    // Check BB target file
    std::ifstream bbTargetsFile(outDirectory + AFLGO_BB_TARGETS_FILE, std::ios::in);
    if (!bbTargetsFile.is_open())
    {
        std::cerr << "Error: BB target file " << outDirectory + AFLGO_BB_TARGETS_FILE << " doesn't exist or is not a file" << std::endl;
        return 1;
    }
    std::list<std::pair<std::string, unsigned>> bbTargets;
    std::string line;
    while (std::getline(bbTargetsFile, line))
    {
        line = trimStr(line);
        std::size_t pos = line.find_last_of(":");
        std::string targetFileName = line.substr(0, pos);
        int targetLine = atoi(line.substr(pos + 1).c_str());
        if (targetLine <= 0)
        {
            std::cerr << "Error: wrong target BB '" << line << "'" << std::endl;
            return 1;
        }
        std::string targetFilePath = projRootDir + "/" + targetFileName;
        if (!sys::fs::exists(targetFilePath) || !sys::fs::is_regular_file(targetFilePath))
        {
            std::cerr << "Error: failed to find target file '" << targetFileName << "' under directory '" << projRootDir << "'" << std::endl;
            std::cerr << "(Please mind the slashes in file path)" << std::endl;
            return 1;
        }
        bbTargets.emplace_back(targetFileName, (unsigned)targetLine);
    }
    // Create dot file directory
    std::string dotfiles(outDirectory + AFLGO_DOTFILES_DIR);
    if (sys::fs::create_directory(dotfiles))
    {
        std::cerr << "Error: could not create directory " << dotfiles << std::endl;
        return 1;
    }

    LLVMContext Context;

    // Load the bitcode file
    ErrorOr<std::unique_ptr<MemoryBuffer>> FileOrErr = MemoryBuffer::getFile(bcFile);
    if (std::error_code EC = FileOrErr.getError())
    {
        std::cerr << "Error: failed to read bitcode file: " << EC.message() << std::endl;
        return 1;
    }

    // Parse the bitcode file
    Expected<std::unique_ptr<Module>> ModuleOrErr = parseBitcodeFile(FileOrErr.get()->getMemBufferRef(), Context);
    if (std::error_code EC = errorToErrorCode(ModuleOrErr.takeError()))
    {
        std::cerr << "Error: failed to parse bitcode file: " << EC.message() << std::endl;
        return 1;
    }

    // Get the module
    std::unique_ptr<Module> M = std::move(ModuleOrErr.get());
    if (!M)
    {
        std::cerr << "Error: the module handler is null" << std::endl;
        return 1;
    }

    std::ofstream bbtargets_new(outDirectory + AFLGO_BB_TARGETS_NEW_FILE, std::ios::out | std::ios::trunc);
    std::ofstream bbnames(outDirectory + AFLGO_BB_NAMES_FILE, std::ios::out | std::ios::trunc);
    std::ofstream bbcalls(outDirectory + AFLGO_BB_CALLS_FILE, std::ios::out | std::ios::trunc);
    std::ofstream fnames(outDirectory + AFLGO_FUNC_NAMES_FILE, std::ios::out | std::ios::trunc);
    std::ofstream ftargets(outDirectory + AFLGO_FUNC_TARGETS_FILE, std::ios::out | std::ios::trunc);

    std::unordered_set<std::string> bbTargetNewSet;
    std::unordered_set<std::string> bbNameSet;
    std::unordered_set<std::string> bbCallSet;
    std::unordered_set<std::string> fNameSet;
    std::unordered_set<std::string> fTargetSet;

    // Traverse the module
    for (Module::iterator F = M->begin(), E = M->end(); F != E; ++F)
    {
        if (isBlacklisted(&(*F)))
            continue;
        // errs() << "Function: " << F->getName() << "\n";
        std::string funcLocName = getFuncLocName(&(*F), projRootDir);
        std::string funcPathName = repSepStr(funcLocName);

        bool hasTarget = false;
        bool hasBB = false;
        for (Function::iterator BB = F->begin(), E = F->end(); BB != E; ++BB)
        {
            std::string bb_name = "";
            std::string filename = "";
            unsigned line = 0;
            unsigned column = 0;
            bool isTarget = false;

            for (Instruction &I : BB->getInstList())
            {
                // Get debug location information
                // getDebugLocWithPath(&I, filename, line, projRootDir);
                getDebugLocWithColAndPath(&I, filename, line, column, projRootDir);

                /* Don't worry about external libs */
                static const std::string Xlibs("/usr/");
                if (filename.empty() || line == 0 || !filename.compare(0, Xlibs.size(), Xlibs))
                    continue;

                // Assign BB name
                if (bb_name.empty())
                    bb_name = filename + ":" + std::to_string(line);

                // Check whether this BB is target BB
                for (auto &bbTarget : bbTargets)
                {
                    if (!bbTarget.first.compare(filename) && bbTarget.second == line)
                    {
                        isTarget = true;
                        hasTarget = true;
                        if (!bb_name.empty())
                        {
                            if (bbTargetNewSet.find(bb_name) == bbTargetNewSet.end())
                            {
                                bbTargetNewSet.emplace(bb_name);
                                bbtargets_new << bb_name << std::endl;
                            }
                        }
                    }
                }

                // Get the function called by this BB
                if (auto *CI = dyn_cast<CallInst>(&I))
                {
                    if (auto *calledFunction = CI->getCalledFunction())
                    {
                        if (!isBlacklisted(calledFunction))
                        {
                            std::string tmpBBCallCont = bb_name + "," + getFuncLocName(calledFunction, projRootDir);
                            if (bbCallSet.find(tmpBBCallCont) == bbCallSet.end())
                            {
                                bbCallSet.emplace(tmpBBCallCont);
                                bbcalls << tmpBBCallCont << std::endl;
                            }
                        }
                        // errs() << funcLocName << "->" << getFuncLocName(calledFunction, projRootDir) << "\n";
                        // errs() << "  Calls: " << calledFunction->getName() << "\n";
                    }
                }
            }

            // Check BB name
            if (!bb_name.empty())
            {
                BB->setName(bb_name + ":");
                if (!BB->hasName())
                {
                    std::string newname = bb_name + ":";
                    Twine t(newname);
                    SmallString<256> NameData;
                    StringRef NameRef = t.toStringRef(NameData);
                    MallocAllocator Allocator;
                    BB->setValueName(ValueName::Create(NameRef, Allocator));
                }

                std::string tmpBBName = BB->getName().str();
                auto lastIndex = tmpBBName.find_last_of(":");
                if (lastIndex >= 0 && lastIndex < tmpBBName.size())
                    tmpBBName = tmpBBName.substr(0, lastIndex);
                if (bbNameSet.find(tmpBBName) == bbNameSet.end())
                {
                    bbNameSet.emplace(tmpBBName);
                    bbnames << tmpBBName << std::endl;
                }
                hasBB = true;
            }
        }

        if (hasBB)
        {
            // Generate CFG
            std::string cfgFileName = dotfiles + "/cfg." + funcPathName + ".dot";
            std::error_code EC;
            raw_fd_ostream cfgFile(cfgFileName, EC, sys::fs::F_None);
            if (!EC)
            {
                WriteGraph(cfgFile, &(*F), true);
                cfgFile.close();
                if (!removeDupLines(cfgFileName))
                {
                    std::cout << "Warning: failed to remove duplicate edges in CFG for " << funcLocName << std::endl;
                }
            }
            else
            {
                std::cout << "Warning: failed to generate CFG for " << funcLocName << " : " << EC.message() << std::endl;
            }

            // Target function
            if (hasTarget)
            {
                if (fTargetSet.find(funcLocName) == fTargetSet.end())
                {
                    fTargetSet.emplace(funcLocName);
                    ftargets << funcLocName << std::endl;
                }
            }
            if (fNameSet.find(funcLocName) == fNameSet.end())
            {
                fNameSet.emplace(funcLocName);
                fnames << funcLocName << std::endl;
            }
        }
    }

    // Assign function names along with their locations
    for (Module::iterator F = M->begin(), E = M->end(); F != E; ++F)
    {
        // errs() << "Function: " << F->getName() << "\n";
        std::string funcLocName = getFuncLocName(&(*F), projRootDir);
        F->setName(funcLocName);
    }

    // Generate call graph
    auto cgGraph = CallGraph(*M);
    std::error_code EC;
    std::string cgFileName = dotfiles + "/" + AFLGO_CALLGRAPH_FILE;
    raw_fd_ostream cgFile(cgFileName, EC, sys::fs::F_None);
    if (!EC)
        WriteGraph(cgFile, &cgGraph, true);
    else
    {
        std::cerr << "Error: failed to generate call graph: " << EC.message() << "\n";
        return 1;
    }
    cgFile.close();
    // Remove duplicate edges in call graph
    if (!removeDupLines(cgFileName))
        return 1;

    return 0;
}
