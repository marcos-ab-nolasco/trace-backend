#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parent.parent
KEEP_NAMES = {".git", ".gitmodules"}
VARIANT_BRANCHES: dict[str, str] = {
    "backend": "variant/backend",
    "frontend": "variant/frontend",
}


def run_git(args: Iterable[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Executa comando git na raiz do projeto."""
    return subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        check=check,
        text=True,
        capture_output=False,
    )


def ensure_repo_root() -> None:
    if not (ROOT_DIR / ".git").exists():
        print("Erro: execute o script a partir da raiz do repositório.", file=sys.stderr)
        sys.exit(1)


def working_tree_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    return not result.stdout.strip()


def branch_exists(branch: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", branch],
        cwd=ROOT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def fetch_branch(branch: str) -> None:
    print(f"🔄 Buscando branch '{branch}'...")
    run_git(["fetch", "origin", branch])


def checkout_variant(branch: str) -> Path:
    tmpdir = Path(tempfile.mkdtemp(prefix="variant-"))
    try:
        print(f"📦 Criando worktree temporária para '{branch}' em {tmpdir}...")
        run_git(["worktree", "add", "--force", "--detach", str(tmpdir), branch])
    except Exception:
        if tmpdir.exists():
            shutil.rmtree(tmpdir, ignore_errors=True)
        raise
    return tmpdir


def clean_root() -> None:
    print("🧹 Removendo arquivos atuais (exceto .git)...")
    for item in ROOT_DIR.iterdir():
        if item.name in KEEP_NAMES:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def copy_variant(src_root: Path) -> None:
    print("📁 Copiando arquivos da variante...")
    for item in src_root.iterdir():
        if item.name in KEEP_NAMES:
            continue
        dest = ROOT_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dest, symlinks=True)
        else:
            shutil.copy2(item, dest)


def remove_worktree(path: Path) -> None:
    print("🧹 Removendo worktree temporária...")
    run_git(["worktree", "remove", "--force", str(path)])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aplicar conteúdo de uma branch variante do template.")
    variant_help = ", ".join(f"{k} -> {v}" for k, v in VARIANT_BRANCHES.items())
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--variant", choices=VARIANT_BRANCHES.keys(), help=f"Atalho conhecido ({variant_help}).")
    group.add_argument("--branch", help="Branch explícita a ser aplicada.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignora alterações pendentes (pode sobrescrever trabalho local).",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    ensure_repo_root()
    args = parse_args(argv)

    if not args.force and not working_tree_clean():
        print("Erro: working tree contém alterações locais. Use --force para sobrescrever.", file=sys.stderr)
        return 1

    branch = args.branch or VARIANT_BRANCHES[args.variant]
    checkout_ref = branch
    if not branch_exists(branch):
        fetch_branch(branch)
        if not branch_exists(branch):
            remote_ref = f"origin/{branch}"
            if branch_exists(remote_ref):
                # Usa referência remota quando não há branch local após o fetch.
                checkout_ref = remote_ref
            else:
                print(f"Erro: branch '{branch}' não encontrada após git fetch.", file=sys.stderr)
                return 1

    tmpdir = None
    try:
        tmpdir = checkout_variant(checkout_ref)
        clean_root()
        copy_variant(tmpdir)
        print("\n✅ Variante aplicada com sucesso!")
        print("📌 Lembre-se de revisar o diff e criar um commit com as alterações.")
    finally:
        if tmpdir:
            try:
                remove_worktree(tmpdir)
            except Exception as exc:  # pragma: no cover - limpeza best effort
                print(f"Aviso: falha ao remover worktree temporária ({exc}). Remova manualmente se necessário.")
                shutil.rmtree(tmpdir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
