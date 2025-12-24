import flet as ft
import asyncio
import os
from datetime import datetime

# モジュールインポート
from styles import AppColors, TextStyles, ComponentStyles
# braille_logicはjanomeを使用するように変更済み
from braille_logic import BrailleConverter, SPACE_MARK
from stl_generator import STLGenerator

async def main(page: ft.Page):
    # --- 1. アプリ全体の初期設定 ---
    page.title = "Tenji P-Fab"
    page.bgcolor = AppColors.BACKGROUND
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 390
    page.window_height = 844
    page.padding = 0
    
    # Mac対策: アプリ起動時にウィンドウを最前面に持ってくる
    try:
        page.window_to_front()
    except:
        pass

    # ファイル保存用ダイアログの準備 (Overlayに追加)
    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)
    page.update()

    # ロジッククラスの初期化
    converter = BrailleConverter()
    stl_generator = STLGenerator()
    
    # --- 2. 状態管理変数 ---
    current_mapped_data = [] 
    editing_index = -1       
    settings = {
        "max_chars_per_line": 10,
        "max_lines_per_plate": 3,
        "scale": 1.0,
        "pause_for_color": False
    }
    
    # UI参照用のRef
    txt_input_ref = ft.Ref[ft.TextField]()
    edit_field_ref = ft.Ref[ft.TextField]()
    chars_slider_ref = ft.Ref[ft.Slider]()
    lines_slider_ref = ft.Ref[ft.Slider]()

    # かな変換ライブラリの動作チェック
    # braille_logic側でJanomeの初期化に失敗した場合のフラグチェック
    if not converter.use_kakasi:
        error_detail = getattr(converter, 'error_msg', 'Unknown Error')
        page.snack_bar = ft.SnackBar(
            content=ft.Text(f"⚠️ かな変換機能が無効です ({error_detail})\nひらがなで入力してください"),
            bgcolor=AppColors.ERROR,
            duration=5000,
            action="OK"
        )
        page.snack_bar.open = True
        page.update()

    def _make_dot(is_active):
        """点字のドット1つを生成する"""
        return ft.Container(
            width=8, height=8,
            bgcolor=AppColors.DOT_ACTIVE if is_active else AppColors.DOT_INACTIVE,
            border_radius=4,
        )

    # 点字プレビューを表示するエリア (スクロール可能)
    braille_display_area = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        spacing=10, 
    )

    # --- 4. イベントハンドラ ---

    def open_edit_dialog(index):
        """読み修正ダイアログを開く"""
        nonlocal editing_index
        editing_index = index
        item = current_mapped_data[index]
        edit_dialog.title = ft.Text(f"「{item['orig']}」の読みを修正")
        if edit_field_ref.current:
            edit_field_ref.current.value = item['reading']
        page.open(edit_dialog)

    def render_braille_preview():
        """現在のデータをもとに点字プレビューを再描画する"""
        braille_display_area.controls.clear()
        
        # 表示用にデータをフラットなリストに変換（スペース挿入）
        flat_cells_all = []
        for word_idx, item in enumerate(current_mapped_data):
            for cell in item['cells']:
                flat_cells_all.append({
                    'dots': cell['dots'],
                    'char': cell['char'],
                    'word_idx': word_idx, 
                    'orig': item['orig']
                })
            # 単語区切りのスペース (最後以外)
            if word_idx < len(current_mapped_data) - 1:
                flat_cells_all.append({
                    'dots': SPACE_MARK,
                    'char': ' ',
                    'word_idx': -1,
                    'orig': '(Space)'
                })
        
        # 設定された文字数で分割（プレート分け）
        chunk_size = settings["max_chars_per_line"]
        if chunk_size <= 0: chunk_size = 10

        # 行ごとのリストを作成
        lines_list = [flat_cells_all[i:i + chunk_size] for i in range(0, len(flat_cells_all), chunk_size)]
        
        # プレートごとのリストを作成
        lines_per_plate = settings["max_lines_per_plate"]
        if lines_per_plate <= 0: lines_per_plate = 1
        plates = [lines_list[i:i + lines_per_plate] for i in range(0, len(lines_list), lines_per_plate)]

        for i, plate_lines in enumerate(plates):
            plate_num = i + 1
            header_text = ft.Text(f"Plate #{plate_num}", style=TextStyles.PLATE_LABEL)
            
            plate_content_controls = []
            
            for line_cells in plate_lines:
                row_controls = []
                for cell_info in line_cells:
                    cell_dots = cell_info['dots']
                    char_str = cell_info['char']
                    word_idx = cell_info['word_idx']
                    
                    # 点字の列 (左・右)
                    col1 = ft.Column(spacing=2, controls=[
                        _make_dot(cell_dots[0]), _make_dot(cell_dots[1]), _make_dot(cell_dots[2])
                    ])
                    col2 = ft.Column(spacing=2, controls=[
                        _make_dot(cell_dots[3]), _make_dot(cell_dots[4]), _make_dot(cell_dots[5])
                    ])
                    
                    # 1文字分のUI
                    cell_ui = ft.Container(
                        content=ft.Column([
                            ft.Container(
                                content=ft.Row([col1, col2], spacing=2),
                                padding=4,
                                bgcolor=AppColors.SURFACE,
                                border_radius=4,
                                shadow=ft.BoxShadow(blur_radius=1, color=ft.Colors.with_opacity(0.1, "#000000")),
                            ),
                            ft.Text(char_str, style=TextStyles.READING, text_align=ft.TextAlign.CENTER, width=20)
                        ], spacing=2, alignment=ft.MainAxisAlignment.CENTER),
                        
                        # クリックで編集 (スペース以外)
                        on_click=lambda e, idx=word_idx: open_edit_dialog(idx) if idx != -1 else None,
                        tooltip=f"元の単語: {cell_info['orig']}" if word_idx != -1 else None
                    )
                    row_controls.append(cell_ui)
                
                # 行コンテナ
                plate_content_controls.append(
                    ft.Row(row_controls, spacing=8, alignment=ft.MainAxisAlignment.START, scroll=ft.ScrollMode.ALWAYS)
                )

            # プレート全体をまとめるコンテナ
            plate_ui = ft.Column([
                header_text,
                ft.Container(
                    content=ft.Column(plate_content_controls, spacing=10),
                    padding=10, 
                    bgcolor=ft.Colors.WHITE54, 
                    border_radius=8,
                    border=ft.border.all(1, ft.Colors.BLACK12)
                ),
                ft.Divider(height=10, color=ft.Colors.TRANSPARENT)
            ], spacing=2)
            
            braille_display_area.controls.append(plate_ui)
            
        # ページ全体を更新して反映
        page.update()

    def update_braille_from_input(text):
        """テキスト入力時に点字変換を実行"""
        nonlocal current_mapped_data
        current_mapped_data = converter.convert_with_mapping(text)
        render_braille_preview()

    def save_reading_edit(e):
        """読み修正の保存"""
        nonlocal current_mapped_data
        if editing_index < 0: return
        new_reading = edit_field_ref.current.value
        if new_reading:
            current_mapped_data[editing_index]['reading'] = new_reading
            # 再変換
            new_cells = converter.kana_to_cells(new_reading)
            current_mapped_data[editing_index]['cells'] = new_cells
            # 互換性のためdotsも更新
            current_mapped_data[editing_index]['braille'] = [c['dots'] for c in new_cells]
            
            render_braille_preview()
            page.open(ft.SnackBar(content=ft.Text(f"読みを修正しました")))
        page.close(edit_dialog)

    # 編集ダイアログ定義
    edit_dialog = ft.AlertDialog(
        title=ft.Text("読みの修正"),
        content=ft.TextField(ref=edit_field_ref, autofocus=True, label="読み（ひらがな）"),
        actions=[
            ft.TextButton("キャンセル", on_click=lambda e: page.close(edit_dialog)),
            ft.TextButton("保存", on_click=save_reading_edit),
        ],
    )

    def on_chars_slider_change(e):
        settings["max_chars_per_line"] = int(e.control.value)
        e.control.label = f"{int(e.control.value)}文字"
        e.control.update()
        if current_mapped_data:
            render_braille_preview()

    def on_lines_slider_change(e):
        settings["max_lines_per_plate"] = int(e.control.value)
        e.control.label = f"{int(e.control.value)}行"
        e.control.update()
        if current_mapped_data:
            render_braille_preview()

    def show_settings(e):
        """設定ダイアログを表示"""
        dlg = ft.AlertDialog(
            title=ft.Text("出力設定"),
            content=ft.Column([
                ft.Text("1行あたりの文字数", size=14),
                ft.Slider(
                    ref=chars_slider_ref,
                    min=5, max=30, divisions=25, 
                    value=settings["max_chars_per_line"], 
                    label=f"{settings['max_chars_per_line']}文字",
                    on_change=on_chars_slider_change
                ),
                ft.Text("1プレートあたりの行数", size=14),
                ft.Slider(
                    ref=lines_slider_ref,
                    min=1, max=10, divisions=9, 
                    value=settings["max_lines_per_plate"], 
                    label=f"{settings['max_lines_per_plate']}行",
                    on_change=on_lines_slider_change
                ),
                ft.Text("ドットサイズ (Scale)", size=14),
                ft.Slider(min=0.8, max=1.5, divisions=7, label="{value}x", value=settings["scale"]),
                ft.Checkbox(label="色変え停止 (Layer Pause)", value=settings["pause_for_color"]),
            ], height=300, tight=True),
            actions=[ft.TextButton("閉じる", on_click=lambda e: page.close(dlg))],
        )
        page.open(dlg)

    # --- 保存関連処理 ---

    def get_structured_data_for_export():
        """エクスポート用に禁則処理済みの構造化データ(plates > lines > cells)を生成"""
        # 1. フラット化
        flat_cells_all = []
        for word_idx, item in enumerate(current_mapped_data):
            for cell in item['cells']:
                flat_cells_all.append(cell) # cellは辞書
            if word_idx < len(current_mapped_data) - 1:
                flat_cells_all.append({'dots': SPACE_MARK, 'char': ' '})
        
        # 行分割ロジックはmain内に関数定義していないため、簡易的に文字数分割を行う
        # (厳密な禁則処理付き分割関数が必要なら、braille_logic.pyに移譲するかここで再定義する)
        
        chars_per_line = settings["max_chars_per_line"]
        lines_per_plate = settings["max_lines_per_plate"]
        
        # 行分割
        lines = [flat_cells_all[i:i + chars_per_line] for i in range(0, len(flat_cells_all), chars_per_line)]
        
        # プレート分割
        plates = [lines[i:i + lines_per_plate] for i in range(0, len(lines), lines_per_plate)]
        
        return plates

    def handle_save_dialog_click(e):
        """保存ダイアログを開く"""
        if not current_mapped_data:
            page.open(ft.SnackBar(content=ft.Text("データがありません。")))
            return
        
        file_picker.save_file(dialog_title="名前を付けて保存")

    def on_file_picked(e: ft.FilePickerResultEvent):
        """ダイアログでファイルが選択された時の処理"""
        if e.path:
            try:
                plates_data = get_structured_data_for_export()
                original_txt = txt_input_ref.current.value if txt_input_ref.current else ""
                
                stl_generator.generate_package_from_plates(
                    plates_data, e.path, original_text_str=original_txt
                )
                page.open(ft.SnackBar(content=ft.Text(f"保存しました: {os.path.basename(e.path)}")))
            except Exception as ex:
                page.open(ft.SnackBar(content=ft.Text(f"エラー: {str(ex)}"), bgcolor=AppColors.ERROR))

    file_picker.on_result = on_file_picked

    def handle_quick_save_click(e):
        """ダウンロードフォルダへ直接保存 (Sandbox対策)"""
        if not current_mapped_data:
            page.open(ft.SnackBar(content=ft.Text("データがありません。")))
            return
        
        try:
            home_dir = os.path.expanduser("~")
            download_dir = os.path.join(home_dir, "Downloads")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tenji_export_{timestamp}.zip"
            save_path = os.path.join(download_dir, filename)
            
            plates_data = get_structured_data_for_export()
            original_txt = txt_input_ref.current.value if txt_input_ref.current else ""
            
            stl_generator.generate_package_from_plates(
                plates_data, save_path, original_text_str=original_txt
            )
            
            page.open(ft.SnackBar(
                content=ft.Text(f"ダウンロードフォルダに保存しました:\n{filename}"),
                action="OK",
                duration=5000
            ))
        except Exception as ex:
            page.open(ft.SnackBar(content=ft.Text(f"保存失敗: {str(ex)}"), bgcolor=AppColors.ERROR))

    # --- 5. UI構築 ---
    
    txt_input = ft.TextField(
        ref=txt_input_ref,
        multiline=True, min_lines=3, max_lines=5,
        hint_text="ここに日本語を入力...",
        border=ft.InputBorder.NONE,
        text_style=TextStyles.BODY,
        on_change=lambda e: update_braille_from_input(e.control.value)
    )

    drawer = ft.NavigationDrawer(
        controls=[
            ft.Container(height=12),
            ft.NavigationDrawerDestination(label="履歴", icon="history"),
            ft.NavigationDrawerDestination(label="設定", icon="settings"),
        ],
    )

    header = ft.Container(
        content=ft.Row([
            ft.IconButton(icon="menu", icon_color=AppColors.PRIMARY, on_click=lambda e: page.open(drawer)),
            ft.Text("Tenji P-Fab", style=TextStyles.HEADER),
            ft.Row([
                ft.IconButton(icon="save_alt", icon_color=AppColors.PRIMARY, tooltip="保存", on_click=handle_save_dialog_click),
                ft.IconButton(icon="settings", icon_color=AppColors.PRIMARY, on_click=show_settings)
            ])
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=ft.padding.only(top=50, left=10, right=10, bottom=10),
        bgcolor=AppColors.BACKGROUND
    )

    body_content = ft.Column([
        # 上部: プレビューエリア
        ft.Container(
            content=ft.Column([
                ft.Text("Braille Preview (Tap to edit)", style=TextStyles.CAPTION),
                ft.Container(
                    content=braille_display_area,
                    expand=True,
                    padding=10, 
                    alignment=ft.alignment.top_left,
                )
            ]),
            expand=True, 
            bgcolor=AppColors.BACKGROUND,
        ),
        # 下部: 入力エリア & ボタン
        ft.Container(
            content=ft.Column([
                ft.Text("Input Text", style=TextStyles.CAPTION),
                ft.Container(
                    content=ft.Column([
                        txt_input,
                        ft.Divider(color=AppColors.BACKGROUND),
                        ft.Row([
                            ft.IconButton(icon="mic", icon_color=AppColors.PRIMARY),
                            ft.Container(width=10),
                            # 保存ボタン (Dialog)
                            ft.ElevatedButton(
                                "保存 (Dialog)", 
                                icon="save",
                                style=ComponentStyles.MAIN_BUTTON_STYLE,
                                on_click=handle_save_dialog_click,
                                expand=True
                            ),
                            ft.Container(width=10),
                            # 保存ボタン (Quick Save)
                            ft.ElevatedButton(
                                "Quick Save", 
                                icon="download",
                                style=ComponentStyles.SUB_BUTTON_STYLE,
                                on_click=handle_quick_save_click,
                                tooltip="ダウンロードフォルダに直接保存",
                                expand=True
                            )
                        ])
                    ]),
                    bgcolor=AppColors.SURFACE,
                    border_radius=12,
                    shadow=ComponentStyles.CARD_SHADOW,
                    padding=20,
                )
            ]),
            expand=True, padding=20,
            border_radius=ft.border_radius.only(top_left=30, top_right=30),
            bgcolor=AppColors.SURFACE,
        )
    ], spacing=0, expand=True)

    # ビューの構築
    main_view = ft.View("/", controls=[header, body_content], bgcolor=AppColors.BACKGROUND, padding=0, drawer=drawer)
    
    # スプラッシュ画面
    splash_content = ft.Container(
        content=ft.Column(
            [ft.Icon(name="grid_on_rounded", size=80, color=AppColors.SURFACE),
             ft.Text("Tenji P-Fab", style=ft.TextStyle(size=30, weight=ft.FontWeight.BOLD, color=AppColors.SURFACE))],
            alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER
        ),
        bgcolor=AppColors.PRIMARY, alignment=ft.alignment.center, expand=True
    )

    page.add(splash_content)
    await asyncio.sleep(2)
    page.views.clear()
    page.views.append(main_view)
    page.update()

if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
