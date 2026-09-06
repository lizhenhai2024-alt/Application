#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix

BLUE = (18, 58, 99)
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]

@dataclass(frozen=True)
class Rect:
    x0: float; y0: float; x1: float; y1: float
    @property
    def w(self): return self.x1 - self.x0
    @property
    def h(self): return self.y1 - self.y0
    @property
    def cx(self): return (self.x0 + self.x1) / 2
    @property
    def cy(self): return (self.y0 + self.y1) / 2
    def expand(self, d): return Rect(self.x0-d, self.y0-d, self.x1+d, self.y1+d)
    def intersects(self, other, gap=0.0):
        a, b = self.expand(gap/2), other.expand(gap/2)
        return not (a.x1 <= b.x0 or a.x0 >= b.x1 or a.y1 <= b.y0 or a.y0 >= b.y1)

def rect_from(v): return Rect(*map(float, v))

def find_font(size, preferred=None):
    for p in ([preferred] if preferred else []) + FONT_CANDIDATES:
        if p and os.path.exists(p):
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()

def text_size(text, font):
    im = Image.new("RGB", (10, 10), "white")
    b = ImageDraw.Draw(im).textbbox((0, 0), text, font=font)
    return max(1, b[2]-b[0]), max(1, b[3]-b[1])

def load_input(spec):
    p = Path(spec["input"])
    if p.suffix.lower() == ".pdf":
        import fitz
        doc = fitz.open(str(p))
        page = doc[int(spec.get("page", 0))]
        z = float(spec.get("pdf_zoom", 2.0))
        pix = page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return Image.open(p).convert("RGB")

def body_collision(r, body, clearance=0):
    if body.get("type", "rect") == "rect":
        return r.intersects(rect_from(body["bbox"]).expand(clearance))
    cx, cy = float(body["cx"]), float(body["cy"])
    rr = float(body["r"]) + clearance
    qx = min(max(cx, r.x0), r.x1); qy = min(max(cy, r.y0), r.y1)
    return (qx-cx)**2 + (qy-cy)**2 <= rr*rr

def classify_side(a, body):
    if body.get("type", "rect") == "circle":
        dx, dy = a.cx-float(body["cx"]), a.cy-float(body["cy"])
        return ("RIGHT" if dx >= 0 else "LEFT") if abs(dx) >= abs(dy) else ("BOTTOM" if dy >= 0 else "TOP")
    b = rect_from(body["bbox"])
    d = {"LEFT":abs(a.cx-b.x0), "RIGHT":abs(a.cx-b.x1), "TOP":abs(a.cy-b.y0), "BOTTOM":abs(a.cy-b.y1)}
    return min(d, key=d.get)

@dataclass
class Candidate:
    ref_i: int
    rect: Rect
    side: str
    lane: int
    cost: float

def rect_candidate(anchor, wh, body, side, lane, shift, clearance, lane_gap, anchor_gap):
    w, h = wh; b = rect_from(body["bbox"]); out = clearance + lane*lane_gap
    if side == "LEFT":
        x1 = min(anchor.x0-anchor_gap, b.x0-out); return Rect(x1-w, anchor.cy-h/2+shift, x1, anchor.cy+h/2+shift)
    if side == "RIGHT":
        x0 = max(anchor.x1+anchor_gap, b.x1+out); return Rect(x0, anchor.cy-h/2+shift, x0+w, anchor.cy+h/2+shift)
    if side == "TOP":
        y1 = min(anchor.y0-anchor_gap, b.y0-out); return Rect(anchor.cx-w/2+shift, y1-h, anchor.cx+w/2+shift, y1)
    y0 = max(anchor.y1+anchor_gap, b.y1+out); return Rect(anchor.cx-w/2+shift, y0, anchor.cx+w/2+shift, y0+h)

