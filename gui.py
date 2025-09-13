from datetime import datetime
import os
import sys

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QPixmap, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.game_memory import GameProcess, CharacterScannerThread
from config import (
    ANIMAL_ORBS,
    CHARACTERS,
    INSANE_LEVEL_UNLOCKS_FLAT,
    NORMAL_LEVEL_UNLOCKS_FLAT,
    OFFSETS,
    PROCESS_NAME,
    RELIC_UNLOCKS,
    SKULL_OPTIONS,
    STATS_DISPLAY,
    STRUCT_SIZE,
    WEAPONS,
)


# ---------------------- Utilities ----------------------
def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def load_stylesheet(path):
    with open(resource_path(path), "r", encoding="utf-8") as file:
        stylesheet = file.read()

    image_map = {
        "images/chevron-down.png": resource_path("images/chevron-down.png"),
        "images/chevron-up.png": resource_path("images/chevron-up.png"),
    }

    for placeholder, real_path in image_map.items():
        stylesheet = stylesheet.replace(
            f"url({placeholder})", f"url({real_path.replace('\\', '/')})")

    return stylesheet


def pick_cascading_flat_index(byte_tuple, flattened_list):
    byte0, byte1, byte2 = byte_tuple
    if byte2 != 0:
        byte1 = byte0 = 0xFF
    elif byte1 != 0:
        byte0 = 0xFF

    cascaded_tuple = (byte0, byte1, byte2)
    for index, (_, values) in enumerate(flattened_list):
        if values == cascaded_tuple:
            return index

    # Fallback by highest non-zero byte
    if byte2 != 0:
        target, array_index = byte2, 2
    elif byte1 != 0:
        target, array_index = byte1, 1
    else:
        target, array_index = byte0, 0

    for index, (_, (ai, value)) in enumerate(flattened_list):
        if ai == array_index and value == target:
            return index
    return 0


