#!/usr/bin/env bash
set -e

# AI Skills Multi-Harness Setup & Synchronizer
# Author: Rahul (@hvtrk)
# Repo: git@github.com:hvtrk/ai-skill-rules.git

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$SCRIPT_DIR/skills"
RULES_SRC="$SCRIPT_DIR/rules/core.md"
GLOBAL_MEMORY_DIR="$HOME/.agents/memory"
MEMORY_CORE="$SCRIPT_DIR/scripts/memory.py"
MCP_SYNC="$SCRIPT_DIR/scripts/mcp_sync.py"
MCP_MANIFEST="$SCRIPT_DIR/mcp/servers.json"

# Colors for terminal output
BOLD="\033[1m"
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
CYAN="\033[0;36m"
NC="\033[0m"

DRY_RUN=false
APPLY_MCP=false
PROJECT_DIR=""
ACTION="global"

# -----------------------------------------------------------------------------
# Declarative Harness Registry
# Format: "key|Display Name|Skills Directory Path|Extra Hook Name"
# -----------------------------------------------------------------------------
HARNESS_REGISTRY=(
    "antigravity|Google Antigravity|$HOME/.gemini/config/skills|sync_antigravity_extra"
    "claude|Claude Code|$HOME/.claude/skills|sync_claude_extra"
    "opencode|OpenCode|$HOME/.config/opencode/skills|"
    "global_agents|Global Agents Harness|$HOME/.agents/skills|"
)

usage() {
    echo -e "${BOLD}AI Skills Installer & Multi-Harness Synchronizer (v3.0)${NC}"
    echo ""
    echo "Usage:"
    echo "  ./setup.sh [options]"
    echo ""
    echo "Options:"
    echo "  --global              Install/symlink skills & seed global memory across all agent harnesses (default)"
    echo "  --antigravity         Install/symlink skills & rules specifically for Google Antigravity"
    echo "  --project <dir>       Link skills & rules directly into a specific project repository"
    echo "  --memory-init <dir>   Initialize workspace .memory/ hierarchy in a project (idempotent)"
    echo "  --import              Import newly installed skills from ~/.agents/skills into ~/ai-skills"
    echo "  --status              Show sync status across all agent harnesses & global memory"
    echo "  --sync-mcp            Preview MCP server manifest sync across harnesses (dry-run unless --apply)"
    echo "  --apply               Combine with --sync-mcp to write changes (default is preview-only)"
    echo "  --dry-run             Show what links and directories would be created without making changes"
    echo "  -h, --help            Show this help message"
    echo ""
    exit 0
}

# Parse command-line flags
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --global) ACTION="global" ;;
        --antigravity) ACTION="antigravity" ;;
        --import) ACTION="import" ;;
        --status) ACTION="status" ;;
        --sync-mcp) ACTION="sync_mcp" ;;
        --apply) APPLY_MCP=true ;;
        --dry-run) DRY_RUN=true ;;
        --project) ACTION="project"; PROJECT_DIR="$2"; shift ;;
        --memory-init) ACTION="memory_init"; PROJECT_DIR="$2"; shift ;;
        -h|--help) usage ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; usage ;;
    esac
    shift
done

if [ "$APPLY_MCP" = true ] && [ "$ACTION" != "sync_mcp" ]; then
    echo -e "${YELLOW}[WARN]${NC} --apply has no effect without --sync-mcp; ignoring."
fi

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

