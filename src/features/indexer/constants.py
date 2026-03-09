from tree_sitter_language_pack import SupportedLanguage


BLOCK_TYPES = {
    "block",
    "statement_block",
    "compound_statement",
    "if_statement",
    "for_statement",
    "while_statement",
    "do_statement",
    "try_statement",
    "switch_statement",
    "with_statement",
    "else_clause",
    "elif_clause",
    "catch_clause",
    "finally_clause",
    "case_clause",
}


EXT_TO_LANG: dict[str, SupportedLanguage] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".java": "java",
    ".kt": "kotlin",
    ".go": "go",
    ".c": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".swift": "swift",
    # ".sh": "bash",
}

FUNCTION_NODE_TYPES = {
    "python": {"function_definition"},
    "javascript": {
        "function_declaration",
        "function_expression",
        # "arrow_function",
        "method_definition",
    },
    "typescript": {
        "function_declaration",
        "function_expression",
        # "arrow_function",
        "method_definition",
    },
    "tsx": {
        "function_declaration",
        "function_expression",
        # "arrow_function",
        "method_definition",
    },
    "java": {"method_declaration", "constructor_declaration"},
    "kotlin": {
        "function_declaration",
        "constructor_declaration",
        "secondary_constructor",
    },
    "go": {"function_declaration", "method_declaration"},
    "c": {"function_definition"},
    "cpp": {"function_definition", "constructor_or_destructor_definition"},
    "csharp": {"method_declaration", "constructor_declaration"},
    "php": {"function_definition", "method_declaration"},
    "swift": {
        "function_declaration",
        "initializer_declaration",
        "deinitializer_declaration",
    },
}

CLASS_NODE_TYPES: dict[str, set[str]] = {
    "python": {"class_definition"},
    "javascript": {"class_declaration"},
    "typescript": {"class_declaration", "interface_declaration"},
    "tsx": {"class_declaration", "interface_declaration"},
    "java": {"class_declaration", "interface_declaration"},
    "kotlin": {"class_declaration", "object_declaration", "interface_declaration"},
    "go": set(),  # go uses types; class-like structures differ
    "c": set(),
    "cpp": {"class_specifier", "struct_specifier"},
    "csharp": {"class_declaration", "interface_declaration", "struct_declaration"},
    "php": {"class_declaration", "interface_declaration", "trait_declaration"},
    "swift": {
        "class_declaration",
        "struct_declaration",
        "protocol_declaration",
        "enum_declaration",
    },
}

BODY_FIELD_HINTS = (
    "body",
    "block",
    "members",
    "suite",
)

BODY_NODE_TYPES = (
    # C / C++
    "compound_statement",
    "field_declaration_list",
    # JS / TS / TSX
    "statement_block",
    # Kotlin
    "class_body",
    "function_body",
    # Java
    "class_body",
    "interface_body",
    # Common / generic
    "block",
    "declaration_list",
    "interface_body",
)


SKIP_NODE_TYPES = {
    "access_specifier",
}