# ---------------------- Game Process Monitor ----------------------
class GameProcessMonitor:

    def __init__(self,
                 status_log,
                 apply_changes_button=None,
                 process_name=PROCESS_NAME):
        self.status_log = status_log
        self.apply_changes_button = apply_changes_button
        self.process_name = process_name
        self.game_process = GameProcess(process_name)
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_process)
        self.timer.start(1000)

        self.attached = False
        self.character_data = []
        self.first_character_address = None

        # GUI Element References
        self.checkboxes = {}
        self.combos = {}
        self.spinboxes = {}
        self.current_character_name = None

        # Scanner Thread
        self.scanner = None
        self.scanning = False
        self.scan_complete = False

        # Track last status
        self.last_status = None

        if apply_changes_button:
            apply_changes_button.clicked.connect(self.apply_current_changes)

    # ---------------------- Status ----------------------
    def append_status(self, message, color):
        message = str(message).rstrip("\n")
        timestamp = f"[{datetime.now().strftime('%H:%M:%S')}] "

        cursor = self.status_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        timestamp_format = QTextCharFormat()
        timestamp_format.setForeground(QColor("#f0f0f0"))
        cursor.insertText(timestamp, timestamp_format)

        message_format = QTextCharFormat()
        message_format.setForeground(color)
        cursor.insertText(message + "\n", message_format)

        self.status_log.setTextCursor(cursor)
        self.status_log.ensureCursorVisible()

    def check_process(self):
        try:
            if self.game_process.attach():
                if not self.attached:
                    self.attached = True
                    self.append_status(
                        f"Successfully connected to {self.process_name}!",
                        QColor("#4caf50"))
                    self.start_scan()
                    self.last_status = "attached"
            else:
                if self.last_status != "detached":
                    self.attached = False
                    self.first_character_address = None
                    self.append_status(
                        f"Waiting for {self.process_name} to start...",
                        QColor("#f0f0f0"))

                    self.stop_scanner()

                    if self.apply_changes_button:
                        self.apply_changes_button.setEnabled(False)
                    if hasattr(self, "rescan_button"):
                        self.rescan_button.setEnabled(False)

                    self.last_status = "detached"
        except Exception as e:
            if self.last_status != "error":
                self.attached = False
                self.first_character_address = None
                self.append_status(
                    f"Error checking {self.process_name}: {e}. Ensure that the game is running.",
                    QColor("#ff5555"))

                self.stop_scanner()

                if self.apply_changes_button:
                    self.apply_changes_button.setEnabled(False)
                if hasattr(self, "rescan_button"):
                    self.rescan_button.setEnabled(False)

                self.last_status = "error"

    # ---------------------- Memory Scan ----------------------
    def start_scan(self):
        if not self.attached:
            self.append_status(
                f"Cannot scan because {self.process_name} is not attached. Please start the game first.",
                QColor("#ff5555"))
            return

        if self.scanner is not None:
            self.append_status("Scan already in progress.", QColor("#ffa500"))
            return

        self.scanning = True
        if self.apply_changes_button:
            self.apply_changes_button.setEnabled(False)
        if hasattr(self, "rescan_button"):
            self.rescan_button.setEnabled(False)

        self.append_status("Starting scan in 3 seconds...", QColor("#2196f3"))
        QTimer.singleShot(3000, self._begin_scan)

    def _begin_scan(self):
        self.scanner = CharacterScannerThread(self.game_process)
        self.scanner.status_update.connect(self.append_status)
        self.scanner.scan_finished.connect(self.populate_character_fields)
        self.scanner.start()

    def stop_scanner(self):
        if self.scanner:
            self.scanner.quit()
            self.scanner.wait()
            self.scanner = None

    def populate_character_fields(self, all_character_data):
        self.character_data = all_character_data
        self.first_character_address = self.game_process.find_first_character_address(
        )
        self.scan_complete = True
        self.scanning = False

        self.append_status(
            f"Character data populated for {len(all_character_data)} entries.",
            QColor("#4caf50"))

        if self.current_character_name:
            self.populate_character_ui(self.current_character_name)

        if self.apply_changes_button and self.attached:
            self.apply_changes_button.setEnabled(True)
        if hasattr(self, "rescan_button"):
            self.rescan_button.setEnabled(True)

        self.stop_scanner()

    # ---------------------- Registration ----------------------
    def register_character_checkbox(self, name, checkbox):
        self.checkboxes[name] = checkbox

    def register_character_combos(self, combos_dict):
        self.combos = combos_dict

    def register_character_spinboxes(self, spinboxes_dict):
        self.spinboxes = spinboxes_dict

    # ---------------------- UI Population ----------------------
    def populate_character_ui(self, selected_name):
        self.current_character_name = selected_name
        if selected_name not in CHARACTERS:
            return

        character_index = CHARACTERS[selected_name]["id"] - 1
        if character_index >= len(self.character_data):
            if self.scan_complete:
                self.append_status(f"No character data for {selected_name}.",
                                   QColor("#ffa500"))
            return

        character_memory_block = self.character_data[character_index]

        # Checkboxes
        self.checkboxes["character_unlocked"].setChecked(
            bool(character_memory_block.get("is_character_unlocked")))
        self.checkboxes["insane_mode_unlocked"].setChecked(
            character_memory_block.get("insane_mode", 0) == 0x01)

        # Combos
        def set_combo(combo: QComboBox, value):
            for i in range(combo.count()):
                if combo.itemData(i) == value:
                    combo.setCurrentIndex(i)
                    return
            combo.setCurrentIndex(0)

        set_combo(self.combos["weapon"],
                  character_memory_block.get("weapon", 0))
        set_combo(self.combos["animal_type"],
                  character_memory_block.get("animal_type", 0))
        set_combo(self.combos["relic_unlocks"],
                  character_memory_block.get("relic_unlocks", 0))
        set_combo(self.combos["skull"], character_memory_block.get("skull", 0))

        # Level Unlocks
        normal_level_bytes = (
            character_memory_block.get("normal_level_unlocks_0", 0),
            character_memory_block.get("normal_level_unlocks_1", 0),
            character_memory_block.get("normal_level_unlocks_2", 0),
        )
        insane_level_bytes = (
            character_memory_block.get("insane_level_unlocks_0", 0),
            character_memory_block.get("insane_level_unlocks_1", 0),
            character_memory_block.get("insane_level_unlocks_2", 0),
        )
        self.combos["normal_level_unlocks"].setCurrentIndex(
            pick_cascading_flat_index(normal_level_bytes,
                                      NORMAL_LEVEL_UNLOCKS_FLAT))
        self.combos["insane_level_unlocks"].setCurrentIndex(
            pick_cascading_flat_index(insane_level_bytes,
                                      INSANE_LEVEL_UNLOCKS_FLAT))

        # Stats
        for stat_name, stat_spinbox in self.spinboxes.items():
            value = int(character_memory_block.get(stat_name, 0))
            stat_spinbox.setValue(value + 1 if stat_name == "level" else value)

    # ---------------------- Apply Changes ----------------------
    def apply_current_changes(self):
        selected_name = self.current_character_name
        if not selected_name or selected_name not in CHARACTERS:
            self.append_status("No character selected.", QColor("#ff5555"))
            return
        if not self.first_character_address:
            self.append_status("No base address yet.", QColor("#ff5555"))
            return

        character_index = CHARACTERS[selected_name]["id"] - 1
        character_base_address = self.first_character_address + (
            character_index * STRUCT_SIZE)
        character_memory_block = self.character_data[character_index]

        # Checkboxes
        self.game_process.write_struct_field(
            character_base_address,
            "is_character_unlocked",
            0x80
            if self.checkboxes["character_unlocked"].isChecked() else 0x00,
        )
        self.game_process.write_struct_field(
            character_base_address,
            "insane_mode",
            0x01
            if self.checkboxes["insane_mode_unlocked"].isChecked() else 0x00,
        )

        # Combos
        for combo_name in ["weapon", "animal_type", "relic_unlocks", "skull"]:
            self.game_process.write_struct_field(
                character_base_address, combo_name,
                self.combos[combo_name].currentData())

        # Levels
        def flat_to_bytes(flat_list, index):
            if not (0 <= index < len(flat_list)):
                return (0, 0, 0)
            _, (byte_index, value) = flat_list[index]
            b0 = b1 = b2 = 0
            if byte_index == 0: b0 = value
            elif byte_index == 1: b1 = value
            elif byte_index == 2: b2 = value
            if b2 != 0: b1 = b0 = 0xFF
            elif b1 != 0: b0 = 0xFF
            return (b0, b1, b2)

        normal_level_byte0, normal_level_byte1, normal_level_byte2 = flat_to_bytes(
            NORMAL_LEVEL_UNLOCKS_FLAT,
            self.combos["normal_level_unlocks"].currentIndex())
        insane_level_byte0, insane_level_byte1, insane_level_byte2 = flat_to_bytes(
            INSANE_LEVEL_UNLOCKS_FLAT,
            self.combos["insane_level_unlocks"].currentIndex())

        for field_name, value in zip(
            [
                "normal_level_unlocks_0",
                "normal_level_unlocks_1",
                "normal_level_unlocks_2",
                "insane_level_unlocks_0",
                "insane_level_unlocks_1",
                "insane_level_unlocks_2",
            ],
            [
                normal_level_byte0,
                normal_level_byte1,
                normal_level_byte2,
                insane_level_byte0,
                insane_level_byte1,
                insane_level_byte2,
            ],
        ):
            self.game_process.write_struct_field(character_base_address,
                                                 field_name, value)
            character_memory_block[field_name] = value

        # Stats
        for stat_name, stat_spinbox in self.spinboxes.items():
            memory_value = stat_spinbox.value(
            ) - 1 if stat_name == "level" else stat_spinbox.value()
            self.game_process.write_struct_field(character_base_address,
                                                 stat_name, memory_value)
            character_memory_block[stat_name] = memory_value

        self.append_status(f"Applied changes to {selected_name}.",
                           QColor("#4caf50"))


