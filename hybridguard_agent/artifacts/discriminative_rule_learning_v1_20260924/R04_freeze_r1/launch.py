"""Isolated launcher: -I -S ignores cwd, PYTHONPATH and user site packages."""
from pathlib import Path
import sys
root = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path[:0] = [str(root / "snapshot"), str(root / "dependencies/site-packages")]
from hybridguard_agent.research.rule_learning.runner import main
main()
