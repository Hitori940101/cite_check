# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

**Cite Check** — a citation verification system for academic papers. Part of the DeepScientist paper-tooling ecosystem alongside `paper_check` (format checking) and `paper_form_check` (AI-powered review).

## Current Status

This project is in the **pre-development / planning** phase. No code has been written yet.

## Sibling Projects

- `../paper_check/` — Web-based academic paper format detection (FastAPI + Vue 3, Python 3.11+, SQLite). Handles `.docx`/`.doc` upload, template-based format validation, and auto-correction.
- `../paper_form_check/` — AI-powered paper content and format checking (Docker-based, FastAPI backend).

When designing this project's architecture, refer to sibling projects for established patterns (project structure, API conventions, document parsing approaches).

## Project Rules

- **每次功能改动测试合格后必须 git commit**：实现一个功能 → 运行测试通过 → 立即提交版本。不允许积累多个未提交的功能变更。提交信息遵循 Conventional Commits（`feat:`, `fix:`, `docs:` 等）。

## Conventions

- **Package manager**: `uv` (preferred over conda/pip for new projects)
- **Python**: 3.11+
- **Configuration**: Hydra + OmegaConf when config composition is needed
- **Working directories**: `/plan` for planning docs, `/temp` for scratch files (create as needed)