# ---------------------- Profile UI ----------------------
def update_character_profile(selected_name, name_label, image_label):
    character_info = CHARACTERS.get(selected_name)
    if character_info is None:
        name_label.setText(selected_name or "No Character Selected")
        pixmap = QPixmap(200, 200)
        pixmap.fill(Qt.GlobalColor.gray)
    else:
        image_path = resource_path(character_info["image"])
        if not os.path.exists(image_path):
            pixmap = QPixmap(200, 200)
            pixmap.fill(Qt.GlobalColor.gray)
        else:
            pixmap = QPixmap(image_path)

        name_label.setText(selected_name)

    image_label.setPixmap(
        pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio,
                      Qt.TransformationMode.SmoothTransformation))
    image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)


# ---------------------- GUI ----------------------
def run_gui():
    icon_path = resource_path("icons/app_icon.ico")

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(icon_path))

    window = QWidget()
    window.setWindowTitle("Castle Crashers Memory Editor v1.0.2")
    window.setWindowIcon(QIcon(icon_path))

    window.setWindowFlags(Qt.WindowType.Window
                          | Qt.WindowType.WindowTitleHint
                          | Qt.WindowType.WindowMinimizeButtonHint
                          | Qt.WindowType.WindowCloseButtonHint
                          | Qt.WindowType.CustomizeWindowHint)

    window.setFixedSize(1050, 500)

    # Load QSS Stylesheet
    qss = load_stylesheet("style/styles.qss")
    app.setStyleSheet(qss)

    # ---------------------- Layouts ----------------------
    main_layout = QHBoxLayout()
    main_layout.setSpacing(10)

    # Character List
    character_list = QListWidget()
    character_list.addItems(CHARACTERS.keys())
    character_list.setAlternatingRowColors(True)
    character_list.setFixedWidth(175)
    main_layout.addWidget(character_list)

    # Profile + Combos
    profile_frame = QFrame()
    profile_layout = QVBoxLayout(profile_frame)
    profile_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    profile_layout.setSpacing(10)

    name_label = QLabel()
    name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    name_label.setContentsMargins(0, -6, 0, 0)
    name_label.setObjectName("nameLabel")
    profile_layout.addWidget(name_label)

    image_label = QLabel()
    profile_layout.addWidget(image_label)

    character_unlocked_checkbox = QCheckBox("Character Unlocked")
    insane_mode_unlocked_checkbox = QCheckBox("Insane Mode Unlocked")
    unlocks_layout = QHBoxLayout()
    unlocks_layout.setSpacing(15)
    unlocks_layout.addWidget(character_unlocked_checkbox)
    unlocks_layout.addWidget(insane_mode_unlocked_checkbox)
    profile_layout.addLayout(unlocks_layout)

    def add_combo(label_text, items):
        hbox = QHBoxLayout()
        label = QLabel(label_text)
        combo = QComboBox()
        for name, value in items:
            combo.addItem(name, value)
        combo.setFixedWidth(275)
        hbox.addWidget(label)
        hbox.addWidget(combo)
        profile_layout.addLayout(hbox)
        return combo

    combos = {
        "weapon": add_combo("Weapon", WEAPONS),
        "animal_type": add_combo("Animal Orb", ANIMAL_ORBS),
        "normal_level_unlocks": add_combo("Normal Mode",
                                          NORMAL_LEVEL_UNLOCKS_FLAT),
        "insane_level_unlocks": add_combo("Insane Mode",
                                          INSANE_LEVEL_UNLOCKS_FLAT),
        "relic_unlocks": add_combo("Relic Unlocks", RELIC_UNLOCKS),
        "skull": add_combo("Skull", SKULL_OPTIONS),
    }

    main_layout.addWidget(profile_frame, 1)

    # ---------------------- Details Panel ----------------------
    details_layout = QVBoxLayout()
    details_layout.setSpacing(15)

    # Stats Group
    stats_group = QGroupBox("Stats")
    stats_grid = QGridLayout(stats_group)
    stats_grid.setHorizontalSpacing(20)
    stats_grid.setVerticalSpacing(5)

    spinboxes = {}
    for i, (stat_name, display_name) in enumerate(STATS_DISPLAY.items()):
        label = QLabel(display_name)
        spinbox = QSpinBox()
        dtype = OFFSETS[stat_name]["type"]
        if dtype == "byte":
            spinbox.setRange(0, 255)
        elif dtype == "int32":
            spinbox.setRange(-2147483648, 2147483647)
        stats_grid.addWidget(label, i // 2, (i % 2) * 2)
        stats_grid.addWidget(spinbox, i // 2, (i % 2) * 2 + 1)
        spinboxes[stat_name] = spinbox
    details_layout.addWidget(stats_group)

    # Buttons Row
    buttons_layout = QHBoxLayout()
    buttons_layout.setSpacing(15)

    apply_changes_button = QPushButton("Apply Changes")
    apply_changes_button.setFixedWidth(150)
    apply_changes_button.setEnabled(False)
    buttons_layout.addWidget(apply_changes_button)

    rescan_button = QPushButton("Rescan Memory")
    rescan_button.setFixedWidth(150)
    rescan_button.setEnabled(False)
    buttons_layout.addWidget(rescan_button)

    buttons_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    details_layout.addLayout(buttons_layout, stretch=0)

    # Status Log
    status_log = QTextEdit()
    status_log.setReadOnly(True)
    status_log.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
    status_log.setObjectName("statusLog")
    details_layout.addWidget(status_log)

    # ---------------------- Monitor --------------
    monitor = GameProcessMonitor(status_log, apply_changes_button)
    monitor.register_character_checkbox("character_unlocked",
                                        character_unlocked_checkbox)
    monitor.register_character_checkbox("insane_mode_unlocked",
                                        insane_mode_unlocked_checkbox)
    monitor.register_character_combos(combos)
    monitor.register_character_spinboxes(spinboxes)
    monitor.rescan_button = rescan_button

    rescan_button.clicked.connect(lambda: monitor._begin_scan())

    # Character Selection
    def on_character_selected(selected_name):
        monitor.populate_character_ui(selected_name)
        update_character_profile(selected_name, name_label, image_label)

    character_list.currentTextChanged.connect(on_character_selected)

    # Window Close
    def on_close(event):
        monitor.stop_scanner()
        if monitor.timer.isActive():
            monitor.timer.stop()
        event.accept()

    window.closeEvent = on_close

    # Final Layout
    main_layout.addLayout(details_layout, 2)
    window.setLayout(main_layout)
    window.show()
    sys.exit(app.exec())