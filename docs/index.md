---
description: "Graph-based RAG system that parses multi-language codebases with Tree-sitter, builds knowledge graphs, and enables natural language querying, editing, and optimization."
---

# ZeroGate-Red-Teaming

**The ultimate RAG for your monorepo.** Query, understand, and edit multi-language codebases with the power of AI and knowledge graphs.

<p align="center">
  <img src="assets/demo.gif" alt="ZeroGate-Red-Teaming Demo">
</p>

## What is ZeroGate-Red-Teaming?

ZeroGate-Red-Teaming is an accurate Retrieval-Augmented Generation (RAG) system that analyzes multi-language codebases using Tree-sitter, builds comprehensive knowledge graphs in Memgraph, and enables natural language querying of codebase structure and relationships as well as editing capabilities.

## Key Features

- **Multi-Language Support** for Python, TypeScript, JavaScript, Rust, Java, C++, Go, Lua, and more
- **Tree-sitter Parsing** for robust, language-agnostic AST analysis
- **Knowledge Graph Storage** using Memgraph for interconnected codebase structure
- **Natural Language Querying** to ask questions about your code in plain English
- **AI-Powered Cypher Generation** with Google Gemini, OpenAI, and Ollama support
- **Code Snippet Retrieval** with actual source code for found functions and methods
- **Advanced File Editing** with AST-based function targeting and visual diff previews
- **Shell Command Execution** for running tests and CLI tools
- **Interactive Code Optimization** with language-specific best practices
- **Reference-Guided Optimization** using your own coding standards
- **Dependency Analysis** from `pyproject.toml`
- **Semantic Code Search** using UniXcoder embeddings to find functions by intent
- **MCP Server Integration** for seamless use with Claude Code
- **Real-Time Graph Updates** via file watcher for active development

## Quick Start

```bash
pip install ZeroGate-Red-Teaming
docker compose up -d
cgr start --repo-path ./my-project --update-graph --clean
```

See the [Installation](getting-started/installation.md) guide for full setup instructions.

## Enterprise Services

ZeroGate-Red-Teaming is open source and free to use. For organizations that need more, we offer **fully managed cloud-hosted solutions** and **on-premise deployments**.

[View plans & pricing at ZeroGate-Red-Teaming.com](https://ZeroGate-Red-Teaming.com/enterprise){ .md-button }