def circle_candidate(anchor, wh, body, lane, angle_shift, clearance, lane_gap):
    w, h = wh; cx, cy, r = float(body["cx"]), float(body["cy"]), float(body["r"])
    a = math.atan2(anchor.cy-cy, anchor.cx-cx) + angle_shift
    rr = r + clearance + lane*lane_gap + max(w, h)*0.35
    px, py = cx+rr*math.cos(a), cy+rr*math.sin(a)
    return Rect(px-w/2, py-h/2, px+w/2, py+h/2)

def generate_candidates(fig, refs, font, gap, clearance, lanes):
    body = fig["body"]
    anchors = [rect_from(r["bbox"]) for r in refs]
    obstacles = [rect_from(x) for x in fig.get("obstacles", [])] + anchors
    out = []
    for i, ref in enumerate(refs):
        a = anchors[i]; side = classify_side(a, body); wh = text_size(str(ref["name"]), font); cs = []
        if body.get("type", "rect") == "circle":
            for lane in range(1, lanes+1):
                for ang in [0, -0.10, 0.10, -0.20, 0.20, -0.30, 0.30]:
                    r = circle_candidate(a, wh, body, lane, ang, clearance, gap*2)
                    if body_collision(r, body) or any(r.intersects(o, gap*0.25) for o in obstacles): continue
                    cs.append(Candidate(i, r, side, lane, lane*100 + abs(ang)*100 + math.hypot(r.cx-a.cx, r.cy-a.cy)))
        else:
            shifts = [0, -0.75, 0.75, -1.5, 1.5, -2.25, 2.25]
            for lane in range(1, lanes+1):
                for s in shifts:
                    sh = s*wh[1]
                    r = rect_candidate(a, wh, body, side, lane, sh, clearance, gap*2, gap*0.5)
                    if body_collision(r, body) or any(r.intersects(o, gap*0.25) for o in obstacles): continue
                    cs.append(Candidate(i, r, side, lane, lane*100 + abs(sh) + math.hypot(r.cx-a.cx, r.cy-a.cy)))
        if not cs:
            raise RuntimeError(f"No legal candidates for ref {ref['token']} {ref['name']}")
        out.append(cs)
    return out

def order_conflict(ca, cb, aa, ab, gap):
    if ca.side != cb.side: return False
    if ca.side in ("LEFT", "RIGHT"):
        return (aa.cy < ab.cy and ca.rect.y1+gap > cb.rect.y0) or (ab.cy < aa.cy and cb.rect.y1+gap > ca.rect.y0)
    return (aa.cx < ab.cx and ca.rect.x1+gap > cb.rect.x0) or (ab.cx < aa.cx and cb.rect.x1+gap > ca.rect.x0)

def solve_global(groups, refs, gap):
    flat, offsets = [], []
    for g in groups: offsets.append(len(flat)); flat += g
    n = len(flat); rows=[]; lo=[]; hi=[]
    for i,g in enumerate(groups):
        rows.append({offsets[i]+k:1 for k in range(len(g))}); lo.append(1); hi.append(1)
    anchors = [rect_from(r["bbox"]) for r in refs]
    for i in range(len(refs)):
        for j in range(i+1, len(refs)):
            for ki,ca in enumerate(groups[i]):
                for kj,cb in enumerate(groups[j]):
                    if ca.rect.intersects(cb.rect, gap) or order_conflict(ca, cb, anchors[i], anchors[j], gap*0.5):
                        rows.append({offsets[i]+ki:1, offsets[j]+kj:1}); lo.append(-np.inf); hi.append(1)
    A = lil_matrix((len(rows), n), dtype=float)
    for ri,row in enumerate(rows):
        for ci,v in row.items(): A[ri,ci]=v
    res = milp(c=np.array([x.cost for x in flat]), integrality=np.ones(n), bounds=Bounds(np.zeros(n), np.ones(n)),
               constraints=LinearConstraint(A.tocsr(), np.array(lo), np.array(hi)), options={"time_limit":20.0, "presolve":True})
    if not res.success or res.x is None: raise RuntimeError(f"Layout solver infeasible: {res.message}")
    chosen=[]
    for i,g in enumerate(groups):
        vals=res.x[offsets[i]:offsets[i]+len(g)]; chosen.append(g[int(np.argmax(vals))])
    return chosen

