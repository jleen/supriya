#!/usr/bin/env python3
"""Generate .pyi stub files for UGen classes."""

import ast
from pathlib import Path
from typing import Any


class UGenStubGenerator(ast.NodeVisitor):
    """Generate stub file content for UGen classes."""

    def __init__(self, source_path: Path):
        self.source_path = source_path
        self.imports: set[str] = set()
        self.ugen_classes: list[str] = []
        self.non_ugen_classes: list[str] = []
        self.ugen_decorator_params: dict[str, Any] = {}
        self.current_class_params: list[tuple[str, bool]] = []

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Collect imports from the source file."""
        if node.module:
            names = ", ".join(alias.name for alias in node.names)
            self.imports.add(f"from {node.module} import {names}")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definitions and generate stubs for @ugen decorated classes."""
        # Check if class has @ugen decorator
        ugen_decorator = None
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(
                decorator.func, ast.Name
            ):
                if decorator.func.id == "ugen":
                    ugen_decorator = decorator
                    break
            elif isinstance(decorator, ast.Name) and decorator.id == "ugen":
                ugen_decorator = decorator
                break

        if ugen_decorator:
            # Parse decorator arguments
            decorator_args = self._parse_decorator_args(ugen_decorator)

            # Collect param() calls
            params = self._collect_params(node)

            # Generate stub
            stub = self._generate_ugen_stub(node.name, decorator_args, params)
            self.ugen_classes.append(stub)
        else:
            # Track non-@ugen classes
            self.non_ugen_classes.append(node.name)

        self.generic_visit(node)

    def _parse_decorator_args(self, decorator: ast.AST) -> dict[str, Any]:
        """Parse arguments from @ugen decorator."""
        args = {}
        if isinstance(decorator, ast.Call):
            for keyword in decorator.keywords:
                if keyword.arg:
                    if isinstance(keyword.value, ast.Constant):
                        args[keyword.arg] = keyword.value.value
        return args

    def _collect_params(self, node: ast.ClassDef) -> list[tuple[str, bool]]:
        """Collect param() calls from class body.

        Returns list of (param_name, unexpanded) tuples.
        """
        params = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.value, ast.Call):
                # Handle annotated assignments like: name: type = param()
                if isinstance(item.value.func, ast.Name) and item.value.func.id == "param":
                    param_name = item.target.id if isinstance(item.target, ast.Name) else None
                    unexpanded = self._get_unexpanded_arg(item.value)
                    if param_name:
                        params.append((param_name, unexpanded))
            elif isinstance(item, ast.Assign):
                # Handle regular assignments like: name = param()
                for target in item.targets:
                    if isinstance(target, ast.Name) and isinstance(item.value, ast.Call):
                        if isinstance(item.value.func, ast.Name) and item.value.func.id == "param":
                            param_name = target.id
                            unexpanded = self._get_unexpanded_arg(item.value)
                            params.append((param_name, unexpanded))
        return params

    def _get_unexpanded_arg(self, call: ast.Call) -> bool:
        """Extract unexpanded argument from param() call."""
        for keyword in call.keywords:
            if keyword.arg == "unexpanded":
                if isinstance(keyword.value, ast.Constant):
                    return bool(keyword.value.value)
        return False

    def _generate_ugen_stub(
        self, class_name: str, decorator_args: dict[str, Any], params: list[tuple[str, bool]]
    ) -> str:
        """Generate stub class definition for @ugen decorated classes."""
        lines = [f"class {class_name}(UGen):"]

        # Generate __init__ method
        init_params = ["self", "*", "calculation_rate: CalculationRateLike"]

        # Add channel_count parameter if needed
        is_multichannel = decorator_args.get("is_multichannel", False)
        fixed_channel_count = decorator_args.get("fixed_channel_count", False)
        if is_multichannel and not fixed_channel_count:
            channel_count = decorator_args.get("channel_count", 1)
            init_params.append(f"channel_count: int = {channel_count}")

        # Add parameter arguments
        for param_name, unexpanded in params:
            type_hint = "UGenVectorInput" if unexpanded else "UGenScalarInput"
            init_params.append(f"{param_name}: {type_hint} = ...")

        init_params.append("**kwargs: Any")

        lines.append(f"    def __init__({', '.join(init_params)}) -> None: ...")

        # Generate property stubs for parameters
        for param_name, unexpanded in params:
            return_type = "UGenVector" if unexpanded else "UGenScalar"
            lines.append(f"    @property")
            lines.append(f"    def {param_name}(self) -> {return_type}: ...")

        # Generate rate class methods (ar, kr, ir, dr, new)
        for rate_name in ["ar", "kr", "ir", "dr", "new"]:
            if not decorator_args.get(rate_name, False):
                continue

            rate_params = ["cls"]
            if params:
                rate_params.append("*")

            # Add parameter arguments with UGenRecursiveInput type
            for param_name, _ in params:
                rate_params.append(f"{param_name}: UGenRecursiveInput = ...")

            # Add channel_count parameter if needed
            if is_multichannel and not fixed_channel_count:
                channel_count = decorator_args.get("channel_count", 1)
                rate_params.append(f"channel_count: int = {channel_count}")

            lines.append(f"    @classmethod")
            lines.append(
                f"    def {rate_name}({', '.join(rate_params)}) -> UGenOperable: ..."
            )

        return "\n".join(lines)

    def _generate_non_ugen_stub(self, node: ast.ClassDef) -> str:
        """Generate a basic stub for a non-@ugen class."""
        lines = []

        # Class definition with base classes
        if node.bases:
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(f"{ast.unparse(base.value)}.{base.attr}")
            bases_str = f"({', '.join(bases)})" if bases else ""
        else:
            bases_str = ""

        lines.append(f"class {node.name}{bases_str}:")

        # Find methods
        has_methods = False

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                has_methods = True
                if item.name == "__init__":
                    # Generate __init__ stub
                    params = self._get_function_params(item)
                    lines.append(f"    def __init__({params}) -> None: ...")
                elif not item.name.startswith("_") or item.name in ["__str__", "__repr__", "__plot__"]:
                    # Generate method stub for public methods and some special methods
                    params = self._get_function_params(item)
                    return_type = self._get_return_annotation(item)

                    # Check if it's a property
                    is_property = any(
                        isinstance(d, ast.Name) and d.id == "property"
                        for d in item.decorator_list
                    )

                    if is_property:
                        lines.append("    @property")
                        lines.append(f"    def {item.name}(self) -> {return_type}: ...")
                    elif any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in item.decorator_list):
                        lines.append("    @staticmethod")
                        lines.append(f"    def {item.name}({params}) -> {return_type}: ...")
                    elif any(isinstance(d, ast.Name) and d.id == "classmethod" for d in item.decorator_list):
                        lines.append("    @classmethod")
                        lines.append(f"    def {item.name}({params}) -> {return_type}: ...")
                    else:
                        lines.append(f"    def {item.name}({params}) -> {return_type}: ...")

        # If no methods, add ellipsis
        if not has_methods:
            lines.append("    ...")

        return "\n".join(lines)

    def _get_function_params(self, func: ast.FunctionDef) -> str:
        """Extract function parameters as a string."""
        params = []
        args = func.args

        # Regular args
        for i, arg in enumerate(args.args):
            param_str = arg.arg
            if arg.annotation:
                param_str += f": {ast.unparse(arg.annotation)}"
            # Check if it has a default
            default_offset = len(args.args) - len(args.defaults)
            if i >= default_offset:
                default = args.defaults[i - default_offset]
                param_str += f" = {ast.unparse(default)}"
            params.append(param_str)

        # *args
        if args.vararg:
            vararg_str = f"*{args.vararg.arg}"
            if args.vararg.annotation:
                vararg_str += f": {ast.unparse(args.vararg.annotation)}"
            params.append(vararg_str)

        # Keyword-only args
        for i, arg in enumerate(args.kwonlyargs):
            param_str = arg.arg
            if arg.annotation:
                param_str += f": {ast.unparse(arg.annotation)}"
            if i < len(args.kw_defaults) and args.kw_defaults[i] is not None:
                param_str += f" = {ast.unparse(args.kw_defaults[i])}"
            params.append(param_str)

        # **kwargs
        if args.kwarg:
            kwarg_str = f"**{args.kwarg.arg}"
            if args.kwarg.annotation:
                kwarg_str += f": {ast.unparse(args.kwarg.annotation)}"
            params.append(kwarg_str)

        return ", ".join(params)

    def _get_return_annotation(self, func: ast.FunctionDef) -> str:
        """Get the return type annotation."""
        if func.returns:
            return ast.unparse(func.returns)
        return "Any"

    def _collect_non_ugen_stubs(self) -> list[str]:
        """Collect stubs for non-@ugen classes."""
        if not self.non_ugen_classes:
            return []

        # Re-parse to get class nodes
        source = self.source_path.read_text()
        tree = ast.parse(source)

        stubs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in self.non_ugen_classes:
                stubs.append(self._generate_non_ugen_stub(node))

        return stubs

    def generate(self) -> str:
        """Generate complete stub file content."""
        # Read and parse source file
        source = self.source_path.read_text()
        tree = ast.parse(source)
        self.visit(tree)

        # Build stub content
        lines = []

        # Add standard imports needed for stubs
        lines.extend(
            [
                "from typing import Any",
                "",
                "from supriya.typing import CalculationRateLike",
                "from supriya.ugens.core import UGen, UGenOperable, UGenRecursiveInput, UGenScalar, UGenScalarInput, UGenVector, UGenVectorInput",
                "",
            ]
        )

        # Add non-@ugen classes first
        non_ugen_stubs = self._collect_non_ugen_stubs()
        for stub in non_ugen_stubs:
            lines.append(stub)
            lines.append("")

        # Add @ugen classes
        for class_stub in self.ugen_classes:
            lines.append(class_stub)
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"


def main():
    """Generate stub files for all UGen modules."""
    root = Path(__file__).parent.parent
    ugens_dir = root / "supriya" / "ugens"

    # Get all .py files in ugens directory (excluding __init__ and core)
    ugen_files = [
        f
        for f in ugens_dir.glob("*.py")
        if f.stem not in ["__init__", "core", "compilers", "factories"]
    ]

    for ugen_file in sorted(ugen_files):
        print(f"Processing {ugen_file.name}...")
        generator = UGenStubGenerator(ugen_file)
        stub_content = generator.generate()

        # Only write stub if there are classes
        if generator.ugen_classes or generator.non_ugen_classes:
            stub_file = ugen_file.with_suffix(".pyi")
            stub_file.write_text(stub_content)
            print(f"  Generated {stub_file.name} ({len(generator.ugen_classes)} @ugen, {len(generator.non_ugen_classes)} other)")
        else:
            print(f"  No classes found, skipping")


if __name__ == "__main__":
    main()
