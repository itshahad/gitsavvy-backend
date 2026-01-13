# DB schema
https://drive.google.com/file/d/10ibLK4_cq8hO5rsIVx31JhRKaYNi4pvc/view?usp=sharing


# Authentication: 

- Use Github OAuth
- Retreive user profile data from `github-api`
- if first time. store user data in db


# Onboarding

- Ask user about preferences:
    - programming languages
    - topics

# Add projects to site:

- in admin dashboared, we bulk add repos with its url

# Process repos:
## Indexing: 

1. get repo metadata
2. download repo
3. retrieve selected files
4. for each file: create AST with tree-sitter for code files, for text files, make splitting by num of lines, take an overlapping lines between chunks
5. take nodes and embed it
	- `FILE_OUTLINE` chunk (imports/exports + symbol list)
	- `CLASS_OUTLINE` chunks (signature + method names; **no bodies**)
	- `FUNCTION/METHOD_BODY` chunks (full body; split if too big)
	- include header with embeddings to reserve semantics:
```
File: src/services/github.ts
Language: TypeScript
Symbol: function fetchRepoTree
Lines: 120-210
Parent: class GitHubIndexer
----
<actual code here>
```
6. store the actual code in db
7. store embedding_vector in vector db
8. delete repo after finishing all files

## Documentation:
1. Generate summaries for leaf chunks (functions/methods)
	- Ask LLM to output structured JSON:
		- `one_line_purpose`
		- `inputs` (params)
		- `outputs` (return)
		- `side_effects` (DB/network/files)
		- `calls` (important functions/classes mentioned)
	- Save result into chunks.summary_text
2. Build per-file docs
	- `FILE_OUTLINE` chunk
	- all `CLASS_OUTLINE` chunks in that file
	- all `FUNC_BODY` chunks **summaries** in that file
3. Build repo-level docs (README + architecture)
	1. Identify “important files”:
	    - easiest MVP: top-level paths + common entrypoints (`main`, `app`, `index`, `server`, `manage`, `cli`, `src/`)
	    - better: vector-search over `FILE_OUTLINE` chunks for queries like:
	        - “entry point”, “server startup”, “configuration”, “database”, “authentication”
	2. Feed LLM:
	    - repository metadata
	    - folder tree (if you stored it)
	    - a bundle of the **most important module docs or outlines**
	3. Generate:
	    - what project does
	    - how to run
	    - key architecture components
	    - where to look for X

## Recommendation
