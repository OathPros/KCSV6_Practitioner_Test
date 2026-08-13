#!/usr/bin/env python3
"""Create a self-contained, expanded PDF handout from the Auto Triage deck."""
from html.parser import HTMLParser
from pathlib import Path
import re, textwrap

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "index.html"
OUTPUT = ROOT / "auto-triage-deck.pdf"

class Node:
    def __init__(self, tag="", attrs=None, parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs or []), parent, []
    def text(self):
        return re.sub(r"\s+", " ", " ".join(x if isinstance(x,str) else x.text() for x in self.children)).strip()
    def findall(self, pred):
        out=[]
        for x in self.children:
            if not isinstance(x,str):
                if pred(x): out.append(x)
                out += x.findall(pred)
        return out

class Parser(HTMLParser):
    void={"meta","link","br","hr","img","input"}
    def __init__(self): super().__init__(); self.root=Node(); self.cur=self.root
    def handle_starttag(self,tag,attrs):
        n=Node(tag,attrs,self.cur); self.cur.children.append(n)
        if tag not in self.void: self.cur=n
    def handle_startendtag(self,tag,attrs): self.handle_starttag(tag,attrs); self.cur=self.cur.parent if self.cur.tag==tag else self.cur
    def handle_endtag(self,tag):
        n=self.cur
        while n is not self.root and n.tag!=tag: n=n.parent
        if n is not self.root: self.cur=n.parent
    def handle_data(self,data):
        if self.cur.tag not in {"style","script"} and data.strip(): self.cur.children.append(data.strip())

def esc(s): return str(s).replace("\\","\\\\").replace("(","\\(").replace(")","\\)").encode("latin-1","replace").decode("latin-1")
def rgb(h): return tuple(int(h[i:i+2],16)/255 for i in (1,3,5))
def wrap(text, width): return textwrap.wrap(text,width=width,break_long_words=False,break_on_hyphens=False) or [""]

