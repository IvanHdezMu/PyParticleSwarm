"""Desktop batch editor. All solver execution runs in a separate process."""
from dataclasses import replace
from itertools import product
from pathlib import Path
import signal
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from tools.dataset_generators.gui import ThemedDropdown
from ..experiments.experiment_config import ExperimentConfiguration, RepetitionSpec, is_parameter_active
from ..infrastructure.experiment_options import ROOT
from ..experiments.experiment_batch import load_catalog, load_presets
from .experiment_editor import NUMERIC_FIELDS, OPERATOR_LABELS, add_numeric, parse_numeric, remove_value, toggle_value, review
from ..experiments.batch_store import create_batch, batch_status, finish_batch
from ..experiments.experiment_process import BatchProcess


FIELD_HELP = {
    'c1': 'Search budget multiplier. The effective budget scales with the number of nodes.',
    'k': 'Size of the route segment used by k-based operators.',
    'primary_operator_share': 'Fraction of particles assigned to the primary operator in mixed modes. 0.2 = 20%.',
    'minimum_reset_probability': 'Probability in [0, 1]. 0.2 = 20%.',
    'maximum_reset_probability': 'Probability in [0, 1]. 0.2 = 20%.',
    'reset_threshold_divisor': 'Controls the threshold used by the permutation-reset logic.',
    'progress_warmup_multiplier': 'Controls when periodic progress/history recording begins relative to problem size.',
}


