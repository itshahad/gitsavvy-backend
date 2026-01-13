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
    ".sql",
}

FUNC_HINTS = ("function", "method", "constructor")
CLASS_HINTS = ("class", "interface", "struct", "trait", "protocol", "object")

DECL_HINTS = ("declaration", "definition", "item")
SPEC_SUFFIX = "_specifier"