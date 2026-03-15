from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import Any, Callable


class HotkeyOverlayApp:
    def __init__(
        self,
        title: str,
        submit_handler: Callable[[str], dict[str, Any]],
        voice_input_handler: Callable[[], dict[str, Any]] | None = None,
        status_supplier: Callable[[], dict[str, Any]] | None = None,
        hotkey_label: str = "ctrl+alt+space",
        state_path: Path | None = None,
    ) -> None:
        self.title = title
        self.submit_handler = submit_handler
        self.voice_input_handler = voice_input_handler
        self.status_supplier = status_supplier
        self.hotkey_label = hotkey_label
        self.state_path = state_path
        self.result_queue: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        self.voice_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.status_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.pending_prompt_index: str | None = None
        self.compact_mode = True
        self.drag_origin_x = 0
        self.drag_origin_y = 0
        self.voice_capture_active = False
        self._save_state_job: str | None = None
        self._tooltip_window: tk.Toplevel | None = None
        self.window_state = self._load_window_state()

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(title)
        self.root.configure(bg="#0A0F16")
        self.root.resizable(True, True)
        self.root.attributes("-topmost", True)
        self.root.bind_all("<Control-KeyPress>", self._handle_control_keypress, add="+")
        self.root.bind_all("<Control-Up>", lambda event: self._resize_window(0, -40), add="+")
        self.root.bind_all("<Control-Down>", lambda event: self._resize_window(0, 40), add="+")
        self.root.bind_all("<Control-Left>", lambda event: self._resize_window(-60, 0), add="+")
        self.root.bind_all("<Control-Right>", lambda event: self._resize_window(60, 0), add="+")

        self.window = tk.Toplevel(self.root)
        self.window.withdraw()
        self.window.title(title)
        self.window.configure(bg="#0A0F16")
        self.window.resizable(True, True)
        self.window.attributes("-topmost", True)
        self.window.overrideredirect(True)
        self.window.protocol("WM_DELETE_WINDOW", self.hide)
        self.window.bind("<Escape>", lambda _event: self.hide())
        self.window.bind("<Control-l>", lambda _event: self._clear_transcript())
        self.window.bind("<Configure>", self._on_window_configure)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#0A0F16")
        style.configure(
            "TEntry",
            fieldbackground="#111925",
            foreground="#EAF1F7",
            bordercolor="#203246",
            lightcolor="#203246",
            darkcolor="#203246",
        )
        style.configure(
            "TButton",
            background="#F06A3A",
            foreground="#FFFFFF",
            borderwidth=0,
            focusthickness=0,
            focuscolor="#F06A3A",
            font=("Bahnschrift", 10),
        )
        style.map("TButton", background=[("active", "#C8542A")])
        style.configure("Ghost.TButton", background="#162131", foreground="#D8E2EC")
        style.map("Ghost.TButton", background=[("active", "#1E3046")])

        shell = tk.Frame(self.window, bg="#0A0F16", padx=16, pady=16)
        shell.pack(fill="both", expand=True)
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(2, weight=1)

        header = tk.Frame(shell, bg="#0A0F16")
        header.grid(row=0, column=0, sticky="ew")
        self._bind_drag(header)

        title_box = tk.Frame(header, bg="#0A0F16")
        title_box.pack(side="left", fill="x", expand=True)
        self._bind_drag(title_box)
        tk.Label(
            title_box,
            text=title,
            bg="#0A0F16",
            fg="#F3F7FB",
            font=("Bahnschrift", 20, "bold"),
        ).pack(anchor="w")
        self.subtitle_label = tk.Label(
            title_box,
            text="Локальный ассистент с model-first actions и живым runtime context",
            bg="#0A0F16",
            fg="#8DA2B6",
            font=("Bahnschrift", 9),
        )
        self.subtitle_label.pack(anchor="w", pady=(2, 0))

        self.hotkey_chip = tk.Label(
            header,
            text=f"Hotkey  {self.hotkey_label}",
            bg="#162131",
            fg="#D9E6F2",
            padx=12,
            pady=8,
            font=("Bahnschrift", 10, "bold"),
        )
        self.hotkey_chip.pack(side="right")
        self._bind_drag(self.hotkey_chip)

        self.controls_bar = tk.Frame(header, bg="#0A0F16")
        self.controls_bar.pack(side="right", padx=(0, 10))
        ttk.Button(self.controls_bar, text="Focus", command=self.toggle_compact_mode, style="Ghost.TButton").pack(side="left")

        self.hint_chip = tk.Label(
            header,
            text="Shortcuts",
            bg="#1E3046",
            fg="#D8E7F6",
            padx=10,
            pady=8,
            font=("Bahnschrift", 10, "bold"),
        )
        self.hint_chip.pack(side="right", padx=(0, 10))
        self.hint_chip.bind("<Enter>", self._show_shortcuts_tooltip)
        self.hint_chip.bind("<Leave>", self._hide_shortcuts_tooltip)
        self._bind_drag(self.hint_chip)

        chips = tk.Frame(shell, bg="#0A0F16")
        chips.grid(row=1, column=0, sticky="ew", pady=(14, 12))
        self.llm_chip = self._make_chip(chips, "LLM", "checking", "#193329", "#C8F7D2")
        self.memory_chip = self._make_chip(chips, "Memory", "checking", "#2B213A", "#E6D9FF")
        self.shortcuts_chip = self._make_chip(chips, "Shortcuts", "0", "#1B2736", "#D8E7F6")
        self.voice_chip = self._make_chip(chips, "Voice", "off", "#1B2736", "#D8E7F6")
        self.mode_chip = self._make_chip(chips, "Mode", "overlay", "#3A2417", "#FFD8C7")
        self.chips = chips

        content = tk.Frame(shell, bg="#0A0F16")
        content.grid(row=2, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        transcript_card = tk.Frame(content, bg="#101823", highlightthickness=1, highlightbackground="#1E2C3B")
        transcript_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        transcript_header = tk.Frame(transcript_card, bg="#101823")
        transcript_header.pack(fill="x", padx=12, pady=(10, 8))
        tk.Label(
            transcript_header,
            text="Диалог",
            bg="#101823",
            fg="#F3F7FB",
            font=("Bahnschrift", 11, "bold"),
        ).pack(side="left")
        self.status_line = tk.Label(
            transcript_header,
            text="ready",
            bg="#101823",
            fg="#76D7C4",
            font=("Bahnschrift", 9),
        )
        self.status_line.pack(side="right")

        self.transcript = tk.Text(
            transcript_card,
            width=74,
            height=18,
            wrap="word",
            bg="#101823",
            fg="#EAF1F7",
            insertbackground="#EAF1F7",
            relief="flat",
            padx=14,
            pady=10,
            font=("Cascadia Mono", 10),
            spacing1=2,
            spacing3=6,
        )
        self.transcript.tag_configure("assistant_label", foreground="#F7B267", font=("Bahnschrift", 10, "bold"))
        self.transcript.tag_configure("user_label", foreground="#71C6FF", font=("Bahnschrift", 10, "bold"))
        self.transcript.tag_configure("meta", foreground="#93A7BB", font=("Bahnschrift", 9))
        self.transcript.tag_configure("assistant_text", foreground="#F3F7FB")
        self.transcript.tag_configure("user_text", foreground="#D8E7F6")
        self.transcript.tag_configure("system_text", foreground="#A9BACB")
        self.transcript.bind("<Key>", self._block_transcript_edit)
        self.transcript.bind("<Control-c>", self._copy_transcript_selection)
        self.transcript.bind("<Control-a>", self._select_all_transcript)
        self.transcript.bind("<Button-3>", self._show_transcript_menu)
        self.transcript.pack(fill="both", expand=True, padx=2, pady=(0, 2))
        self.transcript_menu = tk.Menu(self.window, tearoff=0)
        self.transcript_menu.add_command(label="Copy", command=self._copy_transcript_selection_command)
        self.transcript_menu.add_command(label="Select All", command=self._select_all_transcript_command)

        side = tk.Frame(content, bg="#0A0F16", width=248)
        side.grid(row=0, column=1, sticky="ns")
        side.pack_propagate(False)
        self.side_panel = side

        actions_card = tk.Frame(side, bg="#101823", highlightthickness=1, highlightbackground="#1E2C3B")
        actions_card.pack(fill="x")
        tk.Label(
            actions_card,
            text="Последние действия",
            bg="#101823",
            fg="#F3F7FB",
            font=("Bahnschrift", 11, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 6))
        self.action_list = tk.Listbox(
            actions_card,
            bg="#101823",
            fg="#DCE6EF",
            highlightthickness=0,
            borderwidth=0,
            selectbackground="#16293C",
            selectforeground="#FFFFFF",
            activestyle="none",
            font=("Bahnschrift", 10),
            height=8,
        )
        self.action_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        quick_card = tk.Frame(side, bg="#101823", highlightthickness=1, highlightbackground="#1E2C3B")
        quick_card.pack(fill="x", pady=(12, 0))
        tk.Label(
            quick_card,
            text="Быстрые запросы",
            bg="#101823",
            fg="#F3F7FB",
            font=("Bahnschrift", 11, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 8))
        for label, prompt in (
            ("Погода", "какая погода сегодня?"),
            ("Новости", "дай короткую выжимку по новостям про игры"),
            ("Музыка", "открой музыку"),
            ("Статус", "status"),
        ):
            ttk.Button(
                quick_card,
                text=label,
                command=lambda value=prompt: self._inject_prompt(value),
                style="Ghost.TButton",
            ).pack(fill="x", padx=10, pady=(0, 8))

        self.suggestion_card = tk.Frame(shell, bg="#101823", highlightthickness=1, highlightbackground="#1E2C3B")
        self.suggestion_card.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        tk.Label(
            self.suggestion_card,
            text="Подходящие ярлыки",
            bg="#101823",
            fg="#F3F7FB",
            font=("Bahnschrift", 10, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 8))
        self.suggestion_buttons_row = tk.Frame(self.suggestion_card, bg="#101823")
        self.suggestion_buttons_row.pack(fill="x", padx=10, pady=(0, 10))
        self.suggestion_buttons: list[ttk.Button] = []
        self.suggestion_card.grid_remove()

        composer = tk.Frame(shell, bg="#0A0F16", height=116)
        composer.grid(row=4, column=0, sticky="ew", pady=(0, 0))
        composer.grid_columnconfigure(0, weight=1)
        input_card = tk.Frame(composer, bg="#101823", highlightthickness=1, highlightbackground="#1E2C3B")
        input_card.grid(row=0, column=0, sticky="ew")

        input_header = tk.Frame(input_card, bg="#101823")
        input_header.pack(fill="x", padx=12, pady=(10, 2))
        tk.Label(
            input_header,
            text="Поле ввода",
            bg="#101823",
            fg="#F3F7FB",
            font=("Bahnschrift", 10, "bold"),
        ).pack(side="left")
        tk.Label(
            input_header,
            text="Enter = отправить",
            bg="#101823",
            fg="#8DA2B6",
            font=("Bahnschrift", 9),
        ).pack(side="right")

        entry_shell = tk.Frame(input_card, bg="#101823")
        entry_shell.pack(fill="x", padx=12, pady=(0, 12))
        self.input_var = tk.StringVar()
        self.entry = tk.Entry(
            entry_shell,
            textvariable=self.input_var,
            bg="#132030",
            fg="#F3F7FB",
            insertbackground="#F06A3A",
            insertwidth=2,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#27415A",
            highlightcolor="#F06A3A",
            font=("Bahnschrift", 11),
        )
        self.entry.pack(fill="x", expand=True, ipady=10)
        self.entry.bind("<Return>", self._on_submit)

        greeting = "Готов. Нажми хоткей и напиши сообщение."
        if self.voice_input_handler is not None:
            greeting += " Ctrl+4 — диктовка."
        self._append_line("assistant", greeting)
        self.window.after(120, self._poll_results)
        self.window.after(140, self._poll_voice_results)
        self.window.after(160, self._poll_status)
        self.window.after(300, self._schedule_status_refresh)
        self.compact_mode = bool(self.window_state.get("compact_mode", True))
        self._apply_compact_mode()

    def run(self) -> int:
        self.root.mainloop()
        return 0

    def show(self) -> None:
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()
        self._apply_saved_geometry()
        self.window.minsize(560, 320)
        self.entry.focus_set()
        self._schedule_status_refresh()

    def hide(self) -> None:
        self._save_window_state()
        self.window.withdraw()

    def toggle(self) -> None:
        if self.window.state() == "withdrawn":
            self.show()
        else:
            self.show()

    def enqueue_result(self, user_text: str, result: dict[str, Any]) -> None:
        self.result_queue.put((user_text, result))

    def _submit_from_button(self) -> None:
        self._submit()

    def _on_submit(self, _event: tk.Event[tk.Misc]) -> str | None:
        self._submit()
        return "break"

    def _submit(self) -> None:
        user_text = self.input_var.get().strip()
        if not user_text:
            return
        self.input_var.set("")
        self._append_line("you", user_text)
        self.pending_prompt_index = self._append_line("assistant", "...")
        self.status_line.configure(text="thinking", fg="#F7B267")
        threading.Thread(
            target=self._run_submit,
            args=(user_text,),
            daemon=True,
        ).start()

    def _run_submit(self, user_text: str) -> None:
        result = self.submit_handler(user_text)
        self.enqueue_result(user_text, result)

    def _poll_results(self) -> None:
        while True:
            try:
                user_text, result = self.result_queue.get_nowait()
            except queue.Empty:
                break
            self._replace_last_assistant_line(result.get("message", "No response"))
            self._update_actions(result)
            self._update_suggestions(result)
            self.status_line.configure(text="ready", fg="#76D7C4")
        self.window.after(120, self._poll_results)

    def _poll_status(self) -> None:
        while True:
            try:
                snapshot = self.status_queue.get_nowait()
            except queue.Empty:
                break
            self._apply_status(snapshot)
        self.window.after(180, self._poll_status)

    def _schedule_status_refresh(self) -> None:
        if self.status_supplier is None:
            return
        threading.Thread(target=self._load_status_snapshot, daemon=True).start()

    def _load_status_snapshot(self) -> None:
        try:
            snapshot = self.status_supplier()
        except Exception as exc:  # pragma: no cover
            snapshot = {"llm": {"ok": False, "error": str(exc)}, "semantic_memory": {"ok": False}, "shortcut_catalog_entries": 0}
        self.status_queue.put(snapshot)

    def _poll_voice_results(self) -> None:
        while True:
            try:
                result = self.voice_queue.get_nowait()
            except queue.Empty:
                break
            self.voice_capture_active = False
            if result.get("ok") and str(result.get("text", "")).strip():
                text = str(result.get("text", "")).strip()
                current = self.input_var.get().strip()
                combined = f"{current} {text}".strip() if current else text
                self.input_var.set(combined)
                self.entry.focus_set()
                self.entry.icursor("end")
                self.status_line.configure(text="dictation ready", fg="#76D7C4")
                self._append_line("system", f"voice> {text}")
                continue
            message = str(result.get("message", "Не удалось распознать речь")).strip() or "Не удалось распознать речь"
            self.status_line.configure(text="voice idle", fg="#F7B267")
            self._append_line("system", f"voice> {message}")
        self.window.after(140, self._poll_voice_results)

    def _append_line(self, speaker: str, text: str) -> str:
        start_index = self.transcript.index("end-1c")
        label_tag = "assistant_label" if speaker == "assistant" else "user_label" if speaker == "you" else "meta"
        text_tag = "assistant_text" if speaker == "assistant" else "user_text" if speaker == "you" else "system_text"
        self.transcript.insert("end", f"{speaker}> ", (label_tag,))
        self.transcript.insert("end", f"{text}\n", (text_tag,))
        self.transcript.see("end")
        return start_index

    def _replace_last_assistant_line(self, text: str) -> None:
        content = self.transcript.get("1.0", "end-1c").splitlines()
        if content and content[-1] == "assistant> ...":
            content[-1] = f"assistant> {text}"
            self.transcript.delete("1.0", "end")
            for line in content:
                if line.startswith("assistant> "):
                    self.transcript.insert("end", "assistant> ", ("assistant_label",))
                    self.transcript.insert("end", line[len("assistant> ") :] + "\n", ("assistant_text",))
                elif line.startswith("you> "):
                    self.transcript.insert("end", "you> ", ("user_label",))
                    self.transcript.insert("end", line[len("you> ") :] + "\n", ("user_text",))
                else:
                    self.transcript.insert("end", line + "\n", ("system_text",))
        else:
            self.transcript.insert("end", "assistant> ", ("assistant_label",))
            self.transcript.insert("end", f"{text}\n", ("assistant_text",))
        self.transcript.see("end")

    def _center_window(self, width: int, height: int) -> None:
        self.window.update_idletasks()
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = int(screen_height * 0.18)
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def _make_chip(self, parent: tk.Misc, label: str, value: str, bg: str, fg: str) -> tk.Label:
        chip = tk.Label(
            parent,
            text=f"{label}  {value}",
            bg=bg,
            fg=fg,
            padx=12,
            pady=8,
            font=("Bahnschrift", 10, "bold"),
        )
        chip.pack(side="left", padx=(0, 8))
        return chip

    def _apply_status(self, snapshot: dict[str, Any]) -> None:
        llm = snapshot.get("llm", {})
        llm_ok = bool(llm.get("ok", False)) if isinstance(llm, dict) else False
        llm_backend = llm.get("backend", "llm") if isinstance(llm, dict) else "llm"
        self.llm_chip.configure(
            text=f"LLM  {llm_backend}",
            bg="#193329" if llm_ok else "#4A1F23",
            fg="#C8F7D2" if llm_ok else "#FFD6DB",
        )
        memory = snapshot.get("semantic_memory", {})
        memory_ok = bool(memory.get("ok", False)) if isinstance(memory, dict) else False
        points = memory.get("points_count", "n/a") if isinstance(memory, dict) else "n/a"
        self.memory_chip.configure(
            text=f"Memory  {points}",
            bg="#2B213A" if memory_ok else "#4A1F23",
            fg="#E6D9FF" if memory_ok else "#FFD6DB",
        )
        shortcuts = snapshot.get("shortcut_catalog_entries", 0)
        self.shortcuts_chip.configure(text=f"Shortcuts  {shortcuts}")
        stt = snapshot.get("stt", {})
        stt_ok = bool(stt.get("ok", False)) if isinstance(stt, dict) else False
        stt_backend = stt.get("backend", "voice") if isinstance(stt, dict) else "voice"
        if isinstance(stt, dict) and stt.get("implicit"):
            stt_backend = f"{stt_backend}*"
        self.voice_chip.configure(
            text=f"Voice  {stt_backend}",
            bg="#193329" if stt_ok else "#4A1F23",
            fg="#C8F7D2" if stt_ok else "#FFD6DB",
        )

    def _update_actions(self, result: dict[str, Any]) -> None:
        executed = result.get("executed_commands", [])
        if not isinstance(executed, list):
            executed = []
        self.action_list.delete(0, "end")
        if not executed:
            self.action_list.insert("end", "Ответ без внешних действий")
            return
        for item in executed[:8]:
            if not isinstance(item, dict):
                continue
            action = str(item.get("action", "action")).strip()
            status = "ok" if item.get("ok") else "fail"
            message = str(item.get("message", "")).strip()
            line = f"[{status}] {action}"
            if message:
                line += f" | {message}"
            self.action_list.insert("end", line)

    def _update_suggestions(self, result: dict[str, Any]) -> None:
        suggestions = result.get("suggested_shortcuts", [])
        if not isinstance(suggestions, list) or not suggestions:
            self._clear_suggestion_buttons()
            return
        self._clear_suggestion_buttons(keep_visible=True)
        for item in suggestions[:5]:
            if not isinstance(item, dict):
                continue
            display_name = str(item.get("display_name", "")).strip()
            if not display_name:
                continue
            button = ttk.Button(
                self.suggestion_buttons_row,
                text=display_name[:28],
                command=lambda value=display_name: self._submit_prompt(f"открой {value}"),
                style="Ghost.TButton",
            )
            button.pack(side="left", padx=(0, 8))
            self.suggestion_buttons.append(button)
        if self.suggestion_buttons:
            self.suggestion_card.grid()
        else:
            self.suggestion_card.grid_remove()

    def _clear_suggestion_buttons(self, keep_visible: bool = False) -> None:
        for button in self.suggestion_buttons:
            button.destroy()
        self.suggestion_buttons.clear()
        if not keep_visible:
            self.suggestion_card.grid_remove()

    def _inject_prompt(self, prompt: str) -> None:
        self.input_var.set(prompt)
        self.entry.focus_set()

    def _submit_prompt(self, prompt: str) -> None:
        self.input_var.set(prompt)
        self.entry.focus_set()
        self._submit()

    def _clear_transcript(self) -> None:
        self.transcript.delete("1.0", "end")
        self.action_list.delete(0, "end")
        self._clear_suggestion_buttons()
        self._append_line("assistant", "История очищена. Готов к следующему запросу.")

    def _start_voice_capture(self) -> str:
        if self.voice_input_handler is None:
            self.status_line.configure(text="voice unavailable", fg="#F7B267")
            self._append_line("system", "voice> Голосовой ввод недоступен.")
            return "break"
        if self.voice_capture_active:
            return "break"
        self.voice_capture_active = True
        self.status_line.configure(text="listening...", fg="#F7B267")
        threading.Thread(target=self._run_voice_capture, daemon=True).start()
        return "break"

    def _run_voice_capture(self) -> None:
        try:
            result = self.voice_input_handler()
        except Exception as exc:  # pragma: no cover
            result = {"ok": False, "message": str(exc)}
        self.voice_queue.put(result)

    def toggle_compact_mode(self) -> None:
        self.compact_mode = not self.compact_mode
        self._apply_compact_mode()

    def _apply_compact_mode(self) -> None:
        if self.compact_mode:
            self.chips.grid_remove()
            self.side_panel.grid_remove()
            self.subtitle_label.pack_forget()
            self.mode_chip.configure(text="Mode  focus")
            if self.window.state() != "withdrawn":
                self.window.geometry(self._resized_geometry(760, 420))
        else:
            self.chips.grid()
            self.side_panel.grid()
            if not self.subtitle_label.winfo_ismapped():
                self.subtitle_label.pack(anchor="w", pady=(2, 0))
            self.mode_chip.configure(text="Mode  overlay")
            if self.window.state() != "withdrawn":
                self.window.geometry(self._resized_geometry(980, 680))
        self._queue_state_save()

    def _bind_drag(self, widget: tk.Misc) -> None:
        widget.bind("<ButtonPress-1>", self._start_drag)
        widget.bind("<B1-Motion>", self._perform_drag)

    def _start_drag(self, event: tk.Event[tk.Misc]) -> None:
        self.drag_origin_x = event.x_root - self.window.winfo_x()
        self.drag_origin_y = event.y_root - self.window.winfo_y()

    def _perform_drag(self, event: tk.Event[tk.Misc]) -> None:
        x = event.x_root - self.drag_origin_x
        y = event.y_root - self.drag_origin_y
        self.window.geometry(f"+{x}+{y}")

    def _block_transcript_edit(self, event: tk.Event[tk.Misc]) -> str | None:
        allowed = {"Left", "Right", "Up", "Down", "Prior", "Next", "Home", "End"}
        if event.keysym in allowed:
            return None
        if (event.state & 0x4) and event.keysym.lower() in {"c", "a", "с", "ф"}:
            return None
        return "break"

    def _copy_transcript_selection(self, _event: tk.Event[tk.Misc]) -> str | None:
        try:
            selected = self.transcript.get("sel.first", "sel.last")
        except tk.TclError:
            return "break"
        self.window.clipboard_clear()
        self.window.clipboard_append(selected)
        return "break"

    def _select_all_transcript(self, _event: tk.Event[tk.Misc]) -> str | None:
        self.transcript.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _hide_shortcut(self, _event: tk.Event[tk.Misc] | None = None) -> str:
        self.hide()
        return "break"

    def _toggle_focus_shortcut(self, _event: tk.Event[tk.Misc] | None = None) -> str:
        self.toggle_compact_mode()
        return "break"

    def _resize_window(self, delta_width: int, delta_height: int) -> str:
        self.window.update_idletasks()
        width = max(560, self.window.winfo_width() + delta_width)
        height = max(320, self.window.winfo_height() + delta_height)
        x = self.window.winfo_x()
        y = self.window.winfo_y()
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self._queue_state_save()
        return "break"

    def _resized_geometry(self, width: int, height: int) -> str:
        x = self.window.winfo_x()
        y = self.window.winfo_y()
        if x <= 0 and y <= 0:
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()
            x = (screen_width - width) // 2
            y = int(screen_height * 0.18)
        return f"{width}x{height}+{x}+{y}"

    def _handle_control_keypress(self, event: tk.Event[tk.Misc]) -> str | None:
        keycode = int(getattr(event, "keycode", 0) or 0)
        key = (getattr(event, "keysym", "") or "").lower()
        if keycode in {49, 97} or key == "1":
            return self._hide_shortcut(event)
        if keycode in {50, 98} or key == "2":
            return self._toggle_focus_shortcut(event)
        if keycode in {51, 99} or key == "3":
            self._clear_transcript()
            return "break"
        if keycode in {52, 100} or key == "4":
            return self._start_voice_capture()
        return None

    def _show_transcript_menu(self, event: tk.Event[tk.Misc]) -> str:
        try:
            self.transcript_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.transcript_menu.grab_release()
        return "break"

    def _copy_transcript_selection_command(self) -> None:
        self._copy_transcript_selection(None)

    def _select_all_transcript_command(self) -> None:
        self._select_all_transcript(None)

    def _show_shortcuts_tooltip(self, event: tk.Event[tk.Misc]) -> None:
        if self._tooltip_window is not None:
            return
        tooltip = tk.Toplevel(self.window)
        tooltip.overrideredirect(True)
        tooltip.attributes("-topmost", True)
        tooltip.configure(bg="#1A2430")
        label = tk.Label(
            tooltip,
            text=(
                "Ctrl+1  hide window\n"
                "Ctrl+2  focus/overlay\n"
                "Ctrl+3  clear chat\n"
                "Ctrl+4  dictate into input field\n"
                "Ctrl+Arrows  resize window\n"
                "Right click on transcript  copy/select all\n"
                "Esc  hide window"
            ),
            justify="left",
            bg="#1A2430",
            fg="#EAF1F7",
            padx=12,
            pady=10,
            font=("Bahnschrift", 10),
        )
        label.pack()
        tooltip.geometry(f"+{event.x_root + 8}+{event.y_root + 18}")
        self._tooltip_window = tooltip

    def _hide_shortcuts_tooltip(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        if self._tooltip_window is None:
            return
        self._tooltip_window.destroy()
        self._tooltip_window = None

    def _on_window_configure(self, _event: tk.Event[tk.Misc]) -> None:
        if self.window.state() == "withdrawn":
            return
        self._queue_state_save()

    def _queue_state_save(self) -> None:
        if self.state_path is None:
            return
        if self._save_state_job is not None:
            self.window.after_cancel(self._save_state_job)
        self._save_state_job = self.window.after(180, self._save_window_state)

    def _save_window_state(self) -> None:
        if self.state_path is None:
            return
        self._save_state_job = None
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "compact_mode": self.compact_mode,
            "width": int(self.window.winfo_width()),
            "height": int(self.window.winfo_height()),
            "x": int(self.window.winfo_x()),
            "y": int(self.window.winfo_y()),
        }
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.window_state = payload

    def _load_window_state(self) -> dict[str, Any]:
        if self.state_path is None or not self.state_path.exists():
            return {}
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(raw, dict):
            return {}
        return raw

    def _apply_saved_geometry(self) -> None:
        width = int(self.window_state.get("width", 760 if self.compact_mode else 980))
        height = int(self.window_state.get("height", 420 if self.compact_mode else 680))
        x = self.window_state.get("x")
        y = self.window_state.get("y")
        if isinstance(x, int) and isinstance(y, int):
            self.window.geometry(f"{width}x{height}+{x}+{y}")
        else:
            self._center_window(width=width, height=height)