class NumericValues(ctk.CTkFrame):
    """Free numeric entry plus ordered removable values; no numeric choices."""
    def __init__(self, master, field, owner):
        super().__init__(master, fg_color='transparent')
        self.field, self.owner = field, owner
        self.active = True
        self.grid_columnconfigure(0, weight=1)
        self.label = ctk.CTkLabel(self, text=NUMERIC_FIELDS[field][0], anchor='w')
        self.label.grid(row=0, column=0, columnspan=2, sticky='ew')
        self.text = tk.StringVar()
        self.entry = ctk.CTkEntry(self, textvariable=self.text, height=36, placeholder_text='Enter a value')
        self.entry.grid(row=1, column=0, sticky='ew', padx=(0,8))
        self.add_button = ctk.CTkButton(self, text='Add', width=64, height=36, command=self.add)
        self.add_button.grid(row=1, column=1)
        self.chips = ctk.CTkFrame(self, fg_color='transparent')
        self.chips.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(6,10))
        if field in FIELD_HELP:
            self.help_label = ctk.CTkLabel(self, text=FIELD_HELP[field], anchor='w', justify='left',
                                         font=ctk.CTkFont(size=12), wraplength=300)
            self.help_label.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(0,10))
            self.bind('<Configure>', lambda event: self.help_label.configure(wraplength=max(100, event.width-8)))
        self.entry.bind('<Return>', lambda event: self.add())
        self.text.trace_add('write', lambda *args: self.owner.refresh_review())

    def add(self):
        try:
            updated = add_numeric(self.owner.configuration, self.field, self.text.get())
        except ValueError as error:
            self.owner.status.configure(text=str(error))
            return
        self.owner.configuration = updated
        self.text.set('')
        self.owner.refresh()

    def remove(self, value):
        try:
            self.owner.configuration = remove_value(self.owner.configuration, self.field, value)
        except ValueError:
            self.owner.status.configure(text='Keep at least one value. Add its replacement before removing it.')
            return
        self.owner.refresh()

    def render(self, active):
        self.active = active
        state = 'normal' if active else 'disabled'
        self.entry.configure(state=state)
        self.add_button.configure(state=state)
        for child in self.chips.winfo_children():
            child.destroy()
        for i, value in enumerate(getattr(self.owner.configuration, self.field)):
            ctk.CTkButton(self.chips, text=f'{value} ×', width=75, height=28, state=state,
                          command=lambda v=value: self.remove(v)).grid(row=i//4, column=i%4, padx=(0,6), pady=3)


class ExperimentRunnerApp(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode('System')
        ctk.set_default_color_theme('blue')
        super().__init__()
        self.title('PyParticleSwarm Experiment Runner')
        self.geometry('1000x900')
        self.minsize(760, 650)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.catalog = load_catalog()
        self.presets = load_presets()
        self.configuration = ExperimentConfiguration(datasets=(self.catalog[0].id,))
        self.numeric = {}
        self.choice_controls = []
        self.scalar_entries = {}
        self.scalar_rows = {}
        self.advanced_open = False
        self.process = None
        self.batch_directory = None
        self.closing = False
        self._building = True
        self.interrupt_requested = False
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.grid(row=0, column=0, sticky='ew', padx=28, pady=(20,12))
        ctk.CTkLabel(header, text='PyParticleSwarm', font=ctk.CTkFont(size=12)).pack(anchor='w')
        ctk.CTkLabel(header, text='Experiment Runner', font=ctk.CTkFont(size=28, weight='bold')).pack(anchor='w')
        ctk.CTkLabel(header, text='Build a batch from your own values, or start with an editable preset.').pack(anchor='w')
        self.form = ctk.CTkScrollableFrame(self, fg_color='transparent')
        self.form.grid(row=1, column=0, sticky='nsew', padx=20)
        self.form.grid_columnconfigure(0, weight=1)
        self.bind('<Button-4>', lambda event: self.scroll_form(event, -1), add='+')
        self.bind('<Button-5>', lambda event: self.scroll_form(event, 1), add='+')
        self._card_row = 0
        card = self.card('Preset')
        self.preset = ThemedDropdown(card, values=['Custom configuration'] + [p.name for p in self.presets],
                                     command=self.select_preset)
        self.preset.set('Custom configuration')
        self.preset.pack(fill='x', padx=18, pady=(0,16))
        card = self.card('Dataset')
        self.source_filter = ThemedDropdown(card, values=['All sources'] + list(dict.fromkeys(d.source for d in self.catalog)),
                                            command=lambda value: self.filter_datasets())
        self.source_filter.set('All sources')
        self.source_filter.pack(fill='x', padx=18, pady=(0,8))
        self.dataset_selector = ThemedDropdown(card, values=[d.id for d in self.catalog],
                                                command=self.select_dataset)
        self.dataset_selector.pack(fill='x', padx=18, pady=(0,8))
        ctk.CTkLabel(card, text='Problem type', anchor='w').pack(fill='x', padx=18)
        self.problem_selector = ThemedDropdown(card, values=['TSP'], command=self.select_problem)
        self.problem_selector.pack(fill='x', padx=18, pady=(0,16))
        card = self.card('Algorithm')
        self.numeric_rows(card, ('particles','c1'))
        self.choices(card, 'Operators', 'operators', list(OPERATOR_LABELS.items()), columns=2)
        self.numeric_rows(card, ('k','primary_operator_share'))
        self.choices(card, 'Ring — return to the first node', 'ring', [(False,'Off'),(True,'On')])
        self.choices(card, 'Permutation reset', 'permutation_reset', [(False,'Off'),(True,'On')])
        self.numeric_rows(card, ('minimum_reset_probability','maximum_reset_probability'))
        self.refuel_card = self.card('Refuel')
        self.fuel_capacity_var = tk.StringVar(value=str(self.configuration.fuel_capacity[0]))
        self.consumption_var = tk.StringVar(value=str(self.configuration.consumption[0]))
        self.scalar_row(self.refuel_card, 'fuel_capacity', 'Fuel capacity (L)', self.fuel_capacity_var)
        self.scalar_row(self.refuel_card, 'consumption', 'Fuel efficiency (km/L)', self.consumption_var)
        self.choices(self.refuel_card, 'Initial tank', 'full_initial_tank', [(False,'Empty'),(True,'Full')])
        card = self.card('Execution')
        self.name_var = tk.StringVar(value=self.configuration.name)
        self.count_var = tk.StringVar(value='1')
        self.first_var = tk.StringVar(value='1')
        self.output_var = tk.StringVar(value=str(self.configuration.output_dir))
        self.verbose_var = tk.BooleanVar(value=False)
        self.excel_var = tk.BooleanVar(value=True)
        self.scalar_row(card, 'name', 'Batch name', self.name_var)
        self.scalar_row(card, 'repetitions', 'Repetitions', self.count_var)
        ctk.CTkCheckBox(card, text='Verbose console output (saved in execution.log)', variable=self.verbose_var,
                        command=self.refresh).pack(anchor='w', padx=18,pady=6)
        ctk.CTkCheckBox(card, text='Save Excel result histories', variable=self.excel_var,
                        command=self.refresh).pack(anchor='w', padx=18,pady=6)
        advanced_card = self.card('Advanced settings')
        self.advanced_toggle = ctk.CTkButton(advanced_card, text='Show settings', command=self.toggle_advanced)
        self.advanced_toggle.pack(anchor='w', padx=18, pady=(0,12))
        self.advanced_content = ctk.CTkFrame(advanced_card, fg_color='transparent')
        self.numeric_rows(self.advanced_content, ('reset_threshold_divisor','progress_warmup_multiplier'))
        self.scalar_row(self.advanced_content, 'first_id', 'First repetition ID', self.first_var,
                        'Starting label used for repetition numbering. It is not a random seed.')
        self.scalar_row(self.advanced_content, 'output_dir', 'Output directory', self.output_var)
        ctk.CTkButton(self.advanced_content, text='Browse output…', command=self.choose_output,
                      height=32).pack(anchor='e', padx=18, pady=(6,12))
        footer = ctk.CTkFrame(self, corner_radius=12)
        footer.grid(row=2,column=0,sticky='ew',padx=28,pady=(12,20))
        self.count_label = ctk.CTkLabel(footer, text='', font=ctk.CTkFont(size=18,weight='bold'))
        self.count_label.pack(anchor='w',padx=18,pady=(12,4))
        self.status = ctk.CTkLabel(footer,text='',anchor='w',justify='left',wraplength=860)
        self.status.pack(fill='x',padx=18,pady=(0,8))
        self.run_button = ctk.CTkButton(footer,text='Run batch',height=42,command=self.launch)
        self.run_button.pack(fill='x',padx=18,pady=(0,16))
        for variable in (self.name_var,self.count_var,self.first_var,self.output_var,
                         self.fuel_capacity_var,self.consumption_var):
            variable.trace_add('write',lambda *args: self.refresh_review())
        self._building = False
        self.refresh()
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.after(300,self.poll_execution)

    def scalar_row(self, parent, field, label, variable, help_text=None):
        row = ctk.CTkFrame(parent, fg_color='transparent')
        row.pack(fill='x', padx=18, pady=5)
        ctk.CTkLabel(row, text=label, anchor='w', width=235).pack(side='left')
        entry = ctk.CTkEntry(row, textvariable=variable, height=36)
        entry.pack(side='left', fill='x', expand=True)
        self.scalar_entries[field] = entry
        self.scalar_rows[field] = row
        if help_text:
            ctk.CTkLabel(parent, text=help_text, anchor='w', justify='left', wraplength=650,
                         font=ctk.CTkFont(size=12)).pack(fill='x', padx=18, pady=(0,8))

    def toggle_advanced(self):
        self.advanced_open = not self.advanced_open
        if self.advanced_open:
            self.advanced_content.pack(fill='x')
        else:
            self.advanced_content.pack_forget()
        self.advanced_toggle.configure(text='Hide settings' if self.advanced_open else 'Show settings')

    def select_dataset(self, name):
        descriptor = next(d for d in self.catalog if d.id == name)
        mode = self.configuration.problem_modes[0]
        if mode not in descriptor.problem_types:
            mode = descriptor.problem_types[0]
        self.configuration = replace(self.configuration, datasets=(name,), problem_modes=(mode,))
        self.refresh()

    def select_problem(self, label):
        mode = label.lower()
        descriptor = next(d for d in self.catalog if d.id == self.configuration.datasets[0])
        if mode not in descriptor.problem_types:
            return
        self.configuration = replace(self.configuration, problem_modes=(mode,))
        self.refresh()

    def scroll_form(self, event, direction):
        if self.form.check_if_master_is_canvas(event.widget):
            self.form._parent_canvas.yview_scroll(direction * 3, 'units')

    def card(self, title):
        card = ctk.CTkFrame(self.form,corner_radius=12)
        card.grid(row=self._card_row,column=0,sticky='ew',pady=(0,14))
        self._card_row += 1
        ctk.CTkLabel(card,text=title,font=ctk.CTkFont(size=17,weight='bold')).pack(anchor='w',padx=18,pady=(12,10))
        return card

    def numeric_rows(self, card, fields):
        group = ctk.CTkFrame(card,fg_color='transparent')
        group.pack(fill='x',padx=18)
        group.grid_columnconfigure((0,1),weight=1,uniform='values')
        for i, field in enumerate(fields):
            widget = NumericValues(group,field,self)
            widget.grid(row=i//2,column=i%2,sticky='ew',padx=(0,12) if i%2==0 else (12,0))
            self.numeric[field] = widget

    def choices(self, card, label, field, choices, columns=3):
        ctk.CTkLabel(card,text=label,anchor='w').pack(fill='x',padx=18)
        group = ctk.CTkFrame(card,fg_color='transparent')
        group.pack(fill='x',padx=18,pady=(0,12))
        for i,(value,text) in enumerate(choices):
            var = tk.BooleanVar()
            button = ctk.CTkCheckBox(group,text=text,variable=var,
                                    command=lambda f=field,v=value: self.toggle(f,v))
            button.grid(row=i//columns,column=i%columns,sticky='w',padx=(0,18),pady=5)
            self.choice_controls.append((field,value,var,button))

    def field_active(self, field):
        c = self.configuration
        return any(is_parameter_active(field,problem_mode=m,operator=o,permutation_reset=r,
                                        verbose=self.verbose_var.get(),excel=self.excel_var.get())
                   for m,o,r in product(c.problem_modes,c.operators,c.permutation_reset))

    def refresh(self):
        if self._building:
            return
        for field,widget in self.numeric.items():
            active = self.field_active(field)
            widget.render(active)
            if active:
                widget.grid()
            else:
                widget.grid_remove()
        for field,value,var,button in self.choice_controls:
            var.set(value in getattr(self.configuration,field))
            button.configure(state='normal' if self.field_active(field) else 'disabled')
        descriptor = next(d for d in self.catalog if d.id == self.configuration.datasets[0])
        self.dataset_selector.set(descriptor.id)
        self.problem_selector.configure(values=[mode.upper() for mode in descriptor.problem_types])
        self.problem_selector.set(self.configuration.problem_modes[0].upper())
        if self.configuration.problem_modes == ('tspwr',):
            self.refuel_card.grid()
        else:
            self.refuel_card.grid_remove()
        self.refresh_review()

    def toggle(self, field, value):
        try:
            self.configuration = toggle_value(self.configuration,field,value)
        except ValueError:
            self.refresh()
            self.status.configure(text='Keep at least one selection in each required field.')
            return
        self.refresh()

    def filter_datasets(self):
        source = self.source_filter.get()
        datasets = [d.id for d in self.catalog if source == 'All sources' or d.source == source]
        self.dataset_selector.configure(values=datasets)
        if self.configuration.datasets[0] not in datasets:
            self.select_dataset(datasets[0])

    def select_preset(self, name):
        self._building = True
        self.configuration = (ExperimentConfiguration(datasets=(self.catalog[0].id,)) if name=='Custom configuration'
                              else next(p for p in self.presets if p.name==name))
        c = self.configuration
        for widget in self.numeric.values():
            widget.text.set('')
        self.fuel_capacity_var.set(str(c.fuel_capacity[0]))
        self.consumption_var.set(str(c.consumption[0]))
        self.name_var.set(c.name)
        self.count_var.set(str(c.repetitions.count))
        self.first_var.set(str(c.repetitions.first_id))
        self.output_var.set(str(c.output_dir))
        self.verbose_var.set(c.verbose)
        self.excel_var.set(c.excel)
        self.source_filter.set('All sources')
        self.filter_datasets()
        self._building = False
        self.refresh()

    def current_configuration(self):
        if not self.output_var.get().strip():
            raise ValueError('Choose an output directory')
        try:
            repeats = RepetitionSpec(int(self.count_var.get()),int(self.first_var.get()))
        except ValueError:
            raise ValueError('Repetition count and first ID must be positive integers') from None
        fuel = {}
        if self.configuration.problem_modes == ('tspwr',):
            fuel = dict(fuel_capacity=(parse_numeric('fuel_capacity', self.fuel_capacity_var.get()),),
                        consumption=(parse_numeric('consumption', self.consumption_var.get()),))
        return replace(self.configuration, **fuel, name=self.name_var.get(),repetitions=repeats,
                       verbose=self.verbose_var.get(),excel=self.excel_var.get(),output_dir=Path(self.output_var.get()))

    def validated_review(self):
        config = self.current_configuration()
        for field, widget in self.numeric.items():
            if widget.active and widget.text.get().strip():
                add_numeric(config, field, widget.text.get())
                raise ValueError(f'Add or clear the typed value for {NUMERIC_FIELDS[field][0]}.')
        output = config.output_dir.expanduser()
        if not output.is_absolute():
            output = ROOT / output
        if output.exists() and not output.is_dir():
            raise ValueError('Output path is a file, not a directory')
        return review(config, self.catalog)

    def refresh_review(self):
        if self._building or self.process is not None:
            return
        try:
            _, count, warnings = self.validated_review()
            self.count_label.configure(text=f'Planned runs: {count:,}')
            self.status.configure(text='\n'.join(warnings) or 'Ready. Each combination runs once per repetition.')
            self.run_button.configure(state='normal')
        except (ValueError,OSError) as error:
            self.count_label.configure(text='Planned runs: —')
            self.status.configure(text=str(error))
            self.run_button.configure(state='disabled')

    def choose_output(self):
        path = filedialog.askdirectory(parent=self,title='Choose batch output directory')
        if path:
            self.output_var.set(path)

    def launch(self):
        if self.process is not None:
            return
        try:
            plan,count,warnings = self.validated_review()
            config = plan.configuration
            if not messagebox.askyesno('Run batch',f'Run exactly {count:,} executions?\n\nOutput: {config.output_dir}\n\n'+ '\n'.join(warnings),parent=self):
                return
            self.batch_directory = create_batch(plan)
            try:
                self.process = BatchProcess(self.batch_directory)
            except Exception as error:
                finish_batch(self.batch_directory,'failed',str(error))
                raise
            self.run_button.configure(state='disabled')
            self.status.configure(text=f'Batch starting…\n{self.batch_directory}')
        except (ValueError,OSError) as error:
            self.status.configure(text=f'Could not launch: {error}')

    def poll_execution(self):
        if self.process is not None:
            if self.interrupt_requested:
                self.process.interrupt()
                self.interrupt_requested = False
            code = self.process.poll()
            state = batch_status(self.batch_directory)
            completed = sum(state['counts'][key] for key in ('succeeded','failed','interrupted'))
            current = state['current']
            text = f"{state['status'].capitalize()} — {completed:,} / {state['total']:,} finished"
            if current:
                text += f"\nRun {state['ordinal']}: {current['dataset']} · operator {current['operator']} · k {current['k']}"
            if state['error']:
                text += '\n'+state['error']
            self.status.configure(text=text+'\n'+str(self.batch_directory))
            if code is not None:
                self.process = None
                self.refresh_review()
                self.status.configure(text=text+'\n'+str(self.batch_directory))
                if self.closing:
                    self.destroy()
                    return
        elif self.interrupt_requested:
            self.destroy()
            return
        self.after(300,self.poll_execution)

    def close(self):
        if self.process is not None:
            if not messagebox.askyesno('Interrupt batch?', 'Interrupt the current run and close? Completed results will remain saved.',parent=self):
                return
            self.closing = True
            self.process.interrupt()
        else:
            self.destroy()


def main():
    app = ExperimentRunnerApp()
    previous = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT,lambda signum,frame: setattr(app,'interrupt_requested',True))
    try:
        app.mainloop()
    finally:
        signal.signal(signal.SIGINT,previous)
