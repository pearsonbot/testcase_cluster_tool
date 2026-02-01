"""Build script for PyInstaller packaging."""
import os
import sys
import subprocess


def main():
    # Ensure we're in the project root
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    print("=" * 60)
    print("Building testcase_cluster_tool with PyInstaller")
    print("=" * 60)

    # Download model if not present
    model_path = os.path.join(project_root, "models", "text2vec-base-chinese")
    if not os.path.isdir(model_path):
        print("\nDownloading text2vec-base-chinese model...")
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("shibing624/text2vec-base-chinese")
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        model.save(model_path)
        print(f"Model saved to {model_path}")
    else:
        print(f"\nModel already exists at {model_path}")

    # Build with PyInstaller
    print("\nRunning PyInstaller...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "testcase_cluster_tool",
        "--noconfirm",
        "--onedir",
        "--console",
        "--add-data", f"app/templates{os.pathsep}app/templates",
        "--add-data", f"static{os.pathsep}static",
        "--hidden-import", "sentence_transformers",
        "--hidden-import", "sklearn",
        "--hidden-import", "sklearn.utils._cython_blas",
        "--hidden-import", "sklearn.neighbors._typedefs",
        "--hidden-import", "sklearn.neighbors._quad_tree",
        "--hidden-import", "sklearn.tree._utils",
        "--hidden-import", "sklearn.metrics._pairwise_distances_reduction._datasets_pair",
        "--hidden-import", "sklearn.metrics._pairwise_distances_reduction._middle_term_computer",
        "--collect-submodules", "sentence_transformers",
        "--collect-data", "sentence_transformers",
        "--collect-submodules", "torch",
        "--collect-submodules", "transformers",
        "--collect-data", "transformers",
        "--collect-submodules", "tokenizers",
        "--collect-data", "tqdm",
        "run.py",
    ]
    subprocess.check_call(cmd)

    # Post-build: copy model and create directories
    dist_dir = os.path.join(project_root, "dist", "testcase_cluster_tool")
    dest_model = os.path.join(dist_dir, "models", "text2vec-base-chinese")

    if not os.path.isdir(dest_model):
        print(f"\nCopying model to {dest_model}...")
        import shutil
        shutil.copytree(model_path, dest_model)

    os.makedirs(os.path.join(dist_dir, "data"), exist_ok=True)
    os.makedirs(os.path.join(dist_dir, "log"), exist_ok=True)

    # Copy sample file
    sample_src = os.path.join(project_root, "tests", "sample_testcases.xlsx")
    if os.path.exists(sample_src):
        import shutil
        shutil.copy2(sample_src, os.path.join(dist_dir, "sample_testcases.xlsx"))

    print("\n" + "=" * 60)
    print(f"Build complete! Output: {dist_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