init_global_memory() {
    log_info "Verifying global memory at $GLOBAL_MEMORY_DIR..."
    if [ "$DRY_RUN" = true ]; then
        log_info "(Dry-run) Would ensure $GLOBAL_MEMORY_DIR exists with user-profile.md & conventions.md"
        return
    fi

    mkdir -p "$GLOBAL_MEMORY_DIR"
    
    if [ ! -f "$GLOBAL_MEMORY_DIR/user-profile.md" ]; then
        cat << 'EOF' > "$GLOBAL_MEMORY_DIR/user-profile.md"
# Global Developer Profile

Machine-wide preferences, developer identity, and operating environment.

## Environment & Tooling
- **OS**: macOS (zsh shell)
- **Editor / Harnesses**: Antigravity, Claude Code, Cursor, OpenCode/Codex
- **Package Managers**: pnpm / npm / pip / uv
- **Git**: Branch-first development (`v_X` for active dev, PR/merge into `master`)

## Workflow Preferences
- Prioritize minimal invasive changes.
- Avoid unnecessary external dependencies when standard library or existing helpers suffice.
- Output clean, structured markdown with concise explanations.
EOF
        log_success "Created global developer profile at $GLOBAL_MEMORY_DIR/user-profile.md"
    fi

    if [ ! -f "$GLOBAL_MEMORY_DIR/conventions.md" ]; then
        cat << 'EOF' > "$GLOBAL_MEMORY_DIR/conventions.md"
# Global Engineering Conventions

Universal coding principles and quality standards across all projects.

## Architecture & Code Design
1. **Layered Separation**: Strictly separate routing/transport, business logic/services, data access/repositories, and schema validation.
2. **Explicit Interfaces**: Use strict typing (TypeScript `strict: true`, Python type annotations with Pydantic/SQLModel).
3. **Evidence-First Implementation**: Inspect existing patterns before proposing new abstractions or third-party dependencies.

## Error Handling & Reliability
1. **Fail Explicitly**: Never swallow exceptions silently. Log meaningful contextual error messages.
2. **Boundary Validation**: Validate inputs at system boundaries (API endpoints, webhook receivers, CLI inputs).

## Code Style & Formatting
1. Keep functions focused and single-purpose.
2. Avoid unnecessary boilerplate and dead comments.
3. Self-documenting naming conventions over verbose comments.
EOF
        log_success "Created global conventions at $GLOBAL_MEMORY_DIR/conventions.md"
    fi
}

init_project_memory() {
    local target_dir="$1"
    if [ -z "$target_dir" ]; then
        echo -e "${RED}Error: Project directory not specified. Use --memory-init <project-dir>${NC}"
        exit 1
    fi

    if [ ! -f "$MEMORY_CORE" ]; then
        echo -e "${RED}Error: Memory Core not found at $MEMORY_CORE${NC}"
        exit 1
    fi

    log_info "Initializing project memory through the Memory Core: $target_dir/.memory"
    local memory_command=(python3 "$MEMORY_CORE" init "$target_dir")
    if [ "$DRY_RUN" = true ]; then
        memory_command+=(--dry-run)
    fi
    "${memory_command[@]}"
}

sync_antigravity_extra() {
    local src_gemini_md="$SCRIPT_DIR/adapters/antigravity/GEMINI.md"
    local rules_dir="$HOME/.gemini/config/rules"
    local target_rule="$rules_dir/memory.md"
    local global_gemini="$HOME/.gemini/GEMINI.md"

    if [ ! -f "$src_gemini_md" ]; then
        log_warn "Antigravity adapter GEMINI.md not found at $src_gemini_md"
        return
    fi

    # 1. Synchronize to ~/.gemini/config/rules/memory.md (hierarchical rule discovery)
    link_item "$src_gemini_md" "$target_rule"

    # 2. Synchronize to ~/.gemini/GEMINI.md (root global rule file) if empty, missing, or already a symlink
    if [ "$DRY_RUN" = true ]; then
        log_info "(Dry-run) Would verify global Antigravity rule at $global_gemini"
    else
        if [ ! -e "$global_gemini" ] || [ -L "$global_gemini" ]; then
            link_item "$src_gemini_md" "$global_gemini"
        elif [ -f "$global_gemini" ] && [ ! -s "$global_gemini" ]; then
            # File exists but is empty (0 bytes)
            link_item "$src_gemini_md" "$global_gemini"
        else
            log_info "Preserving existing non-empty $global_gemini (global rules active via $target_rule)"
        fi
    fi
}

sync_claude_extra() {
    local claude_dir="$HOME/.claude"
    local claude_md="$claude_dir/CLAUDE.md"
    local src_claude_md="$SCRIPT_DIR/adapters/claude/global_claude.md"

    if [ ! -f "$claude_md" ] && [ -f "$src_claude_md" ]; then
        if [ "$DRY_RUN" = true ]; then
            log_info "(Dry-run) Would create global Claude instructions at $claude_md"
        else
            mkdir -p "$claude_dir"
            cp "$src_claude_md" "$claude_md"
            log_success "Created global Claude instructions at $claude_md"
        fi
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
            local skill_name
            skill_name="$(basename "$skill_dir")"
            link_item "$skill_dir" "$target_dir/$skill_name"
        fi
    done
}

