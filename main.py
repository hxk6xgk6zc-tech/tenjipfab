import logging
import sys
import os
import time
from datetime import datetime

# ログ設定
logging.basicConfig(level=logging.INFO)
print("--- App Starting (Flet 0.80.0+ API Compatible) ---")

import flet as ft

# Fletバージョンの確認用ログ
try:
    print(f"Flet version: {ft.version}")
except:
    print("Flet version: unknown")

# モジュールインポート
try:
    from styles import AppColors, TextStyles, ComponentStyles
    from braille_logic import (
        BrailleConverter, SPACE_MARK,
        DAKUTEN_MARK, HANDAKUTEN_MARK, YOON_MARK, 
        YOON_DAKU_MARK, YOON_HANDAKU_MARK, NUM_INDICATOR, FOREIGN_INDICATOR
    )
    from stl_generator import STLGenerator
    from history_manager import HistoryManager
    print("Modules loaded successfully.")
except ImportError as e:
    logging.error(f"Module import error: {e}", exc_info=True)
    sys.exit(1)

def main(page: ft.Page):
    print("--- Main Function Called ---")
    
    # --- 1. アプリ全体の初期設定 ---
    page.title = "Tenji P-Fab"
    page.bgcolor = AppColors.BACKGROUND
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 390
    page.window_height = 844
    page.padding = 0
    
    try:
        page.window_to_front()
    except Exception:
        pass

    # --- ヘルパー関数 (最新API対応) ---
    def show_snackbar(message, is_error=False, duration=3000):
        """SnackBarを表示する (page.open使用)"""
        try:
            snack = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=AppColors.ERROR if is_error else None,
                duration=duration,
                action="OK"
            )
            page.open(snack)
        except Exception as e:
            logging.error(f"Failed to show snackbar: {e}", exc_info=True)

    def open_dialog(dlg):
        """ダイアログを開く (page.open使用)"""
        print(f"DEBUG: open_dialog called for {dlg}")
        try:
            page.open(dlg)
            print("DEBUG: Dialog opened via page.open().")
        except Exception as e:
            logging.error(f"Dialog open failed: {e}", exc_info=True)

    def close_dialog(dlg):
        """ダイアログを閉じる (page.close使用)"""
        print("DEBUG: close_dialog called")
        try:
            page.close(dlg)
        except Exception as e:
            logging.error(f"Dialog close failed: {e}", exc_info=True)

    def show_drawer(drawer_control):
        """ドロワーを開く (page.open使用)"""
        print("DEBUG: show_drawer called")
        try:
            page.open(drawer_control)
            print("DEBUG: Drawer opened via page.open().")
        except Exception as e:
            logging.error(f"Failed to open drawer: {e}", exc_info=True)

    # --- FilePickerの設定 ---
    is_macos = sys.platform == "darwin"
    
    file_picker = None
    if not is_macos:
        # macOS以外ではFilePickerを使用
        try:
            file_picker = ft.FilePicker()
            page.overlay.append(file_picker)
        except Exception as e:
            logging.error(f"Failed to setup FilePicker: {e}", exc_info=True)
    
    # ロジック初期化
    converter = BrailleConverter()
    stl_generator = STLGenerator()
    history_manager = HistoryManager(page)
    
    # 状態管理
    state = {
        "current_mapped_data": [],
        "editing_index": -1
    }
    
    # 設定の初期化
    settings = {
        "max_chars_per_line": 10,
        "max_lines_per_plate": 3,
        "plate_thickness": 1.0, 
        "scale": 1.0,
        "pause_for_color": False,
        "use_quick_save": False
    }

    # macOSはデフォルトでQuick Save有効
    if is_macos:
        settings["use_quick_save"] = True

    # 設定復元
    try:
        saved_config = history_manager.load_settings()
        if saved_config:
            for key in settings.keys():
                if key in saved_config:
                    settings[key] = saved_config[key]
            # Macは強制的にTrue
            if is_macos:
                settings["use_quick_save"] = True
    except Exception as e:
        print(f"Config Load Error: {e}")
    
    # UI Refs
    txt_input_ref = ft.Ref[ft.TextField]()
    edit_field_ref = ft.Ref[ft.TextField]()
    chars_slider_ref = ft.Ref[ft.Slider]()
    lines_slider_ref = ft.Ref[ft.Slider]()
    thickness_slider_ref = ft.Ref[ft.Slider]() 
    history_limit_slider_ref = ft.Ref[ft.Slider]()
    
    # かな変換チェック
    if hasattr(converter, 'use_kakasi') and not converter.use_kakasi:
        print("Warning: Kana converter (Janome) unavailable.")

    def _make_dot(is_active):
        return ft.Container(
            width=8, height=8,
            bgcolor=AppColors.DOT_ACTIVE if is_active else AppColors.DOT_INACTIVE,
            border_radius=ft.BorderRadius(4, 4, 4, 4),
        )

    braille_display_area = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        spacing=10, 
    )

    # --- ロジック群 ---
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
            # 行あふれ判定
            if len(current_line) + unit_len > max_chars:
                if len(current_line) > 0:
                    lines.append(current_line)
                    current_line = []
            current_line.extend(unit)
            
        if current_line:
            lines.append(current_line)
        return lines

    def open_edit_dialog(index):
        print(f"DEBUG: open_edit_dialog called for index {index}")
        state["editing_index"] = index
        item = state["current_mapped_data"][index]
        edit_dialog.title = ft.Text(f"「{item['orig']}」の読みを修正")
        if edit_field_ref.current:
            edit_field_ref.current.value = item['reading']
        open_dialog(edit_dialog)

    def render_braille_preview():
        braille_display_area.controls.clear()
        
        flat_cells_all = []
        for word_idx, item in enumerate(state["current_mapped_data"]):
            for cell in item['cells']:
                flat_cells_all.append({
                    'dots': cell['dots'],
                    'char': cell['char'],
                    'word_idx': word_idx, 
                    'orig': item['orig']
                })
            if word_idx < len(state["current_mapped_data"]) - 1:
                flat_cells_all.append({
                    'dots': SPACE_MARK,
                    'char': ' ',
                    'word_idx': -1,
                    'orig': '(Space)'
                })
        
        chars_per_line = int(settings["max_chars_per_line"])
        lines_per_plate = int(settings["max_lines_per_plate"])
        
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
                                border_radius=ft.BorderRadius(4, 4, 4, 4),
                                shadow=ft.BoxShadow(blur_radius=1, color=ft.Colors.with_opacity(0.1, "#000000")), # 修正: ft.Colors
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
                    bgcolor=ft.Colors.WHITE54, # 修正: ft.Colors
                    border_radius=ft.BorderRadius(8, 8, 8, 8),
                    border=ft.border.all(1, ft.Colors.BLACK12) # 修正: ft.Colors
                ),
                ft.Divider(height=10, color=ft.Colors.TRANSPARENT) # 修正: ft.Colors
            ], spacing=2)
            
            braille_display_area.controls.append(plate_ui)
            
        page.update()

    def update_braille_from_input(text):
        state["current_mapped_data"] = converter.convert_with_mapping(text)
        render_braille_preview()

    def save_reading_edit(e):
        if state["editing_index"] < 0: return
        new_reading = edit_field_ref.current.value
        if new_reading:
            state["current_mapped_data"][state["editing_index"]]['reading'] = new_reading
            new_cells = converter.kana_to_cells(new_reading)
            state["current_mapped_data"][state["editing_index"]]['cells'] = new_cells
            state["current_mapped_data"][state["editing_index"]]['braille'] = [c['dots'] for c in new_cells]
            render_braille_preview()
            show_snackbar(f"読みを修正しました")
        close_dialog(edit_dialog)

    # 編集ダイアログ
    edit_dialog = ft.AlertDialog(
        title=ft.Text("読みの修正"),
        content=ft.TextField(ref=edit_field_ref, autofocus=True, label="読み（ひらがな）"),
        actions=[
            ft.TextButton("キャンセル", on_click=lambda e: close_dialog(edit_dialog)),
            ft.TextButton("保存", on_click=save_reading_edit),
        ],
    )

    def on_chars_slider_change(e):
        settings["max_chars_per_line"] = int(e.control.value)
        e.control.label = f"{int(e.control.value)}文字"
        e.control.update()
        history_manager.save_settings(settings)
        if state["current_mapped_data"]:
            render_braille_preview()

    def on_lines_slider_change(e):
        settings["max_lines_per_plate"] = int(e.control.value)
        e.control.label = f"{int(e.control.value)}行"
        e.control.update()
        history_manager.save_settings(settings)
        if state["current_mapped_data"]:
            render_braille_preview()

    def on_thickness_slider_change(e):
        settings["plate_thickness"] = float(e.control.value)
        e.control.label = f"{e.control.value:.1f}mm"
        e.control.update()
        history_manager.save_settings(settings)

    def on_save_mode_change(e):
        if is_macos:
            show_snackbar("macOSでは直接保存のみサポートされています")
            e.control.value = True
            e.control.update()
            return
        settings["use_quick_save"] = e.control.value
        e.control.update()
        history_manager.save_settings(settings)
        
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
                    tooltip="ダイアログを開かずに保存します（macOS等推奨）",
                    disabled=is_macos
                ),
            ], height=450, tight=True, scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton("閉じる", on_click=lambda e: close_dialog(dlg))],
        )
        open_dialog(dlg)

    def restore_history_entry(e):
        entry = e.control.data
        settings["max_chars_per_line"] = entry.get("max_chars_per_line", 10)
        settings["max_lines_per_plate"] = entry.get("max_lines_per_plate", 3)
        settings["plate_thickness"] = entry.get("plate_thickness", 1.0)
        history_manager.save_settings(settings)
        
        if txt_input_ref.current:
            txt_input_ref.current.value = entry.get("text", "")
            txt_input_ref.current.update()
            update_braille_from_input(txt_input_ref.current.value)
            
        close_dialog(history_dialog)
        show_snackbar("履歴から復元しました")

    history_dialog = None

    def show_history_dialog(e):
        nonlocal history_dialog
        history_list = history_manager.get_history()
        
        if not history_list:
            content = ft.Text("履歴はありません", color=AppColors.TEXT_SUB)
        else:
            list_items = []
            for entry in history_list:
                raw_text = entry.get("text", "")
                display_text = raw_text[:20] + "..." if len(raw_text) > 20 else raw_text
                timestamp = entry.get('timestamp', '')
                list_items.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.HISTORY, color=AppColors.PRIMARY), # 修正: ft.Icons
                        title=ft.Text(display_text, weight=ft.FontWeight.BOLD),
                        subtitle=ft.Text(timestamp, size=12, color=AppColors.TEXT_SUB),
                        data=entry,
                        on_click=restore_history_entry
                    )
                )
            content = ft.ListView(controls=list_items, height=300)

        history_dialog = ft.AlertDialog(
            title=ft.Text("履歴"),
            content=content,
            actions=[
                ft.TextButton("全削除", on_click=lambda e: _clear_history_handler(e), style=ft.ButtonStyle(color=AppColors.ERROR)),
                ft.TextButton("閉じる", on_click=lambda e: close_dialog(history_dialog))
            ],
        )
        open_dialog(history_dialog)

    def _clear_history_handler(e):
        history_manager.clear_history()
        close_dialog(history_dialog)
        show_snackbar("履歴を削除しました")

    def get_structured_data_for_export():
        flat_cells_all = []
        for word_idx, item in enumerate(state["current_mapped_data"]):
            for cell in item['cells']:
                flat_cells_all.append(cell) 
            if word_idx < len(state["current_mapped_data"]) - 1:
                flat_cells_all.append({'dots': SPACE_MARK, 'char': ' '})
        lines = split_cells_with_rules(flat_cells_all, settings["max_chars_per_line"])
        lines_per_plate = settings["max_lines_per_plate"]
        plates = [lines[i:i + lines_per_plate] for i in range(0, len(lines), lines_per_plate)]
        return plates

    def _on_save_success(path):
        text = txt_input_ref.current.value if txt_input_ref.current else ""
        if text:
            history_manager.add_entry(text, settings)
        show_snackbar(f"保存しました: {os.path.basename(path)}")

    def handle_save_button_click(e):
        if not state["current_mapped_data"]:
            show_snackbar("データがありません。")
            return
        
        if settings["use_quick_save"]:
            handle_quick_save()
        else:
            handle_dialog_save()

    def handle_dialog_save():
        if file_picker:
            page.update()
            file_picker.save_file(dialog_title="パッケージを保存")
        else:
            handle_quick_save()

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
            show_snackbar(f"保存失敗: {str(ex)}", is_error=True)

    def on_file_picked(e):
        if e.path:
            try:
                _perform_export(e.path)
                _on_save_success(e.path)
            except Exception as ex:
                show_snackbar(f"エラー: {str(ex)}", is_error=True)

    def _perform_export(path):
        plates_data = get_structured_data_for_export()
        original_txt = txt_input_ref.current.value if txt_input_ref.current else ""
        stl_generator.generate_package_from_plates(
            plates_data, path, 
            original_text_str=original_txt,
            base_thickness=settings["plate_thickness"]
        )

    if file_picker:
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
            # 修正: ft.Icons
            ft.IconButton(icon=ft.Icons.MENU, icon_color=AppColors.PRIMARY, on_click=lambda e: show_drawer(drawer)),
            ft.Text("Tenji P-Fab", style=TextStyles.HEADER),
            ft.Row([
                ft.IconButton(icon=ft.Icons.SAVE_ALT, icon_color=AppColors.PRIMARY, tooltip="保存", on_click=handle_save_button_click),
                ft.IconButton(icon=ft.Icons.SETTINGS, icon_color=AppColors.PRIMARY, on_click=show_settings)
            ])
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=ft.Padding(left=10, top=50, right=10, bottom=10),
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
        ft.Container(
            content=ft.Column([
                ft.Text("Braille Preview (Tap to edit)", style=TextStyles.CAPTION),
                ft.Container(
                    content=braille_display_area,
                    expand=True,
                    padding=10, 
                    alignment=ft.Alignment(-1, -1),
                )
            ]),
            expand=True, 
            bgcolor=AppColors.BACKGROUND,
        ),
        ft.Container(
            content=ft.Column([
                ft.Text("Input Text", style=TextStyles.CAPTION),
                ft.Container(
                    content=ft.Column([
                        txt_input,
                        ft.Divider(color=AppColors.BACKGROUND),
                        ft.Row([
                            ft.IconButton(icon=ft.Icons.MIC, icon_color=AppColors.PRIMARY),
                            ft.Container(width=10),
                            ft.ElevatedButton(
                                "保存", 
                                icon=ft.Icons.SAVE,
                                style=ComponentStyles.MAIN_BUTTON_STYLE,
                                on_click=handle_save_button_click,
                                expand=True
                            )
                        ])
                    ]),
                    bgcolor=AppColors.SURFACE,
                    border_radius=ft.BorderRadius(12, 12, 12, 12),
                    shadow=ComponentStyles.CARD_SHADOW,
                    padding=20,
                )
            ]),
            expand=True, padding=20,
            border_radius=ft.BorderRadius(30, 30, 0, 0),
            bgcolor=AppColors.SURFACE,
        )
    ], spacing=0, expand=True)

    main_view = ft.View(
        route="/", 
        controls=[header, body_content], 
        bgcolor=AppColors.BACKGROUND, 
        padding=0, 
        drawer=drawer
    )
    
    splash_content = ft.Container(
        content=ft.Column(
            [ft.Icon(ft.Icons.GRID_ON_ROUNDED, size=80, color=AppColors.SURFACE),
             ft.Text("Tenji P-Fab", style=ft.TextStyle(size=30, weight=ft.FontWeight.BOLD, color=AppColors.SURFACE))],
            alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER
        ),
        bgcolor=AppColors.PRIMARY, alignment=ft.Alignment(0, 0), expand=True
    )

    page.add(splash_content)
    page.update()
    time.sleep(1) 
    page.views.clear()
    page.views.append(main_view)
    page.update()

if __name__ == "__main__":
    assets_path = os.path.join(os.getcwd(), "assets")
    if not os.path.exists(assets_path):
        os.makedirs(assets_path)
    
    ft.app(target=main, assets_dir="assets", port=0)
