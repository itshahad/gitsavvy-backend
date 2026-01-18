import re

REPOS_PATH = "repos"

SKIP_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar",
    ".mp4", ".mov", ".avi", ".mp3", ".wav",
    ".exe", ".dll", ".so", ".dylib",
    ".bin", ".class", ".jar",
}

SKIP_DIR_MARKERS = {
    "node_modules/", "dist/", "build/", ".next/", ".nuxt/",
    ".git/", ".idea/", ".vscode/",
    "coverage/", ".venv/", "venv/",
    "__pycache__/", ".pytest_cache/",
    "vendor/", "target/",
}

IMPORTANT_FILES_EXACT = {
    "readme.md", "readme.rst", "readme.txt",
    "license", "license.md", "license.txt",
    "contributing.md", "code_of_conduct.md", "security.md",
    "changelog.md",
    "pyproject.toml", "requirements.txt", "poetry.lock",
    "package.json", "pnpm-lock.yaml", "yarn.lock",
    "dockerfile", "compose.yml", "compose.yaml", ".env.example",
}

IMPORTANT_PREFIXES = (
    "docs/",
    ".github/",
    "src/",
    "app/",
    "lib/",
    "packages/",
)

CODE_EXT = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".kt", ".go", ".rs", ".c", ".cpp", ".h",
    ".cs", ".php", ".rb", ".swift",
    ".md", ".rst", ".txt",
    ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg",
    ".html", ".css", ".scss",
    ".sh", ".bat",
}

FUNC_HINTS = ("function", "method", "constructor")
CLASS_HINTS = ("class", "interface", "struct", "trait", "protocol", "object")

DECL_HINTS = ("declaration", "definition", "item")
SPEC_SUFFIX = "_specifier"

AST_LANG_EXT = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".kt", ".go", ".rs",
    ".c", ".cpp", ".h", ".dart",
    ".cs", ".php", ".rb", ".swift", 
}

TEXT_LANG_EXT = {
    ".md", ".rst", ".txt",
    ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg",
    ".html", ".css", ".scss",
    ".sh", ".bat",
}

BINARY_FILE_MAGICS = {
    #null
    b"\x00",
    # Images
    b"\x89PNG\r\n\x1a\n",          # PNG
    b"\xff\xd8\xff",               # JPEG
    b"GIF87a", b"GIF89a",           # GIF
    b"BM",                          # BMP
    b"RIFF",                        # WEBP / AVI / WAV (needs RIFF check)

    # Documents
    b"%PDF",                       # PDF
    b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",  # Old MS Office (DOC, XLS, PPT)
    b"PK\x03\x04",                 # ZIP / DOCX / XLSX / JAR / APK / ODT
    b"{\\rtf",                     # RTF

    # Archives / compression
    b"\x1f\x8b",                   # GZIP
    b"BZh",                        # BZIP2
    b"\xfd7zXZ",                   # XZ
    b"7z\xbc\xaf\x27\x1c",         # 7-Zip
    b"Rar!",                       # RAR

    # Executables / binaries
    b"MZ",                         # Windows EXE / DLL
    b"\x7fELF",                    # Linux ELF
    b"\xcf\xfa\xed\xfe",           # Mach-O (macOS)
    b"\xca\xfe\xba\xbe",           # Mach-O fat
    b"\xfe\xed\xfa\xce",           # Mach-O (32-bit)
    b"\xfe\xed\xfa\xcf",           # Mach-O (64-bit)

    # Media
    b"OggS",                       # OGG
    b"ID3",                        # MP3
    b"fLaC",                       # FLAC
    b"\x00\x00\x00\x18ftyp",       # MP4
    b"\x00\x00\x00 ftyp",

    # Fonts
    b"\x00\x01\x00\x00",           # TTF
    b"OTTO",                       # OTF
    b"wOFF", b"wOF2",               # WOFF / WOFF2

    # SQLite (often named .db/.txt in tests)
    b"SQLite format 3\x00",
}

SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
