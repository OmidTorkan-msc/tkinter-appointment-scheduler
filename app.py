# -*- coding: utf-8 -*-
"""
Gestore Appuntamenti (Tkinter)

What's included:
- Add / delete appointments
- Overlap (collision) detection with a user warning
- Auto-sort by start time
- Persist to / load from appointments.json
- Clear, testable structure and input validation
"""

import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from tkcalendar import DateEntry


# ------------------------ Domain model ------------------------

class Appuntamento:
    """Lightweight appointment entity."""

    def __init__(self, titolo: str, data_ora: datetime, durata_min: int):
        self.titolo = titolo.strip()
        self.data_ora = data_ora
        self.durata = int(durata_min)

    @property
    def fine(self) -> datetime:
        """Computed end datetime."""
        return self.data_ora + timedelta(minutes=self.durata)

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "titolo": self.titolo,
            "data_ora": self.data_ora.isoformat(),
            "durata": self.durata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Appuntamento":
        """Deserialize from dict."""
        return cls(
            d["titolo"],
            datetime.fromisoformat(d["data_ora"]),
            int(d["durata"]),
        )

    def __str__(self) -> str:
        start = self.data_ora.strftime("%d/%m %H:%M")
        end = self.fine.strftime("%H:%M")
        return f"{self.titolo} — {start} → {end} ({self.durata} min)"


# ------------------------ Application ------------------------

class GestoreAppuntamenti(tk.Tk):
    """Main window and controller."""

    SAVE_FILE = "appointments.json"

    def __init__(self):
        super().__init__()
        self.title("Gestore Appuntamenti")
        self.geometry("460x520")
        self.minsize(460, 520)

        self.appuntamenti: list[Appuntamento] = []

        self._build_ui()
        self._load()
        self._refresh_list()

        # Save gracefully on close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- UI ----------

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        # Form
        frm = ttk.LabelFrame(container, text="Aggiungi / Gestisci")
        frm.pack(fill=tk.X)

        ttk.Label(frm, text="Titolo:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.ent_title = ttk.Entry(frm, width=34)
        self.ent_title.grid(row=0, column=1, padx=6, pady=6, sticky="we", columnspan=2)

        ttk.Label(frm, text="Giorno:").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        self.cal_date = DateEntry(frm, date_pattern="dd/mm/yyyy", width=12)
        self.cal_date.grid(row=1, column=1, padx=6, pady=6, sticky="w")

        ttk.Label(frm, text="Ora Inizio:").grid(row=2, column=0, padx=6, pady=6, sticky="w")
        self.cmb_time = ttk.Combobox(frm, values=self._time_slots(), width=10, state="readonly")
        self.cmb_time.grid(row=2, column=1, padx=6, pady=6, sticky="w")

        ttk.Label(frm, text="Durata (minuti):").grid(row=3, column=0, padx=6, pady=6, sticky="w")
        self.ent_duration = ttk.Entry(frm, width=12)
        self.ent_duration.grid(row=3, column=1, padx=6, pady=6, sticky="w")

        # Buttons
        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=3, pady=(6, 10), sticky="we")
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)

        ttk.Button(btns, text="➕ Aggiungi Appuntamento",
                   command=self._add_appointment).grid(row=0, column=0, padx=4, sticky="we")
        ttk.Button(btns, text="🗑️ Cancella Selezionato",
                   command=self._delete_selected).grid(row=0, column=1, padx=4, sticky="we")

        # List
        lst_frame = ttk.LabelFrame(container, text="Appuntamenti (ordinati per inizio)")
        lst_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.lst = tk.Listbox(lst_frame, height=12)
        self.lst.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Scrollbar(lst_frame, command=self.lst.yview).pack(side=tk.RIGHT, fill=tk.Y)

        # Status bar
        self.status = ttk.Label(container, text="Pronto.", anchor="w")
        self.status.pack(fill=tk.X, pady=(8, 0))

    # ---------- Logic ----------

    @staticmethod
    def _time_slots(step_minutes: int = 30) -> list[str]:
        """Generate HH:MM options by step."""
        return [f"{h:02d}:{m:02d}" for h in range(24) for m in range(0, 60, step_minutes)]

    def _parse_form(self) -> Appuntamento | None:
        """Validate and convert form inputs into an Appuntamento."""
        title = self.ent_title.get().strip()
        time_str = self.cmb_time.get().strip()
        duration_str = self.ent_duration.get().strip()

        if not title or not time_str or not duration_str:
            messagebox.showerror("Errore", "Compila tutti i campi!")
            return None

        try:
            duration = int(duration_str)
            if duration <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Errore", "La durata deve essere un intero positivo.")
            return None

        try:
            # DateEntry returns a date; combine with selected time
            d = self.cal_date.get_date()
            hh, mm = map(int, time_str.split(":"))
            start_dt = datetime(d.year, d.month, d.day, hh, mm)
        except Exception:
            messagebox.showerror("Errore", "Formato data/ora non valido.")
            return None

        return Appuntamento(title, start_dt, duration)

    def _find_overlap(self, new_ap: Appuntamento) -> Appuntamento | None:
        """Return conflicting appointment if time windows overlap, else None."""
        for ap in self.appuntamenti:
            if (new_ap.data_ora < ap.fine) and (new_ap.fine > ap.data_ora):
                return ap
        return None

    def _add_appointment(self) -> None:
        ap = self._parse_form()
        if not ap:
            return

        # Overlap warning
        conflict = self._find_overlap(ap)
        if conflict:
            msg = (f"Questo appuntamento si sovrappone a:\n"
                   f"«{conflict.titolo} — {conflict.data_ora.strftime('%d/%m %H:%M')}».\n"
                   f"Vuoi aggiungerlo comunque?")
            if not messagebox.askyesno("Sovrapposizione", msg):
                self.status.config(text="Aggiunta annullata (sovrapposizione).")
                return

        self.appuntamenti.append(ap)
        self._refresh_list()
        self._clear_form()
        self._save()
        self.status.config(text="Appuntamento aggiunto.")

    def _delete_selected(self) -> None:
        sel = self.lst.curselection()
        if not sel:
            messagebox.showinfo("Info", "Seleziona un appuntamento da cancellare.")
            return
        idx = sel[0]
        ap = self.appuntamenti[idx]
        if messagebox.askyesno("Conferma", f"Cancellare «{ap.titolo}»?"):
            del self.appuntamenti[idx]
            self._refresh_list()
            self._save()
            self.status.config(text="Appuntamento cancellato.")

    def _refresh_list(self) -> None:
        """Sort list and refresh the UI listbox."""
        self.appuntamenti.sort(key=lambda a: a.data_ora)
        self.lst.delete(0, tk.END)
        for ap in self.appuntamenti:
            self.lst.insert(tk.END, str(ap))

    def _clear_form(self) -> None:
        self.ent_title.delete(0, tk.END)
        self.cmb_time.set("")
        self.ent_duration.delete(0, tk.END)

    # ---------- Persistence ----------

    def _save(self) -> None:
        try:
            data = [ap.to_dict() for ap in self.appuntamenti]
            with open(self.SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.status.config(text=f"Errore salvataggio: {e}")

    def _load(self) -> None:
        if not os.path.exists(self.SAVE_FILE):
            return
        try:
            with open(self.SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.appuntamenti = [Appuntamento.from_dict(d) for d in data]
        except Exception as e:
            messagebox.showwarning("Avviso", f"Impossibile caricare i dati:\n{e}")

    def _on_close(self) -> None:
        self._save()
        self.destroy()


if __name__ == "__main__":
    app = GestoreAppuntamenti()
    app.mainloop()
