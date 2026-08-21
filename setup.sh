#!/usr/bin/env bash
set -e

# AI Skills Multi-Harness Setup & Synchronizer
# Author: Rahul (@hvtrk)
# Repo: git@github.com:hvtrk/ai-skill-rules.git

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$SCRIPT_DIR/skills"
RULES_SRC="$SCRIPT_DIR/rules/core.md"

# Colors for terminal output
BOLD="\033[1m"
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"

DRY_RUN=false
PROJECT_DIR=""

usage() {
    echo -e "${BOLD}AI Skills Installer & Synchronizer${NC}"
    echo ""
    echo "Usage:"
    echo "  ./setup.sh [options]"
    echo ""
    echo "Options:"
    echo "  --global              Install/symlink skills globally across all agent harnesses (default)"
    echo "  --project <dir>       Link skills & rules directly into a specific project repository"
    echo "  --dry-run             Show what links and directories would be created without making changes"
    echo "  -h, --help            Show this help message"
    echo ""
    exit 0
}

# Parse command-line flags
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --global) ;;
        --dry-run) DRY_RUN=true ;;
        --project) PROJECT_DIR="$2"; shift ;;
        -h|--help) usage ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; usage ;;
    esac
    shift
done

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

link_item() {
    local src="$1"
    local dest="$2"

    if [ "$DRY_RUN" = true ]; then
        log_info "(Dry-run) Would link: $src -> $dest"
        return
    fi

    mkdir -p "$(dirname "$dest")"
    if [ -L "$dest" ] || [ -e "$dest" ]; then
        rm -rf "$dest"
    fi
    ln -s "$src" "$dest"
    log_success "Linked: $dest -> $src"
}

echo -e "${BOLD}====================================================${NC}"
echo -e "${BOLD}   AI Engineering Skills Hub Setup (Multi-Agent)    ${NC}"
echo -e "${BOLD}====================================================${NC}"
echo ""

# -----------------------------------------------------------------------------
# 1. Antigravity Configuration (~/.gemini/config/skills)
# -----------------------------------------------------------------------------
log_info "Configuring Antigravity (Google AGY)..."
ANTIGRAVITY_SKILLS_DIR="$HOME/.gemini/config/skills"

if [ "$DRY_RUN" = false ]; then
    mkdir -p "$ANTIGRAVITY_SKILLS_DIR"
fi

for skill_dir in "$SKILLS_SRC"/*; do
    if [ -d "$skill_dir" ]; then
        skill_name="$(basename "$skill_dir")"
        link_item "$skill_dir" "$ANTIGRAVITY_SKILLS_DIR/$skill_name"
    fi
done

# -----------------------------------------------------------------------------
# 2. Claude Code Configuration (~/.claude)
# -----------------------------------------------------------------------------
log_info "Configuring Claude Code..."
CLAUDE_DIR="$HOME/.claude"
CLAUDE_SKILLS_DIR="$CLAUDE_DIR/skills"

if [ "$DRY_RUN" = false ]; then
    mkdir -p "$CLAUDE_SKILLS_DIR"
fi

for skill_dir in "$SKILLS_SRC"/*; do
    if [ -d "$skill_dir" ]; then
        skill_name="$(basename "$skill_dir")"
        link_item "$skill_dir" "$CLAUDE_SKILLS_DIR/$skill_name"
    fi
done

CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
if [ ! -f "$CLAUDE_MD" ] && [ "$DRY_RUN" = false ]; then
    cp "$SCRIPT_DIR/adapters/claude/global_claude.md" "$CLAUDE_MD"
    log_success "Created global Claude instructions at $CLAUDE_MD"
fi

# -----------------------------------------------------------------------------
# 3. OpenCode / Codex Configuration (~/.config/opencode)
# -----------------------------------------------------------------------------
log_info "Configuring OpenCode / Codex..."
OPENCODE_DIR="$HOME/.config/opencode/skills"
if [ "$DRY_RUN" = false ]; then
    mkdir -p "$OPENCODE_DIR"
fi

for skill_dir in "$SKILLS_SRC"/*; do
    if [ -d "$skill_dir" ]; then
        skill_name="$(basename "$skill_dir")"
        link_item "$skill_dir" "$OPENCODE_DIR/$skill_name"
    fi
done

# -----------------------------------------------------------------------------
# 4. Optional Project-Level Setup
# -----------------------------------------------------------------------------
if [ -n "$PROJECT_DIR" ]; then
    log_info "Configuring project repository at: $PROJECT_DIR"
    TARGET_AGENTS="$PROJECT_DIR/.agents"
    TARGET_CURSOR="$PROJECT_DIR/.cursorrules"

    if [ "$DRY_RUN" = false ]; then
        mkdir -p "$TARGET_AGENTS"
    fi

    link_item "$SKILLS_SRC" "$TARGET_AGENTS/skills"
    link_item "$RULES_SRC" "$TARGET_AGENTS/rules.md"
    link_item "$SCRIPT_DIR/adapters/cursor/base.cursorrules" "$TARGET_CURSOR"
    log_success "Project-level links configured for: $PROJECT_DIR"
fi

echo ""
echo -e "${GREEN}${BOLD}Setup complete! All skills and operating rules are active.${NC}"
echo -e "You can now use skills via slash commands (e.g. /fullstack-feature) or autonomous discovery in any agent."
