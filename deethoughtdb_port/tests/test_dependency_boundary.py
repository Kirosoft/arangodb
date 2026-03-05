import ast
import pathlib
import sys
import unittest


class DependencyBoundaryTests(unittest.TestCase):
    def test_no_external_imports_outside_stdlib_or_local_package(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        src_root = root / "src" / "deethoughtdb_port"

        stdlib_modules = set(sys.stdlib_module_names)
        allowed_roots = {"deethoughtdb_port"}

        violations: list[str] = []
        for py_file in src_root.rglob("*.py"):
            module = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(module):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        root_name = name.name.split(".")[0]
                        if root_name in allowed_roots or root_name in stdlib_modules:
                            continue
                        violations.append(f"{py_file}: import {name.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.level > 0:
                        continue
                    if node.module is None:
                        continue
                    root_name = node.module.split(".")[0]
                    if root_name in allowed_roots or root_name in stdlib_modules:
                        continue
                    violations.append(f"{py_file}: from {node.module} import ...")

        if violations:
            self.fail("External dependency boundary violated:\n" + "\n".join(violations))


if __name__ == "__main__":
    unittest.main()