def render(spec, output_path, report_path=None):
    img=load_input(spec); figures=spec["figures"]
    long=max(img.size); scale=long/4096.0
    label_px=int(spec.get("label_font_px", max(16, round(28*scale))))
    title_px=int(spec.get("title_font_px", max(15, round(26*scale))))
    label_font=find_font(label_px, spec.get("font")); title_font=find_font(title_px, spec.get("font"))
    gap=float(spec.get("label_gap_px", max(6, label_px*0.45))); clearance=float(spec.get("body_clearance_px", max(8, label_px*0.75)))
    placements=[]; minx=miny=0.0; maxx=float(img.width); maxy=float(img.height)
    for fig in figures:
        refs=[r for r in fig.get("refs", []) if r.get("name")]
        if any("bbox" not in r for r in refs): raise RuntimeError(f"Missing bbox in {fig.get('id','figure')}")
        groups=generate_candidates(fig, refs, label_font, gap, clearance, int(spec.get("lanes",4)))
        chosen=solve_global(groups, refs, gap)
        for r,c in zip(refs,chosen):
            placements.append((fig.get("id",""),r,c)); minx=min(minx,c.rect.x0); miny=min(miny,c.rect.y0); maxx=max(maxx,c.rect.x1); maxy=max(maxy,c.rect.y1)
    pad=int(spec.get("outer_pad_px", max(12,label_px))); title_band=int(spec.get("title_band_px", max(title_px*3,55*scale)))
    lp=int(max(pad,-minx+pad)); rp=int(max(pad,maxx-img.width+pad)); bp=int(max(pad,maxy-img.height+pad)); tp=int(max(pad,-miny+pad))
    canvas=Image.new("RGB",(img.width+lp+rp,img.height+title_band+tp+bp),"white"); ox,oy=lp,title_band+tp; canvas.paste(img,(ox,oy)); d=ImageDraw.Draw(canvas)
    if spec.get("filename"): d.text((pad,max(4,pad//2)),spec["filename"],fill=BLUE,font=title_font)
    for _,r,c in placements: d.text((c.rect.x0+ox,c.rect.y0+oy),str(r["name"]),fill=BLUE,font=label_font)
    errors=[]
    for fid,r,c in placements:
        fig=next(f for f in figures if f.get("id","")==fid)
        if body_collision(c.rect,fig["body"]): errors.append(f"{fid}:{r['token']} intersects body")
        for rr in fig.get("refs",[]):
            if "bbox" in rr and c.rect.intersects(rect_from(rr["bbox"])): errors.append(f"{fid}:{r['token']} overlaps ref {rr['token']}")
    for i in range(len(placements)):
        for j in range(i+1,len(placements)):
            if placements[i][0]==placements[j][0] and placements[i][2].rect.intersects(placements[j][2].rect,gap): errors.append(f"{placements[i][0]} label overlap")
    report={"status":"PASS" if not errors else "FAIL","errors":errors,"placements":[{"figure":fid,"token":r["token"],"name":r["name"],"side":c.side,"lane":c.lane,"rect":[c.rect.x0,c.rect.y0,c.rect.x1,c.rect.y1]} for fid,r,c in placements],"canvas":list(canvas.size)}
    if report_path: Path(report_path).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    if errors: raise RuntimeError("Preflight FAIL: "+"; ".join(errors[:8]))
    s=float(spec.get("output_scale",1.0))
    if s!=1.0: canvas=canvas.resize((round(canvas.width*s),round(canvas.height*s)),Image.Resampling.LANCZOS)
    canvas.save(output_path,"PNG")
    return report

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--spec",required=True); ap.add_argument("--output",required=True); ap.add_argument("--report")
    a=ap.parse_args(); spec=json.loads(Path(a.spec).read_text(encoding="utf-8")); print(json.dumps(render(spec,a.output,a.report),ensure_ascii=False,indent=2))

if __name__=="__main__": main()
