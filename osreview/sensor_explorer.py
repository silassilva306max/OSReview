"""Frozen, independently scrollable sensor investigation window.

Captures the current in-memory snapshot only on user request; a background poll
never redraws tables or resets the selection/scroll position.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from osreview.services.sensor_triage import triage
from osreview.services.sensor_analysis import is_real_temperature


class SensorExplorer(tk.Toplevel):
    def __init__(self, master, data_provider):
        super().__init__(master)
        self.data_provider = data_provider
        self.title('OSReview — Explorador de sensores | leitura congelada')
        self.geometry('1130x720')
        self.minsize(780, 460)
        self.snapshot = {}
        self.configure(bg='#11151D')
        style=ttk.Style(self)
        style.configure('OSReviewSensors.Treeview',background='#1A2636',foreground='#E9F2FF',
                        fieldbackground='#1A2636',rowheight=26,font=('Segoe UI',10),borderwidth=0)
        style.configure('OSReviewSensors.Treeview.Heading',background='#27394E',foreground='#E9F2FF',
                        font=('Segoe UI',10,'bold'),relief='flat')
        style.map('OSReviewSensors.Treeview', background=[('selected','#365C82')],
                  foreground=[('selected','#FFFFFF')])
        style.configure('OSReviewSensors.TNotebook',background='#11151D')
        style.configure('OSReviewSensors.TNotebook.Tab',background='#243346',foreground='#DDEBFF',padding=(12,7))
        style.map('OSReviewSensors.TNotebook.Tab',background=[('selected','#345577')],foreground=[('selected','#FFFFFF')])
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        header = tk.Frame(self, bg='#11151D');header.pack(fill='x',padx=16,pady=(15,8))
        tk.Label(header,text='Explorador de sensores — instantâneo congelado',font=('Segoe UI',17,'bold'),
                 bg='#11151D',fg='#FFFFFF').pack(anchor='w')
        tk.Label(header,text='A rolagem e a seleção não mudam enquanto o monitor atualiza ao fundo.',
                 font=('Segoe UI',10),bg='#11151D',fg='#B8C5D9').pack(anchor='w')
        controls = tk.Frame(self, bg='#11151D');controls.pack(fill='x',padx=16,pady=(4,10))
        tk.Button(controls,text='Capturar leitura mais recente',command=self.capture,bg='#F16B67',fg='#080C11',
                  relief='flat',padx=12,pady=8,cursor='hand2').pack(side='left')
        tk.Button(controls,text='Copiar linha selecionada',command=self.copy_selected,bg='#263546',fg='white',
                  relief='flat',padx=10,pady=8).pack(side='left',padx=10)
        self.filter_var=tk.StringVar(value='Todos')
        ttk.Combobox(controls,textvariable=self.filter_var,state='readonly',width=19,
                     values=['Todos','CPU','GPU','SSD / HD','Placa-mãe / chipset','Memória RAM','Fonte / PSU','Outros']).pack(side='right')
        self.filter_var.trace_add('write',lambda *_:self.fill_valid())
        self.note=tk.Label(self,text='',anchor='w',justify='left',wraplength=1060,
                            bg='#1A2533',fg='#E6EFFA',font=('Segoe UI',10),padx=13,pady=9)
        self.note.pack(fill='x',padx=16,pady=(0,10))
        self.tabs=ttk.Notebook(self,style='OSReviewSensors.TNotebook');self.tabs.pack(fill='both',expand=True,padx=16,pady=(0,16))
        self.tables={}
        defs=[('Leituras válidas',('Grupo','Componente','Sensor','Tipo','Atual','Mín.','Máx.')),
              ('Sem valor',('Componente','Sensor','Tipo','Motivo')),
              ('Dispositivos',('Modelo','Categoria','Sensores','Subdispositivos'))]
        for tab,cols in defs:
            frame=ttk.Frame(self.tabs);self.tabs.add(frame,text=tab)
            tree=ttk.Treeview(frame,columns=cols,show='headings',selectmode='browse',style='OSReviewSensors.Treeview')
            for col in cols:
                tree.heading(col,text=col)
                tree.column(col,width=(265 if col in ('Componente','Modelo') else 155),stretch=True,anchor='w')
            v=ttk.Scrollbar(frame,orient='vertical',command=tree.yview)
            h=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview)
            tree.configure(yscrollcommand=v.set,xscrollcommand=h.set)
            frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1)
            tree.grid(row=0,column=0,sticky='nsew');v.grid(row=0,column=1,sticky='ns');h.grid(row=1,column=0,sticky='ew')
            self.tables[tab]=tree
        self.capture()

    def capture(self):
        self.snapshot=self.data_provider() or {}
        result=triage(self.snapshot)
        self.note.configure(text=(f"{result['status']}  •  Válidas: {result['valid_temperatures']} temperaturas  •  "
                                  f"Sem valor: {result['missing_temperatures']} temperaturas  •  "
                                  f"Potências de 0 W: {result['invalid_power_zero']} (verificar confiabilidade)\n"
                                  + '  '.join(result['findings'][:2])))
        self.fill_valid()
        status=self.snapshot.get('engine_status') or {}
        invalid=status.get('unavailable') or []
        devices=status.get('hardware') or []
        self._fill('Sem valor',[(d.get('Hardware'),d.get('Sensor'),d.get('SensorType'),d.get('Reason')) for d in invalid])
        self._fill('Dispositivos',[(d.get('Hardware'),d.get('Type'),d.get('SensorCount'),d.get('SubdeviceCount')) for d in devices])

    def fill_valid(self):
        group=self.filter_var.get()
        rows=[]
        for group_name,items in (self.snapshot.get('groups') or {}).items():
            if group!='Todos' and group_name!=group: continue
            for d in items:
                value=d.get('value')
                unit=d.get('unit') or ''
                if d.get('type','').lower()=='power' and value == 0:
                    display='0 W (verificar)'
                else:
                    display=f'{value} {unit}'.strip() if value is not None else 'Indisponível'
                if d.get('type','').casefold()=='temperature' and not is_real_temperature(d):
                    display+=' (LIMITE/MARGEM, NÃO ATUAL)'
                rows.append((group_name,d.get('device'),d.get('name'),d.get('type'),display,d.get('min'),d.get('max')))
        self._fill('Leituras válidas',rows)

    def _fill(self,name,rows):
        tree=self.tables[name]
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert('','end',values=['—' if x is None else str(x) for x in row])

    def copy_selected(self):
        tree=self.tables[self.tabs.tab(self.tabs.select(),'text')]
        selected=tree.selection()
        if not selected:
            messagebox.showinfo('OSReview','Selecione uma linha primeiro.',parent=self);return
        values=tree.item(selected[0],'values')
        self.clipboard_clear();self.clipboard_append(' | '.join(map(str,values)))
