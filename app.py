#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import tempfile
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk, ImageOps

import layout_solver

REF_RE = re.compile(r"^\d{1,4}(?:[A-Za-z]|[′'″\"])?$")

@dataclass
class RefItem:
    token: str
    name: str = ""
    bbox: Optional[List[float]] = None
    source: str = "PDF"

@dataclass
class BodyItem:
    kind: str
    bbox: List[float]
    id: str

@dataclass
class PageState:
    refs: Dict[str, RefItem] = field(default_factory=dict)
    bodies: List[BodyItem] = field(default_factory=list)

class PatentAnnotationApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Patent Figure Annotation Studio V2.1.1")
        self.geometry("1500x920")
        self.minsize(1200, 760)
        self.input_path = None
        self.pdf_doc = None
        self.page_index = 0
        self.page_count = 1
        self.page_image = None
        self.output_image = None
        self.page_states: Dict[int, PageState] = {}
        self.display_scale = 1.0
        self.display_offset = (0, 0)
        self.photo = None
        self.output_photo = None
        self.tool_mode = tk.StringVar(value="select")
        self.body_type = tk.StringVar(value="rect")
        self.pending_manual_ref = None
        self.drag_start = None
        self.drag_id = None
        self.filename_var = tk.StringVar()
        self.page_var = tk.StringVar(value="1 / 1")
        self.status_var = tk.StringVar(value="打开原始 PDF 或图片开始。")
        self.output_scale_var = tk.StringVar(value="2")
        self.lanes_var = tk.StringVar(value="4")
        self.label_font_var = tk.StringVar(value="")
        self.title_font_var = tk.StringVar(value="")
        self._build_ui()

    def state(self):
        return self.page_states.setdefault(self.page_index, PageState())

    def _build_ui(self):
        self.columnconfigure(1, weight=1); self.rowconfigure(1, weight=1)
        bar = ttk.Frame(self, padding=6); bar.grid(row=0,column=0,columnspan=2,sticky="ew"); bar.columnconfigure(10,weight=1)
        for col,text,cmd in [
            (0,"打开 PDF / 图片",self.open_input),(1,"上一页",lambda:self.change_page(-1)),(2,"下一页",lambda:self.change_page(1)),
            (4,"导入序号-名称",self.import_mapping),(5,"粘贴映射",self.paste_mapping),(6,"处理当前页",self.process_page),(7,"保存结果",self.save_output)]:
            ttk.Button(bar,text=text,command=cmd).grid(row=0,column=col,padx=3)
        ttk.Label(bar,textvariable=self.page_var,width=10).grid(row=0,column=3,padx=4)
        ttk.Label(bar,text="专利文件名：").grid(row=0,column=9,sticky="e",padx=(15,3))
        ttk.Entry(bar,textvariable=self.filename_var).grid(row=0,column=10,sticky="ew")

        side = ttk.Frame(self,padding=8); side.grid(row=1,column=0,sticky="nsw")
        body_box = ttk.LabelFrame(side,text="1. 机械主体区域",padding=8); body_box.grid(row=0,column=0,sticky="ew",pady=(0,8))
        ttk.Radiobutton(body_box,text="矩形主体",variable=self.body_type,value="rect").grid(row=0,column=0,sticky="w")
        ttk.Radiobutton(body_box,text="圆形主体",variable=self.body_type,value="circle").grid(row=0,column=1,sticky="w")
        ttk.Button(body_box,text="拖框新增主体",command=lambda:self.tool_mode.set("draw_body")).grid(row=1,column=0,columnspan=2,sticky="ew",pady=2)
        ttk.Button(body_box,text="自动估计主体",command=self.auto_body).grid(row=2,column=0,columnspan=2,sticky="ew",pady=2)
        ttk.Button(body_box,text="清除本页主体",command=self.clear_bodies).grid(row=3,column=0,columnspan=2,sticky="ew",pady=2)
        self.body_list = tk.Listbox(body_box,width=34,height=5); self.body_list.grid(row=4,column=0,columnspan=2,sticky="ew",pady=3)
        ttk.Button(body_box,text="删除选中主体",command=self.delete_body).grid(row=5,column=0,columnspan=2,sticky="ew")

        manual = ttk.LabelFrame(side,text="2. 扫描图手动序号",padding=8); manual.grid(row=1,column=0,sticky="ew",pady=(0,8))
        ttk.Button(manual,text="添加序号并在图上点击",command=self.add_manual_ref).grid(row=0,column=0,sticky="ew")
        ttk.Label(manual,text="矢量 PDF 一般无需此步骤。",foreground="#666").grid(row=1,column=0,sticky="w",pady=(4,0))

        mapbox = ttk.LabelFrame(side,text="3. 序号 → 中文名称",padding=6); mapbox.grid(row=2,column=0,sticky="nsew",pady=(0,8))
        self.ref_tree = ttk.Treeview(mapbox,columns=("token","name","source"),show="headings",height=16)
        for c,t,w in [("token","序号",60),("name","中文名称",150),("source","来源",55)]:
            self.ref_tree.heading(c,text=t); self.ref_tree.column(c,width=w,anchor="center" if c!="name" else "w")
        self.ref_tree.grid(row=0,column=0,sticky="nsew"); self.ref_tree.bind("<Double-1>",self.edit_ref_name)
        sb=ttk.Scrollbar(mapbox,orient="vertical",command=self.ref_tree.yview); sb.grid(row=0,column=1,sticky="ns"); self.ref_tree.configure(yscrollcommand=sb.set)

        opt=ttk.LabelFrame(side,text="4. 输出",padding=8); opt.grid(row=3,column=0,sticky="ew")
        ttk.Label(opt,text="输出倍率").grid(row=0,column=0,sticky="w"); ttk.Combobox(opt,textvariable=self.output_scale_var,values=["1","2","3","4"],width=6,state="readonly").grid(row=0,column=1)
        ttk.Label(opt,text="最大 Lane").grid(row=1,column=0,sticky="w"); ttk.Combobox(opt,textvariable=self.lanes_var,values=["2","3","4","5","6"],width=6,state="readonly").grid(row=1,column=1)
        ttk.Label(opt,text="零件名称字号(px)").grid(row=2,column=0,sticky="w"); ttk.Entry(opt,textvariable=self.label_font_var,width=8).grid(row=2,column=1)
        ttk.Label(opt,text="文件名字号(px)").grid(row=3,column=0,sticky="w"); ttk.Entry(opt,textvariable=self.title_font_var,width=8).grid(row=3,column=1)

        nb=ttk.Notebook(self); nb.grid(row=1,column=1,sticky="nsew",padx=(0,8),pady=(0,8))
        f1=ttk.Frame(nb); f2=ttk.Frame(nb); nb.add(f1,text="原图 / 布局"); nb.add(f2,text="输出预览")
        for f in (f1,f2): f.rowconfigure(0,weight=1); f.columnconfigure(0,weight=1)
        self.canvas=tk.Canvas(f1,bg="#d8d8d8",highlightthickness=0); self.canvas.grid(row=0,column=0,sticky="nsew")
        self.canvas.bind("<Configure>",lambda e:self.redraw_input()); self.canvas.bind("<ButtonPress-1>",self.canvas_press); self.canvas.bind("<B1-Motion>",self.canvas_drag); self.canvas.bind("<ButtonRelease-1>",self.canvas_release)
        self.out_canvas=tk.Canvas(f2,bg="#d8d8d8",highlightthickness=0); self.out_canvas.grid(row=0,column=0,sticky="nsew"); self.out_canvas.bind("<Configure>",lambda e:self.redraw_output())
        ttk.Label(self,textvariable=self.status_var,anchor="w",padding=(8,4)).grid(row=2,column=0,columnspan=2,sticky="ew")

    def open_input(self):
        p=filedialog.askopenfilename(filetypes=[("PDF / Images","*.pdf *.png *.jpg *.jpeg *.tif *.tiff"),("All","*.*")])
        if not p:return
        self.input_path=Path(p); self.filename_var.set(self.input_path.name); self.page_states={}; self.output_image=None
        if self.input_path.suffix.lower()==".pdf":
            import fitz
            self.pdf_doc=fitz.open(str(self.input_path)); self.page_count=len(self.pdf_doc)
        else:self.pdf_doc=None; self.page_count=1
        self.page_index=0; self.load_page()

    def load_page(self):
        if self.pdf_doc is not None:
            import fitz
            page=self.pdf_doc[self.page_index]; z=2.0; pix=page.get_pixmap(matrix=fitz.Matrix(z,z),alpha=False)
            self.page_image=Image.frombytes("RGB",[pix.width,pix.height],pix.samples); self.extract_pdf_refs(page,z)
        else:self.page_image=Image.open(self.input_path).convert("RGB")
        self.page_var.set(f"{self.page_index+1} / {self.page_count}"); self.refresh_refs(); self.refresh_bodies(); self.redraw_input(); self.status_var.set("页面已加载。")

    def change_page(self,d):
        n=self.page_index+d
        if 0<=n<self.page_count:self.page_index=n; self.load_page()

    def extract_pdf_refs(self,page,z):
        st=self.state()
        for w in page.get_text("words"):
            t=str(w[4]).strip()
            if REF_RE.match(t) and t not in st.refs:
                st.refs[t]=RefItem(t,"",[w[0]*z,w[1]*z,w[2]*z,w[3]*z],"PDF")

    def refresh_refs(self):
        self.ref_tree.delete(*self.ref_tree.get_children())
        for t,r in sorted(self.state().refs.items(),key=lambda x:(int(re.match(r"\d+",x[0]).group()) if re.match(r"\d+",x[0]) else 9999,x[0])):
            self.ref_tree.insert("","end",iid=t,values=(t,r.name,r.source))

    def refresh_bodies(self):
        self.body_list.delete(0,"end")
        for b in self.state().bodies:self.body_list.insert("end",f"{b.id}: {b.kind} {[round(x) for x in b.bbox]}")

    def parse_mapping(self,text):
        out={}
        for line in text.splitlines():
            line=line.strip()
            if not line or line.startswith("#"):continue
            parts=line.split(",",1) if "," in line else line.split("\t",1) if "\t" in line else line.split(None,1)
            if len(parts)==2:out[parts[0].strip()]=parts[1].strip()
        return out

    def apply_mapping(self,m):
        st=self.state()
        for t,n in m.items():
            if t in st.refs:st.refs[t].name=n
            else:st.refs[t]=RefItem(t,n,None,"映射")
        self.refresh_refs(); self.redraw_input()

    def import_mapping(self):
        p=filedialog.askopenfilename(filetypes=[("Mapping","*.txt *.csv *.tsv *.json"),("All","*.*")])
        if not p:return
        path=Path(p)
        if path.suffix.lower()==".json":
            d=json.loads(path.read_text(encoding="utf-8-sig")); m={str(x["token"]):str(x["name"]) for x in d} if isinstance(d,list) else {str(k):str(v) for k,v in d.items()}
        else:m=self.parse_mapping(path.read_text(encoding="utf-8-sig"))
        self.apply_mapping(m)

    def paste_mapping(self):
        w=tk.Toplevel(self); w.title("粘贴序号 → 中文名称"); w.geometry("480x500")
        txt=tk.Text(w); txt.pack(fill="both",expand=True,padx=8,pady=8); txt.insert("1.0","27 高压通道\n31 阻尼阀装置\n")
        ttk.Button(w,text="应用",command=lambda:(self.apply_mapping(self.parse_mapping(txt.get("1.0","end"))),w.destroy())).pack(pady=6)

    def edit_ref_name(self,e=None):
        s=self.ref_tree.selection()
        if not s:return
        t=s[0]; v=simpledialog.askstring("编辑中文名称",f"序号 {t}：",initialvalue=self.state().refs[t].name,parent=self)
        if v is not None:self.state().refs[t].name=v.strip(); self.refresh_refs(); self.redraw_input()

    def fit(self,im,canvas):
        cw=max(100,canvas.winfo_width()); ch=max(100,canvas.winfo_height()); s=max(.05,min((cw-20)/im.width,(ch-20)/im.height,1.5)); size=(int(im.width*s),int(im.height*s)); off=((cw-size[0])//2,(ch-size[1])//2)
        return im.resize(size,Image.Resampling.LANCZOS),s,off

    def image_to_canvas(self,x,y):ox,oy=self.display_offset; return ox+x*self.display_scale,oy+y*self.display_scale
    def canvas_to_image(self,x,y):ox,oy=self.display_offset; return (x-ox)/self.display_scale,(y-oy)/self.display_scale

    def redraw_input(self):
        self.canvas.delete("all")
        if self.page_image is None:return
        im,s,off=self.fit(self.page_image,self.canvas); self.display_scale=s; self.display_offset=off; self.photo=ImageTk.PhotoImage(im); self.canvas.create_image(*off,anchor="nw",image=self.photo)
        for b in self.state().bodies:
            x0,y0=self.image_to_canvas(b.bbox[0],b.bbox[1]); x1,y1=self.image_to_canvas(b.bbox[2],b.bbox[3]); fn=self.canvas.create_rectangle if b.kind=="rect" else self.canvas.create_oval; fn(x0,y0,x1,y1,outline="#00a060",width=3,dash=(7,4)); self.canvas.create_text(x0+3,y0+3,text=b.id,anchor="nw",fill="#008050")
        for r in self.state().refs.values():
            if r.name and r.bbox:
                x0,y0=self.image_to_canvas(r.bbox[0],r.bbox[1]); x1,y1=self.image_to_canvas(r.bbox[2],r.bbox[3]); self.canvas.create_rectangle(x0,y0,x1,y1,outline="#ff9900",width=2); self.canvas.create_text(x1+4,y0,text=r.name,anchor="nw",fill="#123A63")

    def redraw_output(self):
        self.out_canvas.delete("all")
        if self.output_image is None:return
        im,_,off=self.fit(self.output_image,self.out_canvas); self.output_photo=ImageTk.PhotoImage(im); self.out_canvas.create_image(*off,anchor="nw",image=self.output_photo)

    def canvas_press(self,e):
        if self.tool_mode.get()=="draw_body":self.drag_start=(e.x,e.y); self.drag_id=self.canvas.create_rectangle(e.x,e.y,e.x,e.y,outline="#00a060",width=3,dash=(7,4))
        elif self.tool_mode.get()=="manual_ref":self.finish_manual_ref(e.x,e.y)
    def canvas_drag(self,e):
        if self.tool_mode.get()=="draw_body" and self.drag_start:self.canvas.coords(self.drag_id,*self.drag_start,e.x,e.y)
    def canvas_release(self,e):
        if self.tool_mode.get()!="draw_body" or not self.drag_start:return
        x0,y0=self.drag_start; self.drag_start=None
        if abs(e.x-x0)<20 or abs(e.y-y0)<20:self.redraw_input(); return
        a,b=self.canvas_to_image(min(x0,e.x),min(y0,e.y)); c,d=self.canvas_to_image(max(x0,e.x),max(y0,e.y)); st=self.state(); st.bodies.append(BodyItem(self.body_type.get(),[max(0,a),max(0,b),min(self.page_image.width,c),min(self.page_image.height,d)],f"F{len(st.bodies)+1}")); self.tool_mode.set("select"); self.refresh_bodies(); self.redraw_input()

    def clear_bodies(self):self.state().bodies.clear(); self.refresh_bodies(); self.redraw_input()
    def delete_body(self):
        s=self.body_list.curselection()
        if s:del self.state().bodies[s[0]]; [setattr(b,"id",f"F{i}") for i,b in enumerate(self.state().bodies,1)]; self.refresh_bodies(); self.redraw_input()

    def auto_body(self):
        if self.page_image is None:return
        import numpy as np
        g=np.array(ImageOps.grayscale(self.page_image)); h,w=g.shape; roi=g[int(h*.06):int(h*.90),int(w*.06):int(w*.94)]; ys,xs=np.where(roi<180)
        if len(xs)<100:return messagebox.showwarning("失败","未检测到足够技术线条，请手工拖框。")
        qx0,qx1=np.quantile(xs,[.05,.95]); qy0,qy1=np.quantile(ys,[.04,.96]); box=[int(w*.06)+qx0,int(h*.06)+qy0,int(w*.06)+qx1,int(h*.06)+qy1]; st=self.state(); st.bodies.append(BodyItem("rect",list(map(float,box)),f"F{len(st.bodies)+1}")); self.refresh_bodies(); self.redraw_input()

    def add_manual_ref(self):
        t=simpledialog.askstring("手动序号","输入原始序号：",parent=self)
        if not t:return
        n=simpledialog.askstring("中文名称",f"序号 {t} 的中文名称：",parent=self)
        if n is None:return
        self.state().refs[t]=RefItem(t,n.strip(),None,"手工"); self.pending_manual_ref=t; self.tool_mode.set("manual_ref"); self.refresh_refs()

    def finish_manual_ref(self,cx,cy):
        t=self.pending_manual_ref
        if not t:return
        x,y=self.canvas_to_image(cx,cy); sz=max(18,self.page_image.width*.012); self.state().refs[t].bbox=[x-sz,y-sz*.7,x+sz,y+sz*.7]; self.pending_manual_ref=None; self.tool_mode.set("select"); self.refresh_refs(); self.redraw_input()

    def build_figures(self):
        st=self.state(); refs=[r for r in st.refs.values() if r.name]
        if not st.bodies:raise ValueError("请先定义至少一个机械主体区域。")
        missing=[r.token for r in refs if r.bbox is None]
        if missing:raise ValueError("这些序号没有坐标，请手动点击定位："+", ".join(missing))
        assign={b.id:[] for b in st.bodies}
        for r in refs:
            rr=layout_solver.rect_from(r.bbox); b=min(st.bodies,key=lambda x:(rr.cx-layout_solver.rect_from(x.bbox).cx)**2+(rr.cy-layout_solver.rect_from(x.bbox).cy)**2); assign[b.id].append(r)
        figs=[]
        for b in st.bodies:
            rs=assign[b.id]
            if not rs:continue
            if b.kind=="circle":x0,y0,x1,y1=b.bbox; body={"type":"circle","cx":(x0+x1)/2,"cy":(y0+y1)/2,"r":max(x1-x0,y1-y0)/2}
            else:body={"type":"rect","bbox":b.bbox}
            figs.append({"id":b.id,"bbox":b.bbox,"body":body,"refs":[{"token":r.token,"name":r.name,"bbox":r.bbox} for r in rs],"obstacles":[]})
        return figs

    def process_page(self):
        if self.page_image is None:return
        try:
            work=Path(tempfile.mkdtemp(prefix="patent_anno_")); page=work/"page.png"; self.page_image.save(page)
            spec={"input":str(page),"filename":self.filename_var.get().strip(),"output_scale":float(self.output_scale_var.get()),"lanes":int(self.lanes_var.get()),"figures":self.build_figures()}
            if self.label_font_var.get().strip():spec["label_font_px"]=int(self.label_font_var.get())
            if self.title_font_var.get().strip():spec["title_font_px"]=int(self.title_font_var.get())
            out=work/"annotated.png"; rep=work/"report.json"; layout_solver.render(spec,str(out),str(rep)); self.output_image=Image.open(out).convert("RGB"); self.last_report_path=rep; self.redraw_output(); self.status_var.set("处理完成：Preflight PASS。")
            messagebox.showinfo("完成","当前页处理完成，Preflight PASS。")
        except Exception as e:messagebox.showerror("处理失败",f"{e}\n\n{traceback.format_exc(limit=2)}")

    def save_output(self):
        if self.output_image is None:return messagebox.showwarning("没有结果","请先处理当前页。")
        default=(self.input_path.stem if self.input_path else "patent")+f"_p{self.page_index+1:02d}_中文标注.png"; p=filedialog.asksaveasfilename(initialfile=default,defaultextension=".png",filetypes=[("PNG","*.png")])
        if not p:return
        self.output_image.save(p,"PNG")
        if hasattr(self,"last_report_path"):Path(p).with_suffix(".report.json").write_text(Path(self.last_report_path).read_text(encoding="utf-8"),encoding="utf-8")

if __name__=="__main__":PatentAnnotationApp().mainloop()
