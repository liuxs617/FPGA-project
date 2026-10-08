# Source this from the project root: source scripts/board_env.sh
# Local offline dependencies remain visible when PYTHONPATH is passed to sudo.
export BOARD_PY="$(command -v python3)"
export XILINX_XRT="${XILINX_XRT:-/usr}"
export PYTHONPATH="$PWD/.board_deps:$PWD/software${PYTHONPATH:+:$PYTHONPATH}"
