###

LLVM_CONFIG ?= llvm-config

CLANG_CFL    = `$(LLVM_CONFIG) --cxxflags` -Wl,-znodelete -fno-rtti -fpic $(CXXFLAGS)
CLANG_LFL    = `$(LLVM_CONFIG) --ldflags` `$(LLVM_CONFIG) --system-libs --libs all` $(LDFLAGS)

ifeq "$(shell uname)" "Darwin"
  CLANG_LFL += -Wl,-flat_namespace -Wl,-undefined,suppress
endif

ifeq "$(origin CC)" "default"
	CC         = clang
	CXX        = clang++
endif

SOURCE_FILE = parse_bitcode.cc
BINARY = parse_bitcode

all : $(BINARY)

$(BINARY): $(SOURCE_FILE)
	$(CXX) $(CLANG_CFL) $^ -o $@ $(CLANG_LFL)

.PHONY: clean

clean:
	@rm -f $(BINARY)