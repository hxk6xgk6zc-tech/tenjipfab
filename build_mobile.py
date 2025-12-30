import os
import subprocess
import sys
import glob
import argparse

def run_command(command, cwd=None, ignore_error=False):
    print(f"Executing: {command}")
    result = subprocess.run(command, shell=True, cwd=cwd)
    if result.returncode != 0:
        print(f"Error executing command: {command}")
        if not ignore_error:
            sys.exit(1)
        return False
    return True

def inject_ios_permissions(flutter_root):
    """iOSのInfo.plistに権限を追加"""
    plist_path = os.path.join(flutter_root, "ios", "Runner", "Info.plist")
    if not os.path.exists(plist_path):
        print(f"Warning: {plist_path} not found.")
        return

    print(f"Injecting iOS permissions into {plist_path}...")
    
    # 追加する権限
    # UIRequiresFullScreen: iPad等での全画面表示強制（マルチタスク分割無効化）
    # LSSupportsOpeningDocumentsInPlace / UIFileSharingEnabled: ファイル共有
    permissions = """
    <key>UIRequiresFullScreen</key>
    <true/>
    <key>LSSupportsOpeningDocumentsInPlace</key>
    <true/>
    <key>UIFileSharingEnabled</key>
    <true/>
    <key>UISupportsDocumentBrowser</key>
    <true/>
    """
    
    with open(plist_path, "r") as f:
        content = f.read()

    # 重複追加を防ぐため、キーの存在確認（UIFileSharingEnabledで判定）
    if "<key>UIFileSharingEnabled</key>" not in content:
        # <dict>の直後に追加
        content = content.replace("<dict>", f"<dict>{permissions}")
        with open(plist_path, "w") as f:
            f.write(content)
        print("✅ iOS Permissions injected (inc. UIRequiresFullScreen).")
    else:
        print("ℹ️ iOS Permissions already exist.")

def inject_android_permissions(flutter_root):
    """AndroidのAndroidManifest.xmlに権限を追加"""
    manifest_path = os.path.join(flutter_root, "android", "app", "src", "main", "AndroidManifest.xml")
    if not os.path.exists(manifest_path):
        print(f"Warning: {manifest_path} not found.")
        return

    print(f"Injecting Android permissions into {manifest_path}...")
    
    # 追加する権限（ストレージ読み書き）
    permissions = """
    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE"/>
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"/>
    """
    
    with open(manifest_path, "r") as f:
        content = f.read()

    if "android.permission.WRITE_EXTERNAL_STORAGE" not in content:
        # <application>タグの前に追加
        if "<application" in content:
            content = content.replace("<application", f"{permissions}\n    <application")
            with open(manifest_path, "w") as f:
                f.write(content)
            print("✅ Android Permissions injected.")
    else:
        print("ℹ️ Android Permissions already exist.")

def main():
    # 引数解析の設定
    parser = argparse.ArgumentParser(description="Build Flet app for Mobile")
    parser.add_argument("target", choices=["ios", "android"], help="Build target (ios or android)")
    parser.add_argument("--version", default="1.0.0", help="App version string (e.g. 1.0.0)")
    parser.add_argument("--build-number", default="1", help="Build number integer (e.g. 2)")
    
    args = parser.parse_args()
    
    target = args.target
    version = args.version
    build_number = args.build_number
    
    print(f"🚀 Starting build for {target} [Version: {version}, Build: {build_number}]")

    # 0. 依存ライブラリインストール
    if os.path.exists("requirements.txt"):
        print("Installing dependencies...")
        run_command("pip install -r requirements.txt")

    # 1. クリーンアップ
    if os.path.exists("build"):
        print("Cleaning build directory...")
        run_command("rm -rf build")

    # 2. Fletプロジェクト生成
    # バージョン情報を引数として渡す
    print(f"Generating Flutter project for {target}...")
    
    flet_cmd_base = "flet build apk" if target == "android" else "flet build ipa"
    # バージョンオプションを追加
    flet_cmd = f"{flet_cmd_base} --module-name main --no-web --build-name {version} --build-number {build_number}"
    
    # プロジェクト生成だけが目的なのでignore_error=True (署名エラーなどで止まらないようにする)
    run_command(flet_cmd, ignore_error=True)

    # Flutterプロジェクトルートを特定
    flutter_root = "build/flutter"
    if not os.path.exists(flutter_root):
        found = glob.glob("build/**/pubspec.yaml", recursive=True)
        if found:
            flutter_root = os.path.dirname(found[0])
    
    if not os.path.exists(flutter_root):
        print("Error: Could not find generated Flutter project.")
        sys.exit(1)

    print(f"Flutter project root: {flutter_root}")

    # 3. 権限注入 & ビルド
    if target == "ios":
        inject_ios_permissions(flutter_root)
        print("Building for iOS Simulator...")
        # シミュレーター用ビルド
        run_command("flutter build ios --simulator --debug", cwd=flutter_root)
        
        app_path = os.path.join(flutter_root, "build/ios/iphonesimulator/Runner.app")
        print("\n🎉 iOS Build Complete!")
        print(f"App Bundle: {app_path}")
        print("To run on simulator:")
        print(f"  open -a Simulator")
        print(f"  xcrun simctl install booted \"{app_path}\"")
        print(f"  xcrun simctl launch booted com.yourname.tenjipfab") # Bundle IDは適宜読み替えてください

    elif target == "android":
        inject_android_permissions(flutter_root)
        print("Building for Android Emulator (APK)...")
        # デバッグ用APK
        run_command("flutter build apk --debug", cwd=flutter_root)
        
        apk_path = os.path.join(flutter_root, "build/app/outputs/flutter-apk/app-debug.apk")
        print("\n🎉 Android Build Complete!")
        print(f"APK File: {apk_path}")
        print("To install on emulator:")
        print(f"  adb install \"{apk_path}\"")

if __name__ == "__main__":
    main()