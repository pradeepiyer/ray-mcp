#!/usr/bin/env python3
"""Custom linting script to catch parameter passing issues in tool functions."""

import ast
import os
import sys
from pathlib import Path
from typing import List, Tuple


class ToolFunctionLinter(ast.NodeVisitor):
    """AST visitor to detect problematic patterns in tool functions."""
    
    def __init__(self, filename: str):
        self.filename = filename
        self.issues = []
        self.in_tool_function = False
        self.function_name = None
        
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definitions to check for tool functions."""
        # Check if this is a tool function (has @server.call_tool() decorator)
        is_tool_function = False
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Attribute):
                if decorator.attr == 'call_tool':
                    is_tool_function = True
                    break
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'call_tool':
                    is_tool_function = True
                    break
        
        if is_tool_function:
            self.in_tool_function = True
            self.function_name = node.name
            self.generic_visit(node)
            self.in_tool_function = False
            self.function_name = None
        else:
            self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Visit function calls to check for problematic patterns."""
        if not self.in_tool_function:
            self.generic_visit(node)
            return
            
        # Check for locals() usage
        if isinstance(node.func, ast.Name) and node.func.id == 'locals':
            self.issues.append({
                'line': node.lineno,
                'message': f"locals() usage detected in tool function '{self.function_name}'. "
                          f"This can cause unexpected parameters to be passed. "
                          f"Use explicit parameter dictionaries instead."
            })
        
        # Check for execute_tool calls with locals()
        if (isinstance(node.func, ast.Attribute) and 
            node.func.attr == 'execute_tool' and 
            len(node.args) >= 2):
            
            # Check if the second argument is a locals() call
            if isinstance(node.args[1], ast.Call) and isinstance(node.args[1].func, ast.Name):
                if node.args[1].func.id == 'locals':
                    self.issues.append({
                        'line': node.lineno,
                        'message': f"execute_tool() called with locals() in function '{self.function_name}'. "
                                  f"This can pass unexpected parameters like 'tool_registry'. "
                                  f"Use explicit parameter dictionaries instead."
                    })
        
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit async function definitions (same logic as regular functions)."""
        # Check if this is a tool function
        is_tool_function = False
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Attribute):
                if decorator.attr == 'call_tool':
                    is_tool_function = True
                    break
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'call_tool':
                    is_tool_function = True
                    break
        
        if is_tool_function:
            self.in_tool_function = True
            self.function_name = node.name
            self.generic_visit(node)
            self.in_tool_function = False
            self.function_name = None
        else:
            self.generic_visit(node)


def lint_file(filepath: Path) -> List[dict]:
    """Lint a single file for tool function issues."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        linter = ToolFunctionLinter(str(filepath))
        linter.visit(tree)
        
        return linter.issues
    except SyntaxError as e:
        return [{
            'line': e.lineno,
            'message': f"Syntax error: {e.msg}"
        }]
    except Exception as e:
        return [{
            'line': 0,
            'message': f"Error parsing file: {e}"
        }]


def main():
    """Main linting function."""
    # Get the project root
    project_root = Path(__file__).parent.parent
    
    # Files to check
    tool_function_files = [
        project_root / "ray_mcp" / "tool_functions.py",
    ]
    
    all_issues = []
    
    for filepath in tool_function_files:
        if filepath.exists():
            issues = lint_file(filepath)
            for issue in issues:
                all_issues.append({
                    'file': str(filepath),
                    'line': issue['line'],
                    'message': issue['message']
                })
    
    # Report issues
    if all_issues:
        print("Tool function linting issues found:")
        print("=" * 50)
        for issue in all_issues:
            print(f"{issue['file']}:{issue['line']}: {issue['message']}")
        print("=" * 50)
        print(f"Total issues: {len(all_issues)}")
        sys.exit(1)
    else:
        print("No tool function linting issues found.")
        sys.exit(0)


if __name__ == "__main__":
    main() 