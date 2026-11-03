"""Enforce documented Radon complexity, source-size, and LOC limits."""

import ast
from pathlib import Path

from radon.complexity import cc_rank, cc_visit
from radon.raw import analyze


def main() -> int:
    """Check application, test, and gate-script Python modules."""
    root = Path(__file__).resolve().parents[1]
    paths = _application_paths(root)
    paths.extend(root.joinpath("tests").rglob("*.py"))
    paths.extend(root.joinpath("scripts").rglob("*.py"))
    issues = [issue for path in paths for issue in _file_issues(root, path)]
    for issue in issues:
        print(issue)
    if issues:
        return 1
    print(f"Code-size and Radon checks passed for {len(paths)} Python files.")
    return 0


def _application_paths(root: Path) -> list[Path]:
    paths = [root / "manage.py"]
    for path in root.joinpath("emporio").rglob("*.py"):
        if "migrations" not in path.relative_to(root).parts:
            paths.append(path)
    return paths


def _file_issues(root: Path, path: Path) -> list[str]:
    """Report file, module API, complexity, class, and function limit failures."""
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)
    issues = []
    is_test = "tests" in path.relative_to(root).parts
    file_limit = 200 if is_test else 150
    if analyze(source).sloc > file_limit:
        issues.append(f"{path.relative_to(root)}: source LOC exceeds {file_limit}")
    issues.extend(_size_issues(path, tree, lines, is_test))
    for block in cc_visit(source):
        if block.complexity > 5:
            issues.append(
                f"{path.relative_to(root)}:{block.lineno} {block.name}: "
                f"Radon rank {cc_rank(block.complexity)}"
            )
    return issues


def _size_issues(path: Path, tree: ast.Module, lines: list[str], is_test: bool) -> list[str]:
    """Check function/class limits and explicit module export lists."""
    return (
        _function_issues(path, tree, lines, is_test)
        + _class_issues(path, tree, lines)
        + _api_issues(path, tree)
    )


def _function_issues(path: Path, tree: ast.Module, lines: list[str], is_test: bool) -> list[str]:
    """Check every function against its implementation or test LOC cap."""
    return [
        issue
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        if (issue := _function_issue(path, node, lines, is_test)) is not None
    ]


def _function_issue(
    path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str], is_test: bool
) -> str | None:
    """Return a function LOC violation, if one exists."""
    limit = 30 if is_test and node.name.startswith("test_") else 25
    if _loc(lines, node.lineno, node.end_lineno or node.lineno) > limit:
        return f"{path}:{node.lineno} {node.name}: LOC exceeds {limit}"
    return None


def _class_issues(path: Path, tree: ast.Module, lines: list[str]) -> list[str]:
    """Check class bodies against the 100 nonblank source-line cap."""
    issues: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        end = node.end_lineno or node.lineno
        if _loc(lines, node.lineno, end) > 100:
            issues.append(f"{path}:{node.lineno} {node.name}: class LOC exceeds 100")
    return issues


def _api_issues(path: Path, tree: ast.Module) -> list[str]:
    """Check explicit public exports against the seven-symbol cap."""
    return [issue for node in ast.walk(tree) if (issue := _export_issue(path, node)) is not None]


def _export_issue(path: Path, node: ast.AST) -> str | None:
    """Format an export-count issue only for an oversized assignment."""
    if _exports_too_many(node) and isinstance(node, ast.Assign):
        return f"{path}:{node.lineno}: public API exports more than 7 symbols"
    return None


def _exports_too_many(node: ast.AST) -> bool:
    """Recognize oversized module-level `__all__` assignments."""
    if not isinstance(node, ast.Assign):
        return False
    return _all_assignment(node) and _too_many_exports(node.value)


def _all_assignment(node: ast.Assign) -> bool:
    """Identify an assignment to the module export list."""
    return any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)


def _too_many_exports(value: ast.expr) -> bool:
    """Check whether a list or tuple export declaration exceeds seven names."""
    if not isinstance(value, (ast.List, ast.Tuple)):
        return False
    return len(value.elts) > 7


def _loc(lines: list[str], start: int, end: int) -> int:
    """Count nonblank, noncomment source lines in one syntax node."""
    return sum(
        bool(line.strip()) and not line.lstrip().startswith("#") for line in lines[start - 1 : end]
    )


if __name__ == "__main__":
    raise SystemExit(main())
