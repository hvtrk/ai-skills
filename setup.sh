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
CYAN="\033[0;36m"
NC="\033[0m"

DRY_RUN=false
PROJECT_DIR=""
ACTION="global"

usage() {
    echo -e "${BOLD}AI Skills Installer & Multi-Harness Synchronizer${NC}"
    echo ""
    echo "Usage:"
    echo "  ./setup.sh [options]"
    echo ""
    echo "Options:"
    echo "  --global              Install/symlink skills globally across all agent harnesses (default)"
    echo "  --project <dir>       Link skills & rules directly into a specific project repository"
    echo "  --import              Import newly installed skills from ~/.agents/skills into ~/ai-skills"
    echo "  --status              Show sync status across all agent harnesses"
    echo "  --dry-run             Show what links and directories would be created without making changes"
    echo "  -h, --help            Show this help message"
    echo ""
    exit 0
}

# Parse command-line flags
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --global) ACTION="global" ;;
        --import) ACTION="import" ;;
        --status) ACTION="status" ;;
        --dry-run) DRY_RUN=true ;;
        --project) ACTION="project"; PROJECT_DIR="$2"; shift ;;
        -h|--help) usage ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; usage ;;
    esac
    shift
done

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_cyan() { echo -e "${CYAN}$1${NC}"; }

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

cleanup_broken_symlinks() {
    local target_dir="$1"
    if [ -d "$target_dir" ]; then
        find "$target_dir" -type l ! -exec test -e {} \; -delete 2>/dev/null || true
    fi
}

