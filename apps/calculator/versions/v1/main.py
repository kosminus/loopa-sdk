from __future__ import annotations

import ast
import operator
import os
import tkinter as tk
from pathlib import Path

from forge.artifact.chat import read_status, send_task


APP_VERSION = Path(__file__).resolve().parent.name

BUTTON_LAYOUT = [
    ["7", "8", "9", "/"],
    ["4", "5", "6", "*"],
    ["1", "2", "3", "-"],
    ["C", "0", ".", "+"],
    ["="],
]


class SafeEvaluator:
    BINARY_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
    }

    UNARY_OPERATORS = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def evaluate(self, expression: str) -> float:
        if not expression.strip():
            raise ValueError("Enter an expression first.")
        parsed = ast.parse(expression, mode="eval")
        return self._eval_node(parsed.body)

    def _eval_node(self, node: ast.AST) -> float:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ValueError("Only numbers are allowed.")
            return node.value

        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in self.BINARY_OPERATORS:
                raise ValueError("Unsupported operator.")
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return self.BINARY_OPERATORS[op_type](left, right)

        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in self.UNARY_OPERATORS:
                raise ValueError("Unsupported operator.")
            return self.UNARY_OPERATORS[op_type](self._eval_node(node.operand))

        raise ValueError("Unsupported expression.")


