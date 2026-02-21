# Bash Style Guide

- Make sure that new shell scripts (`.sh` files) have executable permissions (run `chmod +x <script>.sh`)
- Run `find . -name '*.sh' -not -path './node_modules/*' -print0 | xargs -0 shellcheck` to check for issues
