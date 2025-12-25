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

    # 0. 依存ライブラリの確認とインストール
    if os.path.exists("requirements.txt"):
        print("Installing dependencies from requirements.txt...")
        run_command("pip install -r requirements.txt")

    # 1. クリーンアップ
    if os.path.exists("build"):
        print("Cleaning build directory...")
        run_command("rm -rf build")

    # 2. Fletによるベースプロジェクトの生成
    # main.pyを明示的に指定して、Not Foundエラーを回避します
    print("Generating Flutter project...")
    run_command("flet build macos --project main.py --no-android --no-ios")

    # 3. Entitlements（権限ファイル）の検索と修正
    print("Injecting permissions...")
    entitlements_path = "build/macos/Runner/Release.entitlements"
    
    # パスが変わる可能性があるため検索する
    if not os.path.exists(entitlements_path):
        # findコマンドで探す (build/flutter/macos... の場合などに対応)
        import glob
        found = glob.glob("build/**/Release.entitlements", recursive=True)
        if found:
            entitlements_path = found[0]
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
    flutter_root = os.path.dirname(os.path.dirname(os.path.dirname(entitlements_path)))
    
    print(f"Rebuilding with Flutter in {flutter_root}...")
    run_command("flutter build macos --release", cwd=flutter_root)

    print("\n🎉 Build Complete!")
    print(f"App location: {flutter_root}/build/macos/Build/Products/Release/Tenji P-Fab.app")

if __name__ == "__main__":
    main()