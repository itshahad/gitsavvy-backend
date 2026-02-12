import re
from tree_sitter_language_pack import SupportedLanguage

REPOS_PATH = "repos"

SHA1_RE = re.compile(r"^[0-9a-f]{40}$")

SKIP_EXT = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    ".mp4",
    ".mov",
    ".avi",
    ".mp3",
    ".wav",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".class",
    ".jar",
}

SKIP_DIR_MARKERS = {
    "node_modules/",
    "dist/",
    "build/",
    ".next/",
    ".nuxt/",
    ".git/",
    ".idea/",
    ".vscode/",
    "coverage/",
    ".venv/",
    "venv/",
    "__pycache__/",
    ".pytest_cache/",
    "vendor/",
    "target/",
}

IMPORTANT_FILES_EXACT = {
    "readme.md",
    "readme.rst",
    "readme.txt",
    "license",
    "license.md",
    "license.txt",
    "contributing.md",
    "code_of_conduct.md",
    "security.md",
    "changelog.md",
    "pyproject.toml",
    "requirements.txt",
    "poetry.lock",
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "dockerfile",
    "compose.yml",
    "compose.yaml",
    ".env.example",
}

IMPORTANT_PREFIXES = (
    "docs/",
    ".github/",
    "src/",
    "app/",
    "lib/",
    "packages/",
)


AST_LANG_EXT = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".kt",
    ".go",
    ".c",
    ".cpp",
    ".cs",
    ".php",
    ".swift",
}

TEXT_LANG_EXT = {
    ".md",
    ".rst",
    ".txt",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".html",
    ".css",
    ".scss",
    ".sh",
}

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

BINARY_FILE_MAGICS = {
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"GIF87a",
    b"GIF89a",
    b"BM",
    b"RIFF",
    b"%PDF",
    b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
    b"PK\x03\x04",
    b"{\\rtf",
    b"\x1f\x8b",
    b"BZh",
    b"\xfd7zXZ",
    b"7z\xbc\xaf\x27\x1c",
    b"Rar!",
    b"MZ",
    b"\x7fELF",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
    b"\xfe\xed\xfa\xce",
    b"\xfe\xed\xfa\xcf",
    b"OggS",
    b"ID3",
    b"fLaC",
    b"\x00\x00\x00\x18ftyp",
    b"\x00\x00\x00 ftyp",
    b"\x00\x01\x00\x00",
    b"OTTO",
    b"wOFF",
    b"wOF2",
    b"SQLite format 3\x00",
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

# FUNC_HINTS = ("function", "method", "constructor")
# CLASS_HINTS = ("class", "interface", "struct", "trait", "protocol", "object")
# DECL_HINTS = ("declaration", "definition", "item")
# SPEC_SUFFIX = "_specifier"

# BINARY_FILE_MAGICS = {
#     #null
#     b"\x00",
#     # Images
#     b"\x89PNG\r\n\x1a\n",          # PNG
#     b"\xff\xd8\xff",               # JPEG
#     b"GIF87a", b"GIF89a",           # GIF
#     b"BM",                          # BMP
#     b"RIFF",                        # WEBP / AVI / WAV (needs RIFF check)

#     # Documents
#     b"%PDF",                       # PDF
#     b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",  # Old MS Office (DOC, XLS, PPT)
#     b"PK\x03\x04",                 # ZIP / DOCX / XLSX / JAR / APK / ODT
#     b"{\\rtf",                     # RTF

#     # Archives / compression
#     b"\x1f\x8b",                   # GZIP
#     b"BZh",                        # BZIP2
#     b"\xfd7zXZ",                   # XZ
#     b"7z\xbc\xaf\x27\x1c",         # 7-Zip
#     b"Rar!",                       # RAR

#     # Executables / binaries
#     b"MZ",                         # Windows EXE / DLL
#     b"\x7fELF",                    # Linux ELF
#     b"\xcf\xfa\xed\xfe",           # Mach-O (macOS)
#     b"\xca\xfe\xba\xbe",           # Mach-O fat
#     b"\xfe\xed\xfa\xce",           # Mach-O (32-bit)
#     b"\xfe\xed\xfa\xcf",           # Mach-O (64-bit)

#     # Media
#     b"OggS",                       # OGG
#     b"ID3",                        # MP3
#     b"fLaC",                       # FLAC
#     b"\x00\x00\x00\x18ftyp",       # MP4
#     b"\x00\x00\x00 ftyp",

#     # Fonts
#     b"\x00\x01\x00\x00",           # TTF
#     b"OTTO",                       # OTF
#     b"wOFF", b"wOF2",               # WOFF / WOFF2

#     # SQLite (often named .db/.txt in tests)
#     b"SQLite format 3\x00",
# }