sync_harness_skills() {
    local harness_name="$1"
    local target_dir="$2"

    log_info "Synchronizing $harness_name skills to: $target_dir"
    if [ "$DRY_RUN" = false ]; then
        mkdir -p "$target_dir"
        cleanup_broken_symlinks "$target_dir"
    fi

    for skill_dir in "$SKILLS_SRC"/*; do
        if [ -d "$skill_dir" ]; then
            skill_name="$(basename "$skill_dir")"
            link_item "$skill_dir" "$target_dir/$skill_name"
        fi
    done
}

show_status() {
    echo -e "${BOLD}====================================================${NC}"
    echo -e "${BOLD}         AI Skills Repository Status                ${NC}"
    echo -e "${BOLD}====================================================${NC}"
    echo ""
    echo -e "${BOLD}Central Skills in ~/ai-skills/skills:${NC}"
    local count=0
    for skill_dir in "$SKILLS_SRC"/*; do
        if [ -d "$skill_dir" ]; then
            echo "  - $(basename "$skill_dir")"
            count=$((count + 1))
        fi
    done
    echo -e "${GREEN}Total curated skills: $count${NC}"
    echo ""

    echo -e "${BOLD}Harness Sync Destinations:${NC}"
    local harnesses=(
        "Google Antigravity|$HOME/.gemini/config/skills"
        "Claude Code|$HOME/.claude/skills"
        "OpenCode / Codex|$HOME/.config/opencode/skills"
        "Global Agents Harness|$HOME/.agents/skills"
    )

    for h in "${harnesses[@]}"; do
        IFS="|" read -r h_name h_path <<< "$h"
        if [ -d "$h_path" ]; then
            local linked_count=$(find "$h_path" -maxdepth 1 -type l | wc -l | tr -d ' ')
            local dir_count=$(find "$h_path" -maxdepth 1 -type d ! -path "$h_path" | wc -l | tr -d ' ')
            echo -e "  • ${BOLD}$h_name${NC}: $h_path"
            echo -e "    └─ Symlinked skills: ${GREEN}$linked_count${NC} | Standalone directories: ${YELLOW}$dir_count${NC}"
        else
            echo -e "  • ${BOLD}$h_name${NC}: ${RED}Not configured / missing folder${NC} ($h_path)"
        fi
    done
    echo ""
}

import_new_skills() {
    log_info "Scanning ~/.agents/skills for unmanaged skills from 'npx skills add'..."
    local unmanaged_count=0
    
    if [ ! -d "$HOME/.agents/skills" ]; then
        log_warn "~/.agents/skills does not exist. Nothing to import."
        return
    fi

    for item in "$HOME/.agents/skills"/*; do
        if [ -d "$item" ] && [ ! -L "$item" ]; then
            local skill_name="$(basename "$item")"
            if [ ! -d "$SKILLS_SRC/$skill_name" ]; then
                echo -e "Found unmanaged skill: ${YELLOW}$skill_name${NC}"
                if [ "$DRY_RUN" = false ]; then
                    cp -R "$item" "$SKILLS_SRC/$skill_name"
                    log_success "Imported $skill_name into ~/ai-skills/skills/"
                else
                    log_info "(Dry-run) Would import $skill_name -> $SKILLS_SRC/$skill_name"
                fi
                unmanaged_count=$((unmanaged_count + 1))
            fi
        fi
    done

    if [ "$unmanaged_count" -eq 0 ]; then
        log_success "No new unmanaged skills found to import."
    else
        log_success "Imported $unmanaged_count new skill(s). Run './setup.sh --global' to distribute."
    fi
}

echo -e "${BOLD}====================================================${NC}"
echo -e "${BOLD}   AI Engineering Skills Hub Setup (Multi-Agent)    ${NC}"
echo -e "${BOLD}====================================================${NC}"
echo ""

if [ "$ACTION" = "status" ]; then
    show_status
    exit 0
fi

if [ "$ACTION" = "import" ]; then
    import_new_skills
    exit 0
fi

if [ "$ACTION" = "global" ]; then
    # 1. Antigravity (~/.gemini/config/skills)
    sync_harness_skills "Antigravity (Google AGY)" "$HOME/.gemini/config/skills"

    # 2. Claude Code (~/.claude/skills)
    sync_harness_skills "Claude Code" "$HOME/.claude/skills"
    CLAUDE_DIR="$HOME/.claude"
    CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
    if [ ! -f "$CLAUDE_MD" ] && [ "$DRY_RUN" = false ] && [ -f "$SCRIPT_DIR/adapters/claude/global_claude.md" ]; then
        cp "$SCRIPT_DIR/adapters/claude/global_claude.md" "$CLAUDE_MD"
        log_success "Created global Claude instructions at $CLAUDE_MD"
    fi

    # 3. OpenCode / Codex (~/.config/opencode/skills)
    sync_harness_skills "OpenCode / Codex" "$HOME/.config/opencode/skills"

    # 4. Global Agents Harness (~/.agents/skills)
    sync_harness_skills "Global Agents Harness" "$HOME/.agents/skills"

    echo ""
    log_success "All agent harnesses successfully synchronized with ~/ai-skills repository!"
    echo -e "Skills are now available globally in Antigravity, Claude Code, OpenCode, and ~/.agents."
fi

# 5. Optional Project-Level Setup
if [ "$ACTION" = "project" ] && [ -n "$PROJECT_DIR" ]; then
    log_info "Configuring project repository at: $PROJECT_DIR"
    TARGET_AGENTS="$PROJECT_DIR/.agents"
    TARGET_CURSOR="$PROJECT_DIR/.cursorrules"

    if [ "$DRY_RUN" = false ]; then
        mkdir -p "$TARGET_AGENTS"
    fi

    link_item "$SKILLS_SRC" "$TARGET_AGENTS/skills"
    link_item "$RULES_SRC" "$TARGET_AGENTS/rules.md"
    if [ -f "$SCRIPT_DIR/adapters/cursor/base.cursorrules" ]; then
        link_item "$SCRIPT_DIR/adapters/cursor/base.cursorrules" "$TARGET_CURSOR"
    fi
    log_success "Project-level links configured for: $PROJECT_DIR"
fi
