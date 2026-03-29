#!/usr/bin/env bash
# =============================================================================
# Squad Loop Library — Shared functions for synthesis and context management
#
# Sourced by loop_runner.sh and test_synthesis.sh
# =============================================================================

# ---------- Synthesis Triggering ----------

# Check if synthesis should run this cycle.
# Args: $1=cycle_num, $2=synthesis_interval, $3=last_synthesis_cycle (empty if never)
# Returns 0 (true) if synthesis needed, 1 (false) otherwise
needs_synthesis() {
    local cycle_num=$1
    local interval=$2
    local last_synthesis=${3:-""}

    # Never synthesize on cycle 0
    if [ "$cycle_num" -le 0 ]; then
        return 1
    fi

    # If we have a last synthesis cycle, check distance
    if [ -n "$last_synthesis" ]; then
        local since_last=$(( cycle_num - last_synthesis ))
        if [ "$since_last" -lt "$interval" ]; then
            return 1
        fi
    fi

    # Trigger on multiples of interval
    if (( cycle_num % interval == 0 )); then
        return 0
    fi

    return 1
}

# Read the last synthesis cycle number from synthesis.md
# Args: $1=shared_dir
get_last_synthesis_cycle() {
    local synthesis_file="$1/knowledge/synthesis.md"
    if [ -f "$synthesis_file" ]; then
        # Extract cycle number from "Last updated: ... Cycle NN" or "Cycle NN"
        grep -oE 'Cycle [0-9]+' "$synthesis_file" | head -1 | grep -oE '[0-9]+' || echo ""
    else
        echo ""
    fi
}

# ---------- Context Assembly ----------

# Get experiment context for an agent, using synthesis when available.
# Scribe during synthesis gets full history; everyone else gets synthesis + last N experiments.
# Args: $1=agent_role, $2=phase, $3=shared_dir
# Outputs: experiment context to stdout
get_context_for_agent() {
    local agent=$1
    local phase=$2
    local shared_dir=$3
    local experiments_file="$shared_dir/knowledge/experiments.md"
    local synthesis_file="$shared_dir/knowledge/synthesis.md"
    local last_n=5

    # Scribe during synthesis/learn gets FULL experiments (needs everything to synthesize)
    if [ "$agent" = "scribe" ] && { [ "$phase" = "synthesis" ] || [ "$phase" = "learn" ]; }; then
        cat "$experiments_file"
        return
    fi

    # If synthesis exists and has content beyond the header, use it
    local synthesis_lines
    synthesis_lines=$(wc -l < "$synthesis_file" 2>/dev/null || echo "0")

    if [ "$synthesis_lines" -gt 5 ]; then
        # Provide synthesis
        echo "## Knowledge Synthesis (distilled from all experiments)"
        echo ""
        cat "$synthesis_file"
        echo ""

        # Plus last N experiments
        echo "## Recent Experiments (last $last_n)"
        echo ""
        # Extract last N experiment sections (delimited by ## C or --- markers)
        _extract_last_n_experiments "$experiments_file" "$last_n"
    else
        # No synthesis available — give full experiments
        cat "$experiments_file"
    fi
}

# Extract the last N experiment entries from experiments.md
# Experiments are delimited by "## " headers at level 2
# Args: $1=experiments_file, $2=n
_extract_last_n_experiments() {
    local file=$1
    local n=$2

    # Use awk to extract sections starting with "## C" or "## Squad Cycle"
    # and return the last N
    awk -v n="$n" '
    /^## (C[0-9]|Squad Cycle|Pre-Squad)/ {
        section_count++
        sections[section_count] = ""
    }
    section_count > 0 {
        sections[section_count] = sections[section_count] $0 "\n"
    }
    END {
        start = section_count - n + 1
        if (start < 1) start = 1
        for (i = start; i <= section_count; i++) {
            printf "%s", sections[i]
        }
    }
    ' "$file"
}

# ---------- History Trimming ----------

# Trim an agent's history file to keep only the last N entries.
# Older entries are moved to history_archive.md.
# Args: $1=history_file, $2=max_entries
trim_history() {
    local history_file=$1
    local max_entries=$2
    local archive_file="${history_file%.md}_archive.md"

    # Count entries (## Cycle headers)
    local entry_count
    entry_count=$(grep -c "^## Cycle" "$history_file" 2>/dev/null || echo "0")

    if [ "$entry_count" -le "$max_entries" ]; then
        return 0  # Nothing to trim
    fi

    local to_archive=$(( entry_count - max_entries ))

    # Use awk to split: first to_archive entries go to archive, rest stay
    awk -v cutoff="$to_archive" '
    BEGIN { entry_num = 0; in_header = 1 }
    /^## Cycle/ { entry_num++; in_header = 0 }
    {
        if (in_header) {
            # Header lines before first ## Cycle — keep in main file
            header = header $0 "\n"
        } else if (entry_num <= cutoff) {
            archive = archive $0 "\n"
        } else {
            keep = keep $0 "\n"
        }
    }
    END {
        # Write archive (append)
        if (archive != "") {
            print archive > "/dev/fd/3"
        }
        # Write kept entries with header
        printf "%s%s", header, keep
    }
    ' "$history_file" 3>>"$archive_file" > "${history_file}.tmp"

    mv "${history_file}.tmp" "$history_file"
}

# ---------- Context Budget ----------

# Estimate token count for a file (rough: words * 1.3)
# Args: $1=file_path
# Outputs: estimated token count
estimate_context_tokens() {
    local file=$1
    if [ ! -f "$file" ]; then
        echo "0"
        return
    fi
    local words
    words=$(wc -w < "$file" | tr -d '[:space:]')
    # Rough estimate: 1 word ≈ 1.3 tokens for English/markdown
    echo $(( words * 13 / 10 ))
}

# Check if emergency synthesis is needed (context exceeds 80% of limit)
# Args: $1=current_tokens, $2=context_limit
# Returns 0 (true) if emergency synthesis needed
needs_emergency_synthesis() {
    local current=$1
    local limit=$2
    local threshold=$(( limit * 80 / 100 ))

    if [ "$current" -ge "$threshold" ]; then
        return 0
    fi
    return 1
}

# Estimate total context tokens for an agent cycle
# Args: $1=shared_dir, $2=agent_role
# Outputs: estimated total tokens
estimate_agent_context() {
    local shared_dir=$1
    local agent=$2
    local total=0

    # Charter (from repo, but estimate from shared agent history)
    local history_tokens
    history_tokens=$(estimate_context_tokens "$shared_dir/agents/$agent/history.md")
    total=$(( total + history_tokens ))

    # Knowledge files
    for f in experiments.md hypotheses.md decisions.md components.md frontiers.md synthesis.md; do
        local file_tokens
        file_tokens=$(estimate_context_tokens "$shared_dir/knowledge/$f")
        total=$(( total + file_tokens ))
    done

    echo "$total"
}
