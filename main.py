import flet as ft
import asyncio
import os
from datetime import datetime

# モジュールインポート
from styles import AppColors, TextStyles, ComponentStyles
# 特殊符を確実にインポート
from braille_logic import (
    BrailleConverter, SPACE_MARK,
    DAKUTEN_MARK, HANDAKUTEN_MARK, YOON_MARK, 
    YOON_DAKU_MARK, YOON_HANDAKU_MARK, NUM_INDICATOR, FOREIGN_INDICATOR
)
from stl_generator import STLGenerator
from history_manager import HistoryManager

async def main(page: ft.Page):
    # --- 1. アプリ全体の初期設定 ---
    page.title = "Tenji P-Fab"
    page.bgcolor = AppColors.BACKGROUND
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 390
    page.window_height = 844
    page.padding = 0
    
    try:
        page.window_to_front()
    except:
        pass

    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)
    page.update()

    converter = BrailleConverter()
    stl_generator = STLGenerator()
    history_manager = HistoryManager(page)
    
    current_mapped_data = [] 
    editing_index = -1       
    
    # 設定の初期化 (デフォルト値)
    settings = {
        "max_chars_per_line": 10,
        "max_lines_per_plate": 3,
        "plate_thickness": 1.0, 
        "scale": 1.0,
        "pause_for_color": False,
        "use_quick_save": False
    }

    # プラットフォーム判定 (モバイルならQuick Saveをデフォルト推奨だが、保存値があればそちらを優先するため後で判定)
    is_mobile = page.platform in [ft.PagePlatform.IOS, ft.PagePlatform.ANDROID]

    # --- 設定の読み込みと復元 ---
    saved_config = history_manager.load_settings()
    if saved_config:
        # 設定キーが存在すれば上書き
        for key in settings.keys():
            if key in saved_config:
                settings[key] = saved_config[key]
    else:
        # 初回起動時かつモバイルの場合のみデフォルトをQuickSaveにする
        if is_mobile:
            settings["use_quick_save"] = True
    
    txt_input_ref = ft.Ref[ft.TextField]()
    edit_field_ref = ft.Ref[ft.TextField]()
    chars_slider_ref = ft.Ref[ft.Slider]()
    lines_slider_ref = ft.Ref[ft.Slider]()
    thickness_slider_ref = ft.Ref[ft.Slider]() 
    
    # 履歴設定用
    history_limit_slider_ref = ft.Ref[ft.Slider]()

    if not converter.use_kakasi:
        page.snack_bar = ft.SnackBar(
            content=ft.Text(f"⚠️ かな変換機能が無効です (Pykakasi未検出)\nひらがなで入力してください"),
            bgcolor=AppColors.ERROR,
            duration=5000,
            action="OK"
        )
        page.snack_bar.open = True
        page.update()

    def _make_dot(is_active):
        return ft.Container(
            width=8, height=8,
            bgcolor=AppColors.DOT_ACTIVE if is_active else AppColors.DOT_INACTIVE,
            border_radius=4,
        )

    braille_display_area = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        spacing=10, 
    )

    # --- 禁則処理付き行分割ロジック ---
    def split_cells_with_rules(all_cells, max_chars):
        lines = []
        current_line = []
        units = []
        i = 0
        prefix_marks_vals = {
            tuple(DAKUTEN_MARK), tuple(HANDAKUTEN_MARK), tuple(YOON_MARK),
            tuple(YOON_DAKU_MARK), tuple(YOON_HANDAKU_MARK), tuple(NUM_INDICATOR), tuple(FOREIGN_INDICATOR)
        }
        
        while i < len(all_cells):
            cell = all_cells[i]
            cell_dots_tuple = tuple(cell['dots'])
            is_prefix = (cell_dots_tuple in prefix_marks_vals)
            
            if is_prefix and i + 1 < len(all_cells):
                units.append([cell, all_cells[i+1]])
                i += 2
            else:
                units.append([cell])
                i += 1
                
        for unit in units:
            unit_len = len(unit)
            if len(current_line) + unit_len > max_chars:
                if len(current_line) > 0:
                    lines.append(current_line)
                    current_line = []
            current_line.extend(unit)
            
        if current_line:
            lines.append(current_line)
            
        return lines

    def open_edit_dialog(index):
        nonlocal editing_index
        editing_index = index
        item = current_mapped_data[index]
        edit_dialog.title = ft.Text(f"「{item['orig']}」の読みを修正")
        if edit_field_ref.current:
            edit_field_ref.current.value = item['reading']
        page.open(edit_dialog)

    def render_braille_preview():
        braille_display_area.controls.clear()
        
        flat_cells_all = []
        for word_idx, item in enumerate(current_mapped_data):
            for cell in item['cells']:
                flat_cells_all.append({
                    'dots': cell['dots'],
                    'char': cell['char'],
                    'word_idx': word_idx, 
                    'orig': item['orig']
                })
            if word_idx < len(current_mapped_data) - 1:
                flat_cells_all.append({
                    'dots': SPACE_MARK,
                    'char': ' ',
                    'word_idx': -1,
                    'orig': '(Space)'
                })
        
        chars_per_line = settings["max_chars_per_line"]
        lines_per_plate = settings["max_lines_per_plate"]
        
        if chars_per_line <= 0: chars_per_line = 10
        if lines_per_plate <= 0: lines_per_plate = 1

        lines = split_cells_with_rules(flat_cells_all, chars_per_line)
        plates = [lines[i:i + lines_per_plate] for i in range(0, len(lines), lines_per_plate)]

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
                    
                    col1 = ft.Column(spacing=2, controls=[
                        _make_dot(cell_dots[0]), _make_dot(cell_dots[1]), _make_dot(cell_dots[2])
                    ])
                    col2 = ft.Column(spacing=2, controls=[
                        _make_dot(cell_dots[3]), _make_dot(cell_dots[4]), _make_dot(cell_dots[5])
                    ])
                    
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
                        
                        on_click=lambda e, idx=word_idx: open_edit_dialog(idx) if idx != -1 else None,
                        tooltip=f"元の単語: {cell_info['orig']}" if word_idx != -1 else None
                    )
                    row_controls.append(cell_ui)
                
                plate_content_controls.append(
                    ft.Row(row_controls, spacing=8, alignment=ft.MainAxisAlignment.START, scroll=ft.ScrollMode.ALWAYS)
                )

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
            
        page.update()

    def update_braille_from_input(text):
        nonlocal current_mapped_data
        current_mapped_data = converter.convert_with_mapping(text)
        render_braille_preview()

    def save_reading_edit(e):
        nonlocal current_mapped_data
        if editing_index < 0: return
        new_reading = edit_field_ref.current.value
        if new_reading:
            current_mapped_data[editing_index]['reading'] = new_reading
            new_cells = converter.kana_to_cells(new_reading)
            current_mapped_data[editing_index]['cells'] = new_cells
            current_mapped_data[editing_index]['braille'] = [c['dots'] for c in new_cells]
            render_braille_preview()
            page.open(ft.SnackBar(content=ft.Text(f"読みを修正しました")))
        page.close(edit_dialog)

    edit_dialog = ft.AlertDialog(
        title=ft.Text("読みの修正"),
        content=ft.TextField(ref=edit_field_ref, autofocus=True, label="読み（ひらがな）"),
        actions=[
            ft.TextButton("キャンセル", on_click=lambda e: page.close(edit_dialog)),
            ft.TextButton("保存", on_click=save_reading_edit),
        ],
    )

    # --- 設定関連ハンドラ (変更時に自動保存) ---
    def on_chars_slider_change(e):
        settings["max_chars_per_line"] = int(e.control.value)
        e.control.label = f"{int(e.control.value)}文字"
        e.control.update()
        history_manager.save_settings(settings) # 保存
        if current_mapped_data:
            render_braille_preview()

    def on_lines_slider_change(e):
        settings["max_lines_per_plate"] = int(e.control.value)
        e.control.label = f"{int(e.control.value)}行"
        e.control.update()
        history_manager.save_settings(settings) # 保存
        if current_mapped_data:
            render_braille_preview()

    def on_thickness_slider_change(e):
        settings["plate_thickness"] = float(e.control.value)
        e.control.label = f"{e.control.value:.1f}mm"
        e.control.update()
        history_manager.save_settings(settings) # 保存

    def on_save_mode_change(e):
        settings["use_quick_save"] = e.control.value
        e.control.update()
        history_manager.save_settings(settings) # 保存
        
    def on_history_limit_change(e):
        new_limit = int(e.control.value)
        history_manager.set_history_limit(new_limit)
        e.control.label = f"{new_limit}件"
        e.control.update()

    def show_settings(e):
        current_limit = history_manager.get_history_limit()
        
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
                ft.Text("プレートの厚み", size=14),
                ft.Slider(
                    ref=thickness_slider_ref,
                    min=0.5, max=1.5, divisions=10, 
                    value=settings["plate_thickness"], 
                    label=f"{settings['plate_thickness']:.1f}mm",
                    on_change=on_thickness_slider_change
                ),
                ft.Divider(),
                ft.Text("履歴保存件数", size=14),
                ft.Slider(
                    ref=history_limit_slider_ref,
                    min=5, max=50, divisions=9,
                    value=current_limit,
                    label=f"{current_limit}件",
                    on_change=on_history_limit_change
                ),
                ft.Divider(),
                ft.Switch(
                    label="Quick Save (直接保存)",
                    value=settings["use_quick_save"],
                    on_change=on_save_mode_change,
                ),
            ], height=450, tight=True, scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton("閉じる", on_click=lambda e: page.close(dlg))],
        )
        page.open(dlg)

    # --- 履歴機能 ---
    def restore_history_entry(e):
        """履歴アイテムがタップされたときの復元処理"""
        entry = e.control.data
        
        # 1. 設定の復元 (settings辞書とUIの両方を更新)
        settings["max_chars_per_line"] = entry.get("max_chars_per_line", 10)
        settings["max_lines_per_plate"] = entry.get("max_lines_per_plate", 3)
        settings["plate_thickness"] = entry.get("plate_thickness", 1.0)
        
        # 現在の設定値も保存しておく（次回起動時のため）
        history_manager.save_settings(settings)
        
        # 2. テキストの復元と変換
        if txt_input_ref.current:
            txt_input_ref.current.value = entry.get("text", "")
            txt_input_ref.current.update()
            update_braille_from_input(txt_input_ref.current.value)
            
        page.close(history_dialog)
        page.open(ft.SnackBar(content=ft.Text("履歴から復元しました")))

    def show_history_dialog(e):
        """履歴一覧ダイアログを表示"""
        history_list = history_manager.get_history()
        
        if not history_list:
            content = ft.Text("履歴はありません", color=AppColors.TEXT_SUB)
        else:
            list_items = []
            for entry in history_list:
                # テキストの処理
                raw_text = entry.get("text", "")
                if len(raw_text) > 20:
                    display_text = raw_text[:20] + "..."
                else:
                    display_text = raw_text
                
                # タイムスタンプ
                timestamp = entry.get('timestamp', '')
                
                list_items.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.HISTORY, color=AppColors.PRIMARY),
                        title=ft.Text(display_text, weight=ft.FontWeight.BOLD),
                        subtitle=ft.Text(timestamp, size=12, color=AppColors.TEXT_SUB),
                        data=entry,
                        on_click=restore_history_entry
                    )
                )
            content = ft.ListView(controls=list_items, height=300)

        global history_dialog
        history_dialog = ft.AlertDialog(
            title=ft.Text("履歴 (タップして復元)"),
            content=content,
            actions=[
                ft.TextButton("全削除", on_click=lambda e: _clear_history_handler(e), style=ft.ButtonStyle(color=AppColors.ERROR)),
                ft.TextButton("閉じる", on_click=lambda e: page.close(history_dialog))
            ],
        )
        page.open(history_dialog)

    def _clear_history_handler(e):
        history_manager.clear_history()
        page.close(history_dialog)
        page.open(ft.SnackBar(content=ft.Text("履歴を削除しました")))

    # --- 保存処理 ---
    def get_structured_data_for_export():
        flat_cells_all = []
        for word_idx, item in enumerate(current_mapped_data):
            for cell in item['cells']:
                flat_cells_all.append(cell) 
            if word_idx < len(current_mapped_data) - 1:
                flat_cells_all.append({'dots': SPACE_MARK, 'char': ' '})
        
        lines = split_cells_with_rules(flat_cells_all, settings["max_chars_per_line"])
        lines_per_plate = settings["max_lines_per_plate"]
        plates = [lines[i:i + lines_per_plate] for i in range(0, len(lines), lines_per_plate)]
        return plates

    def _on_save_success(path):
        """保存成功時の共通処理"""
        text = txt_input_ref.current.value if txt_input_ref.current else ""
        if text:
            history_manager.add_entry(text, settings)
        page.open(ft.SnackBar(content=ft.Text(f"保存しました: {os.path.basename(path)}")))

    def handle_save_button_click(e):
        if not current_mapped_data:
            page.open(ft.SnackBar(content=ft.Text("データがありません。")))
            return
        
        if settings["use_quick_save"]:
            handle_quick_save()
        else:
            handle_dialog_save()

    def handle_dialog_save():
        page.update()
        file_picker.save_file(dialog_title="パッケージを保存")

    def handle_quick_save():
        try:
            home_dir = os.path.expanduser("~")
            download_dir = os.path.join(home_dir, "Downloads")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tenji_export_{timestamp}.zip"
            save_path = os.path.join(download_dir, filename)
            
            _perform_export(save_path)
            _on_save_success(save_path)
        except Exception as ex:
            page.open(ft.SnackBar(content=ft.Text(f"保存失敗: {str(ex)}"), bgcolor=AppColors.ERROR))

    def on_file_picked(e: ft.FilePickerResultEvent):
        if e.path:
            try:
                _perform_export(e.path)
                _on_save_success(e.path)
            except Exception as ex:
                page.open(ft.SnackBar(content=ft.Text(f"エラー: {str(ex)}"), bgcolor=AppColors.ERROR))

    def _perform_export(path):
        plates_data = get_structured_data_for_export()
        original_txt = txt_input_ref.current.value if txt_input_ref.current else ""
        
        stl_generator.generate_package_from_plates(
            plates_data, path, 
            original_text_str=original_txt,
            base_thickness=settings["plate_thickness"]
        )

    file_picker.on_result = on_file_picked

    # --- UI構築 ---
    txt_input = ft.TextField(
        ref=txt_input_ref,
        multiline=True, min_lines=3, max_lines=5,
        hint_text="ここに日本語を入力...",
        border=ft.InputBorder.NONE,
        text_style=TextStyles.BODY,
        on_change=lambda e: update_braille_from_input(e.control.value)
    )

    header = ft.Container(
        content=ft.Row([
            ft.IconButton(icon="menu", icon_color=AppColors.PRIMARY, on_click=lambda e: page.open(drawer)),
            ft.Text("Tenji P-Fab", style=TextStyles.HEADER),
            ft.Row([
                ft.IconButton(icon="save_alt", icon_color=AppColors.PRIMARY, tooltip="保存", on_click=handle_save_button_click),
                ft.IconButton(icon="settings", icon_color=AppColors.PRIMARY, on_click=show_settings)
            ])
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=ft.padding.only(top=50, left=10, right=10, bottom=10),
        bgcolor=AppColors.BACKGROUND
    )

    drawer = ft.NavigationDrawer(
        controls=[
            ft.Container(height=12),
            ft.NavigationDrawerDestination(
                label="履歴", 
                icon=ft.Icons.HISTORY
            ),
            ft.NavigationDrawerDestination(
                label="設定", 
                icon=ft.Icons.SETTINGS
            ),
        ],
        on_change=lambda e: show_history_dialog(e) if e.control.selected_index == 0 else show_settings(e)
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
                            # 統合された保存ボタン
                            ft.ElevatedButton(
                                "保存", 
                                icon="save",
                                style=ComponentStyles.MAIN_BUTTON_STYLE,
                                on_click=handle_save_button_click,
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

    main_view = ft.View("/", controls=[header, body_content], bgcolor=AppColors.BACKGROUND, padding=0, drawer=drawer)
    
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