show_status() {
    echo -e "${BOLD}====================================================${NC}"
    echo -e "${BOLD}         AI Skills Repository Status (v3.0)         ${NC}"
    echo -e "${BOLD}====================================================${NC}"
    echo ""
    echo -e "${BOLD}Global Memory (~/.agents/memory/):${NC}"
    if [ -d "$GLOBAL_MEMORY_DIR" ]; then
        local user_p="missing"
        local conv_p="missing"
        [ -f "$GLOBAL_MEMORY_DIR/user-profile.md" ] && user_p="${GREEN}active${NC}"
        [ -f "$GLOBAL_MEMORY_DIR/conventions.md" ] && conv_p="${GREEN}active${NC}"
        echo -e "  • user-profile.md: $user_p"
        echo -e "  • conventions.md:  $conv_p"
    else
        echo -e "  • ${RED}Not initialized${NC}"
    fi
    echo ""

    echo -e "${BOLD}Antigravity Global Rules:${NC}"
    local ag_rule_p="missing"
    local ag_gemini_p="missing"
    [ -e "$HOME/.gemini/config/rules/memory.md" ] && ag_rule_p="${GREEN}active${NC}"
    [ -e "$HOME/.gemini/GEMINI.md" ] && ag_gemini_p="${GREEN}active${NC}"
    echo -e "  • ~/.gemini/config/rules/memory.md: $ag_rule_p"
    echo -e "  • ~/.gemini/GEMINI.md:              $ag_gemini_p"
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
    for h in "${HARNESS_REGISTRY[@]}"; do
        IFS="|" read -r h_key h_name h_path h_hook <<< "$h"
        if [ -d "$h_path" ]; then
            local linked_count
            linked_count=$(find "$h_path" -maxdepth 1 -type l | wc -l | tr -d ' ')
            local dir_count
            dir_count=$(find "$h_path" -maxdepth 1 -type d ! -path "$h_path" | wc -l | tr -d ' ')
            local broken_count
            broken_count=$(find "$h_path" -maxdepth 1 -type l ! -exec test -e {} \; -print 2>/dev/null | wc -l | tr -d ' ')
            
            echo -e "  • ${BOLD}$h_name${NC}: $h_path"
            echo -e "    └─ Symlinked: ${GREEN}$linked_count${NC} | Standalone: ${YELLOW}$dir_count${NC} | Broken: ${RED}$broken_count${NC}"
        else
            echo -e "  • ${BOLD}$h_name${NC}: ${RED}Not configured / missing folder${NC} ($h_path)"
        fi
    done
    echo ""

    echo -e "${BOLD}MCP Server Manifest (mcp/servers.json):${NC}"
    if [ -f "$MCP_SYNC" ] && [ -f "$MCP_MANIFEST" ]; then
        python3 "$MCP_SYNC" --manifest "$MCP_MANIFEST" list 2>&1 | sed 's/^/  /'
        echo -e "  ${CYAN}Run './setup.sh --sync-mcp' for a dry-run preview, add --apply to write.${NC}"
    else
        echo -e "  ${RED}Not available (missing scripts/mcp_sync.py or mcp/servers.json)${NC}"
    fi
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
            local skill_name
            skill_name="$(basename "$item")"
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

if [ "$ACTION" = "memory_init" ]; then
    init_project_memory "$PROJECT_DIR"
    exit 0
fi

if [ "$ACTION" = "sync_mcp" ]; then
    if [ ! -f "$MCP_SYNC" ]; then
        echo -e "${RED}Error: MCP sync script not found at $MCP_SYNC${NC}"
        exit 1
    fi
    mcp_command=(python3 "$MCP_SYNC" --manifest "$MCP_MANIFEST" sync --all)
    if [ "$APPLY_MCP" = true ]; then
        mcp_command+=(--apply)
    fi
    "${mcp_command[@]}"
    exit 0
fi

if [ "$ACTION" = "antigravity" ]; then
    init_global_memory
    sync_harness_skills "Google Antigravity" "$HOME/.gemini/config/skills"
    sync_antigravity_extra
    echo ""
    log_success "Google Antigravity harness successfully synchronized!"
    echo -e "Global rules installed at ~/.gemini/config/rules/memory.md and ~/.gemini/GEMINI.md."
    exit 0
fi

if [ "$ACTION" = "global" ]; then
    init_global_memory

    for h in "${HARNESS_REGISTRY[@]}"; do
        IFS="|" read -r h_key h_name h_path h_hook <<< "$h"
        sync_harness_skills "$h_name" "$h_path"
        if [ -n "$h_hook" ] && declare -f "$h_hook" > /dev/null; then
            "$h_hook"
        fi
    done

    echo ""
    log_success "All agent harnesses successfully synchronized with ~/ai-skills repository!"
    echo -e "Skills were linked to configured destinations. Memory retrieval remains agent-guided."
fi

# Optional Project-Level Setup
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

    init_project_memory "$PROJECT_DIR"

    log_success "Project-level links and memory configured for: $PROJECT_DIR"
fi
