import os
import subprocess
import sys

def run_command(command, cwd=None):
    """コマンドを実行し、エラーがあれば停止する"""
    print(f"Executing: {command}")
    result = subprocess.run(command, shell=True, cwd=cwd)
    if result.returncode != 0:
        print(f"Error executing command: {command}")
        sys.exit(1)

def main():
    print("🚀 Starting macOS Build Process...")

    # デバッグ: カレントディレクトリ情報の表示
    print(f"Current Directory: {os.getcwd()}")
    if not os.path.exists("main.py"):
        print("❌ Error: main.py not found in current directory.")
        sys.exit(1)

    # 0. 依存ライブラリの確認とインストール
    if os.path.exists("requirements.txt"):
        print("Installing dependencies from requirements.txt...")
        run_command("pip install -r requirements.txt")

    # 1. クリーンアップ
    if os.path.exists("build"):
        print("Cleaning build directory...")
        run_command("rm -rf build")

    # 2. Fletによるベースプロジェクトの生成
    # 修正: --project . を指定してカレントディレクトリをルートとする
    print("Generating Flutter project...")
    run_command("flet build macos --project . --no-android --no-ios")

    # 3. Entitlements（権限ファイル）の検索と修正
    print("Injecting permissions...")
    
    # パスが変わる可能性があるため検索する
    entitlements_path = None
    import glob
    # 再帰的に検索
    found = glob.glob("build/**/Release.entitlements", recursive=True)
    if found:
        entitlements_path = found[0]
        print(f"Found entitlements at: {entitlements_path}")
    else:
        print("Error: Entitlements file not found.")
        sys.exit(1)

    print(f"Editing: {entitlements_path}")
    
    # 権限を追加するXML断片
    permissions = """
    <key>com.apple.security.files.user-selected.read-write</key>
    <true/>
    <key>com.apple.security.files.downloads.read-write</key>
    <true/>
    <key>com.apple.security.network.client</key>
    <true/>
    """

    with open(entitlements_path, "r") as f:
        content = f.read()

    # </dict>の直前に権限を挿入
    if "<key>com.apple.security.files.user-selected.read-write</key>" not in content:
        content = content.replace("</dict>", f"{permissions}\n</dict>")
        with open(entitlements_path, "w") as f:
            f.write(content)
        print("✅ Permissions injected.")
    else:
        print("ℹ️ Permissions already exist.")

    # 4. Flutterによる再ビルド（変更を反映）
    # Entitlementsファイルがあるディレクトリの親の親... (Flutterプロジェクトルート) を探す
    path_parts = entitlements_path.split(os.sep)
    try:
        # build/flutter/macos/Runner/... -> build/flutter がルート
        macos_index = path_parts.index('macos')
        flutter_root = os.sep.join(path_parts[:macos_index])
    except ValueError:
        print("Could not determine Flutter root. Trying 'build/flutter'...")
        flutter_root = "build/flutter" # 最近のバージョンのデフォルト

    print(f"Rebuilding with Flutter in {flutter_root}...")
    
    if not os.path.exists(flutter_root):
        print(f"Error: Flutter root '{flutter_root}' does not exist.")
        sys.exit(1)

    run_command("flutter build macos --release", cwd=flutter_root)

    print("\n🎉 Build Complete!")
    print(f"Check the output in: {flutter_root}/build/macos/Build/Products/Release/")

if __name__ == "__main__":
    main()