class PDF:
    W,H=960,540
    def __init__(self): self.pages=[]
    def page(self,bg): self.ops=[]; self.fill(bg); self.rect(0,0,self.W,self.H); return self
    def fill(self,c): self.ops.append("%.3f %.3f %.3f rg"%rgb(c))
    def rect(self,x,y,w,h): self.ops.append(f"{x:.1f} {y:.1f} {w:.1f} {h:.1f} re f")
    def line(self,x1,y1,x2,y2,c="#e31837",width=2):
        self.ops.append("%.3f %.3f %.3f RG"%rgb(c)); self.ops.append(f"{width} w {x1} {y1} m {x2} {y2} l S")
    def text(self,x,y,s,size=14,color="#151515",bold=False):
        self.fill(color); font="F2" if bold else "F1"; self.ops.append(f"BT /{font} {size} Tf {x:.1f} {y:.1f} Td ({esc(s)}) Tj ET")
    def paragraph(self,x,y,s,size=14,color="#151515",bold=False,width=76,leading=None,max_lines=30):
        leading=leading or size*1.28
        for ln in wrap(s,width)[:max_lines]: self.text(x,y,ln,size,color,bold); y-=leading
        return y
    def finish(self): self.pages.append("\n".join(self.ops).encode("latin-1"))
    def save(self,path):
        objs=[b"<< /Type /Catalog /Pages 2 0 R >>",b""]
        page_ids=[]
        for stream in self.pages:
            cid=len(objs)+1; objs.append(b"<< /Length %d >>\nstream\n"%len(stream)+stream+b"\nendstream")
            pid=len(objs)+1; page_ids.append(pid)
            objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.W} {self.H}] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> /F2 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> >> >> /Contents {cid} 0 R >>".encode())
        objs[1]=(f"<< /Type /Pages /Count {len(page_ids)} /Kids ["+" ".join(f"{i} 0 R" for i in page_ids)+"] >>").encode()
        data=bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"); offsets=[0]
        for i,o in enumerate(objs,1): offsets.append(len(data)); data.extend(f"{i} 0 obj\n".encode()+o+b"\nendobj\n")
        x=len(data); data.extend(f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode())
        for off in offsets[1:]: data.extend(f"{off:010d} 00000 n \n".encode())
        data.extend(f"trailer << /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()); path.write_bytes(data)

def blocks(node):
    wanted={"p","li","h3","h4"}; found=node.findall(lambda n:n.tag in wanted)
    # Ignore nested list-item duplicates and headings repeated as parent content.
    return [(n.tag,n.text()) for n in found if n.text() and not (n.tag=="li" and any(a.tag=="li" for a in ancestors(n)))]
def ancestors(n):
    out=[]; n=n.parent
    while n: out.append(n); n=n.parent
    return out

def render(title, eyebrow, content, number, dark=False, accent="#e31837", suffix=""):
    bg="#151515" if dark else "#f4f0eb"; fg="#ffffff" if dark else "#151515"; muted="#c9c9c9" if dark else "#5f5f5f"
    pdf.page(bg); pdf.fill(accent); pdf.rect(0,0,12,540); pdf.text(48,492,eyebrow.upper(),11,accent,True); pdf.text(865,492,number,13,muted,True)
    y=444
    for ln in wrap(title,36)[:2]: pdf.text(48,y,ln,32,fg,True); y-=39
    pdf.line(48,y+11,912,y+11,accent,2); y-=14
    entries=content
    cols=[entries[i::2] for i in range(2)] if len(entries)>7 else [entries]
    colw=407 if len(cols)==2 else 820
    for ci,col in enumerate(cols):
        x=48+ci*432; cy=y
        for tag,txt in col:
            if cy<48: break
            if tag in {"h3","h4"}:
                cy-=4; cy=pdf.paragraph(x,cy,txt,16,accent,True,42 if len(cols)==2 else 82,20,max_lines=2)-5
            elif tag=="li":
                pdf.text(x,cy,"•",13,accent,True); cy=pdf.paragraph(x+16,cy,txt,11.5,fg,False,54 if len(cols)==2 else 105,14.5,max_lines=5)-5
            else: cy=pdf.paragraph(x,cy,txt,12.5,muted,False,55 if len(cols)==2 else 104,16,max_lines=6)-7
    pdf.text(48,22,"HALO AUTO TRIAGE  •  EXPANDED PDF EDITION"+("  •  "+suffix if suffix else ""),8,muted,True); pdf.finish()

p=Parser(); p.feed(SOURCE.read_text(encoding="utf-8"))
slides=p.root.findall(lambda n:n.tag=="section" and "slide" in n.attrs.get("class","").split())
pdf=PDF()
for i,s in enumerate(slides,1):
    heading=next(iter(s.findall(lambda n:n.tag in {"h1","h2"})),None)
    title=heading.text() if heading else s.attrs.get("data-title",f"Slide {i}")
    eye=next(iter(s.findall(lambda n:"eyebrow" in n.attrs.get("class","").split())),None)
    panels=s.findall(lambda n:n.attrs.get("role")=="tabpanel")
    base=[]
    panel_nodes=set(panels)
    for n in s.findall(lambda n:n.tag in {"p","li","h3","h4"}):
        if any(a in panel_nodes for a in ancestors(n)): continue
        if n.text(): base.append((n.tag,n.text()))
    classes=s.attrs.get("class",""); dark="slide--ink" in classes or "slide--red" in classes
    accent="#ffffff" if "slide--red" in classes else "#e31837"
    if panels:
        # Overview page preserves shared context, then one full page per clickable panel.
        render(title,eye.text() if eye else s.attrs.get("data-title",""),base,i,dark,accent,"OVERVIEW")
        for j,panel in enumerate(panels,1):
            h=next(iter(panel.findall(lambda n:n.tag=="h3")),None)
            render(h.text() if h else title, title, blocks(panel),f"{i}.{j}",dark,accent,"EXPANDED VIEW")
    else: render(title,eye.text() if eye else s.attrs.get("data-title",""),base,i,dark,accent)
pdf.save(OUTPUT)
print(f"Wrote {OUTPUT.name}: {len(pdf.pages)} pages, {OUTPUT.stat().st_size:,} bytes")
