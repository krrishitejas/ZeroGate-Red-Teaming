---
description: "An advanced Automated Red Teaming Platform for multi-language codebases. Features Hybrid-Aware AI, Semgrep SAST, and Graph-based RAG using Tree-sitter to analyze, query, and identify security vulnerabilities."
---

# ZeroGate-Red-Teaming

**The ultimate Automated Red Teaming Platform for your entire codebase.** Query, understand, and secure multi-language applications with the power of Hybrid-Aware AI, Static Analysis, and Knowledge Graphs.

<p align="center">
  <img src="assets/demo.gif" alt="ZeroGate-Red-Teaming Demo">
</p>

## What is ZeroGate-Red-Teaming?

ZeroGate-Red-Teaming is a cutting-edge security evaluation system built by Rishi Tejas K R. It analyzes multi-language codebases using Tree-sitter, builds comprehensive knowledge graphs in Memgraph, and orchestrates a highly advanced "Hybrid-Aware" AI pipeline. By combining large cloud models (OpenAI/Google), local offline models (AirLLM/Ollama), and deterministic SAST scanners (Semgrep), it autonomously finds, maps, and remediates security vulnerabilities.

## Key Features

- **Hybrid-Aware AI Orchestration** intelligently routes tasks between Cloud APIs and Local/AirLLM models
- **Automated SAST Integration** with Semgrep for high-fidelity vulnerability detection
- **Multi-Language Support** for Python, TypeScript, JavaScript, Rust, Java, C++, Go, and more
- **Tree-sitter Parsing** for robust, language-agnostic AST analysis
- **Knowledge Graph Storage** using Memgraph for interconnected codebase security mapping
- **Natural Language Security Queries** to ask questions about attack vectors in plain English
- **AI-Powered Cypher Generation** translating natural queries into graph database searches
- **Advanced File Editing** with AST-based function targeting and visual diff previews for auto-remediation
- **Semantic Code Search** using local embeddings to find vulnerable intent vs just keyword matches

## Quick Start

```bash
pip install ZeroGate-Red-Teaming
docker compose up -d
cgr start --repo-path ./my-project --update-graph --clean
```

See the [Installation](getting-started/installation.md) guide for full setup instructions.

## Enterprise Services

ZeroGate-Red-Teaming is open source and designed for modern security teams. Need custom deployment or advanced threat rules?

[View GitHub Repository](https://github.com/krrishitejas/ZeroGate-Red-Teaming){ .md-button }
