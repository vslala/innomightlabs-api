#!/usr/bin/env python3
import subprocess
import sys
import os


def die(msg, code=1):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {os.path.basename(sys.argv[0])} <target-branch>", file=sys.stderr)
        sys.exit(1)

    target_branch = sys.argv[1]

    # Find the repo root
    try:
        repo_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL).decode().strip()
    except subprocess.CalledProcessError:
        die("Not inside a Git repository.")

    diff_file = os.path.join(repo_root, "git_diff.dat")
    head_file = os.path.join(repo_root, "git_show_head.dat")

    # Run git diff
    with open(diff_file, "wb") as df:
        proc = subprocess.run(["git", "diff", target_branch], stdout=df, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            # remove incomplete file
            df.close()
            os.remove(diff_file)
            stderr = proc.stderr.decode().strip()
            die(f"'git diff {target_branch}' failed:\n{stderr}")

    # Run git show HEAD
    with open(head_file, "wb") as hf:
        proc = subprocess.run(["git", "show", "HEAD"], stdout=hf, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            hf.close()
            os.remove(head_file)
            stderr = proc.stderr.decode().strip()
            die(f"'git show HEAD' failed:\n{stderr}")

    print("Snapshots written to:")
    print(f"  • {diff_file}")
    print(f"  • {head_file}")


if __name__ == "__main__":
    main()
