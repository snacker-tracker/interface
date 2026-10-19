#!/usr/bin/env bash
# Download dataset(s) from the Hugging Face Hub using curl + jq (no Python required).
set -euo pipefail

usage() {
    cat >&2 <<EOF
Usage: $0 <url|repo_id|username> [-o output_dir] [-r revision] [-t token]

  <target>          Dataset URL (https://huggingface.co/datasets/ns/name),
                     repo id ("namespace/name"), or bare username/org
                     (downloads every dataset that user/org owns).
  -o, --output-dir  Directory to download into (default: ./datasets)
  -r, --revision    Branch/tag/commit to download (default: main)
  -t, --token       Hugging Face access token, for private/gated datasets
                     (falls back to \$HF_TOKEN)
EOF
    exit 1
}

command -v curl >/dev/null || { echo "curl is required." >&2; exit 1; }
command -v jq   >/dev/null || { echo "jq is required (sudo apt install jq)." >&2; exit 1; }

output_dir="datasets"
revision="main"
token="${HF_TOKEN:-}"
target=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -o|--output-dir) output_dir="$2"; shift 2 ;;
        -r|--revision)   revision="$2"; shift 2 ;;
        -t|--token)      token="$2"; shift 2 ;;
        -h|--help)       usage ;;
        -*)              echo "Unknown option: $1" >&2; usage ;;
        *)               target="$1"; shift ;;
    esac
done

[[ -z "$target" ]] && usage

# Normalize target down to a "namespace/name" repo id or a bare username.
if [[ "$target" =~ ^https?:// ]]; then
    repo_id=$(sed -E 's#^https?://huggingface\.co/##; s#^datasets/##; s#^([^/?#]+(/[^/?#]+)?).*#\1#' <<< "$target")
else
    repo_id="${target%/}"
fi

auth_args=()
[[ -n "$token" ]] && auth_args=(-H "Authorization: Bearer ${token}")

download_repo() {
    local repo="$1"
    local dest="${output_dir}/${repo//\//__}"
    echo "Downloading dataset '${repo}' -> ${dest}"

    local info_url="https://huggingface.co/api/datasets/${repo}"
    [[ "$revision" != "main" ]] && info_url="${info_url}/revision/${revision}"

    local json
    json=$(curl -sSL "${auth_args[@]}" "$info_url")

    if jq -e 'has("error")' <<< "$json" >/dev/null 2>&1; then
        echo "  ! Skipped '${repo}': $(jq -r '.error' <<< "$json")" >&2
        return
    fi

    mkdir -p "$dest"
    jq -r '.siblings[].rfilename' <<< "$json" | while IFS= read -r file; do
        [[ -z "$file" ]] && continue
        echo "  - ${file}"
        if ! curl -sSL -f --create-dirs "${auth_args[@]}" \
                -o "${dest}/${file}" \
                "https://huggingface.co/datasets/${repo}/resolve/${revision}/${file}"; then
            echo "    ! failed to download ${file}" >&2
        fi
    done
}

if [[ "$repo_id" == *"/"* ]]; then
    download_repo "$repo_id"
else
    echo "Looking up datasets owned by '${repo_id}'..."
    list_json=$(curl -sSL "${auth_args[@]}" "https://huggingface.co/api/datasets?author=${repo_id}")
    ids=$(jq -r '.[].id' <<< "$list_json")

    if [[ -z "$ids" ]]; then
        echo "No datasets found for user/org '${repo_id}'."
        exit 0
    fi

    echo "Found dataset(s) for '${repo_id}':"
    while IFS= read -r id; do echo "  - $id"; done <<< "$ids"

    while IFS= read -r id; do
        download_repo "$id"
    done <<< "$ids"
fi

echo "Done."