class CalculatorApp:
    def __init__(self) -> None:
        self.evaluator = SafeEvaluator()
        self.root = tk.Tk()
        self.apply_window_identity()
        self.expression = tk.StringVar()
        self.display_value = tk.StringVar(value="0")
        self.status = tk.StringVar(value=f"ready: {APP_VERSION}")
        self.chat_notice = tk.StringVar(value="")
        self.colors = {
            "bg": "#202124",
            "panel": "#f8fafc",
            "panel_dark": "#111827",
            "text": "#111827",
            "text_light": "#f9fafb",
            "muted": "#9ca3af",
            "button": "#38a169", # Changed to green
            "button_active": "#2f8554", # Darker green for hover
            "accent": "#38a169", # Changed to green
            "accent_active": "#2f8554", # Darker green for hover
            "danger": "#fb7185",
        }

    def run(self) -> int:
        self.apply_window_identity()
        self.root.geometry("420x620")
        self.root.minsize(360, 560)
        self.root.configure(bg=self.colors["bg"])
        self.build_ui()
        self.poll_status()
        self.log_startup()
        self.root.mainloop()
        return 0

    def apply_window_identity(self) -> None:
        title = f"Forge Calculator {APP_VERSION}"
        self.root.title(title)
        self.root.wm_title(title)
        try:
            self.root.tk.call("tk", "appname", title)
            self.root.tk.call("wm", "title", ".", title)
        except tk.TclError:
            pass

    def build_ui(self) -> None:
        app_frame = tk.Frame(self.root, bg=self.colors["bg"])
        app_frame.pack(fill=tk.BOTH, expand=True)

        header_frame = tk.Frame(app_frame, bg=self.colors["bg"])
        header_frame.pack(fill=tk.X, padx=14, pady=(12, 6))

        status_label = tk.Label(
            header_frame,
            textvariable=self.status,
            bg=self.colors["bg"],
            fg=self.colors["muted"],
            anchor="w",
            font=("TkDefaultFont", 12),
        )
        status_label.pack(fill=tk.X)

        version_label = tk.Label(
            header_frame,
            text=f"running {APP_VERSION} from {Path(__file__).name}",
            bg=self.colors["bg"],
            fg=self.colors["muted"],
            anchor="w",
            font=("TkDefaultFont", 10),
        )
        version_label.pack(fill=tk.X, pady=(2, 0))

        display_label = tk.Label(
            app_frame,
            textvariable=self.display_value,
            bg=self.colors["panel_dark"],
            fg=self.colors["text_light"],
            anchor="e",
            font=("TkDefaultFont", 34, "bold"),
            padx=16,
            pady=18,
            relief=tk.SOLID,
            bd=1,
        )
        display_label.pack(fill=tk.X, padx=14, pady=(0, 12))
        self.expression.trace_add("write", lambda *_args: self.refresh_display())
        self.root.bind("<Key>", self.handle_keypress)

        buttons_frame = tk.Frame(app_frame, bg=self.colors["bg"])
        buttons_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 12))
        for column in range(4):
            buttons_frame.columnconfigure(column, weight=1, uniform="button")

        for row_index, row in enumerate(BUTTON_LAYOUT):
            buttons_frame.rowconfigure(row_index, weight=1, uniform="button")
            if len(row) == 1:
                button = self.make_button(
                    buttons_frame,
                    row[0],
                    command=lambda label=row[0]: self.handle_button(label),
                    accent=True,
                )
                button.grid(row=row_index, column=0, columnspan=4, sticky="nsew", padx=3, pady=3)
                continue

            for column_index, label in enumerate(row):
                button = self.make_button(
                    buttons_frame,
                    label,
                    command=lambda value=label: self.handle_button(value),
                    danger=label == "C",
                )
                button.grid(row=row_index, column=column_index, sticky="nsew", padx=3, pady=3)

        bottom_frame = tk.Frame(app_frame, bg=self.colors["bg"])
        bottom_frame.pack(fill=tk.X, padx=14, pady=(0, 14))
        bottom_frame.columnconfigure(0, weight=1)

        chat_label = tk.Label(
            bottom_frame,
            text="Ask Forge for any change (history, units, themes, new buttons...)",
            bg=self.colors["bg"],
            fg=self.colors["text_light"],
            anchor="w",
            font=("TkDefaultFont", 13, "bold"),
        )
        chat_label.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        chat_frame = tk.Frame(bottom_frame, bg="#60a5fa", padx=2, pady=2)
        chat_frame.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        chat_frame.columnconfigure(0, weight=1)

        chat_entry = tk.Text(
            chat_frame,
            bg=self.colors["panel"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"],
            relief=tk.FLAT,
            bd=0,
            height=3,
            width=24,
            wrap=tk.WORD,
            font=("TkDefaultFont", 13),
        )
        chat_entry.grid(row=0, column=0, sticky="ew")
        chat_entry.bind("<Return>", lambda event: self.submit_chat(chat_entry, event))

        send_button = self.make_button(
            bottom_frame,
            "Send",
            command=lambda: self.submit_chat(chat_entry),
            accent=True,
        )
        send_button.grid(row=1, column=1, sticky="nsew")

        chat_notice = tk.Label(
            bottom_frame,
            textvariable=self.chat_notice,
            bg=self.colors["bg"],
            fg=self.colors["muted"],
            anchor="w",
            font=("TkDefaultFont", 11),
        )
        chat_notice.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def make_button(
        self,
        parent: tk.Widget,
        label: str,
        command,
        accent: bool = False,
        danger: bool = False,
    ) -> tk.Button:
        background = self.colors["button"]
        active_background = self.colors["button_active"]
        foreground = self.colors["text"]
        if accent:
            background = self.colors["accent"]
            active_background = self.colors["accent_active"]
            foreground = "#ffffff"
        if danger:
            foreground = self.colors["danger"]

        return tk.Button(
            parent,
            text=label,
            command=command,
            bg=background,
            activebackground=active_background,
            fg=foreground,
            activeforeground=foreground,
            relief=tk.FLAT,
            bd=0,
            font=("TkDefaultFont", 16),
            highlightthickness=0,
            padx=8,
            pady=10,
        )

    def handle_keypress(self, event) -> None:
        if isinstance(event.widget, tk.Text):
            return
        if event.keysym in {"Return", "KP_Enter"}:
            self.calculate()
        elif event.keysym == "BackSpace":
            self.expression.set(self.expression.get()[:-1])
        elif event.keysym == "Escape":
            self.expression.set("")
        elif event.char in "0123456789.+-*/":
            self.expression.set(self.expression.get() + event.char)

    def handle_button(self, label: str) -> None:
        if label == "C":
            self.expression.set("")
        elif label == "=":
            self.calculate()
        elif label in "0123456789.+-*/":
            self.expression.set(self.expression.get() + label)
        else:
            self.chat_notice.set(f"Unknown button: {label}")

    def calculate(self) -> None:
        try:
            result = self.evaluator.evaluate(self.expression.get())
        except Exception as exc:
            self.expression.set("Error")
            self.chat_notice.set(str(exc))
            return
        self.expression.set(self.format_number(result))
        self.chat_notice.set("")

    def submit_chat(self, chat_entry: tk.Text, event=None):
        if event is not None and event.state & 0x0001:
            return None

        task = chat_entry.get("1.0", tk.END).strip()
        if not task:
            return "break"

        try:
            send_task(task)
        except Exception as exc:
            self.chat_notice.set(str(exc))
            return "break"

        chat_entry.delete("1.0", tk.END)
        self.chat_notice.set("Task sent to supervisor.")
        return "break"

    def poll_status(self) -> None:
        status = read_status()
        self.status.set(status.get("message", "status unavailable"))
        self.root.after(500, self.poll_status)

    def refresh_display(self) -> None:
        text = self.expression.get() or "0"
        self.display_value.set(text[-28:])

    def log_startup(self) -> None:
        log_path = os.environ.get("FORGE_ARTIFACT_LOG")
        if not log_path:
            return
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(f"started Forge Calculator {APP_VERSION} from {Path(__file__).resolve()}\n")

    def format_number(self, value: float) -> str:
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)


def main() -> int:
    return CalculatorApp().run()


if __name__ == "__main__":
    raise SystemExit(main())
