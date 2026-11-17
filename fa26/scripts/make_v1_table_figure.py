"""Redraw reports/figures/iati_budget_table_2026-10-23.jpg (benchmark v1 table) from the run files.

    python fa26/scripts/make_v1_table_figure.py
"""
from pathlib import Path
import pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
B=Path(__file__).resolve().parents[1]
OUT=B/"reports"/"figures"
def md(p):
    rows={}
    for line in open(p):
        c=[x.strip() for x in line.strip().strip('|').split('|')]
        if len(c)==7 and c[0] not in ('Run','---'): rows[c[0]]=c
    return rows
free=md(f"{B}/reports/benchmark_runs/2026-10-22_v1_free_text2cypher.md")
hyb=md(f"{B}/reports/benchmark_runs/2026-10-22_v1_hybrid.md")
e06=pd.read_csv(f"{B}/data/processed/06_hybrid_eval_2026-10-22_1613.csv")
e05=pd.read_csv(f"{B}/data/processed/05_live_eval_2026-10-22_1521.csv")
def calls(df,model,config=None):
    d=df[df.model==model]
    if config: d=d[d.config==config]
    return f"{int(d.model_calls.sum())}" if len(d) else "not recorded"
spec=[("Free Text2Cypher","Claude Opus 4.6",free,"anthropic_claude-opus-4-6__langgraph_plan-guard-execute__2026-10-22_0935",None),
      ("Free Text2Cypher","Claude Sonnet 4.6",free,"anthropic_claude-sonnet-4-6__langgraph_plan-guard-execute__2026-10-22_0935",None),
      ("Free Text2Cypher","GLM-5.3",free,"zai_glm-5.3__langgraph_plan-guard-execute__2026-10-22_1521",("05","zai/glm-5.3")),
      ("Hybrid router + templates","Claude Opus 4.6",hyb,"hybrid_llm_router__anthropic_claude-opus-4-6__2026-10-22_1613",("06","anthropic/claude-opus-4-6")),
      ("Hybrid router + templates","Claude Sonnet 4.6",hyb,"hybrid_llm_router__anthropic_claude-sonnet-4-6__2026-10-22_1613",("06","anthropic/claude-sonnet-4-6")),
      ("Hybrid router + templates","GLM-5.3",hyb,"hybrid_llm_router__zai_glm-5.3__2026-10-22_1613",("06","zai/glm-5.3"))]
rows=[]
for arch,model,src,run,c in spec:
    r=src[run]; corr,ev,beh,ov,n,ms=r[1],r[2],r[3],r[4],r[5],r[6]
    if c is None: k="not recorded"
    elif c[0]=="05": k=calls(e05,c[1])
    else: k=calls(e06,c[1],"hybrid_llm_router")
    rows.append([arch,model,f"{float(ov):.1f}%",f"{float(corr):.1f}%",f"{float(ev):.1f}%",f"{float(ms)/1000:.1f} s",k])
pd.DataFrame(rows,columns=["arch","model","overall","correct","evidence","latency","calls"]).to_csv(OUT/"iati_budget_table_2026-10-23_values.csv",index=False)

plt.rcParams["font.family"]=["Inter","Helvetica Neue","Arial","DejaVu Sans"]
W,H=12.8,4.75
fig=plt.figure(figsize=(W,H),dpi=300); ax=fig.add_axes([0,0,1,1]); ax.set_xlim(0,W); ax.set_ylim(H,0); ax.axis("off")
GREEN="#0F6E4F"; INK="#1F2328"; MUTED="#57606A"; ROW="#F3F5F4"; LINE="#D8DEE4"
L,R=0.28,W-0.28
ax.text(L,0.48,"Accuracy and latency per full benchmark run (v1, 20 questions)",fontsize=17,weight="bold",color=INK,va="center")
cols=["Architecture","Model","Overall score","Correctness","Evidence F1","Mean latency / question","LLM calls"]
x=[L+0.12,3.05,6.15,7.55,8.85,10.75,R-0.12]
al=["left","left","right","right","right","right","right"]
y0,hh,rh=0.85,0.42,0.40
ax.add_patch(plt.Rectangle((L,y0),R-L,hh,color=GREEN))
for xi,c,a in zip(x,cols,al): ax.text(xi,y0+hh/2,c,color="white",fontsize=10.5,weight="semibold",ha=a,va="center")
for i,r in enumerate(rows):
    y=y0+hh+i*rh
    if i%2==0: ax.add_patch(plt.Rectangle((L,y),R-L,rh,color=ROW))
    ax.plot([L,R],[y+rh,y+rh],color=LINE,lw=0.8)
    bold= r[2]=="100.0%"
    for xi,v,a in zip(x,[r[0]+(" (nb05)" if i<3 else " (nb06)")]+r[1:],al):
        ax.text(xi,y+rh/2,v,fontsize=10.5,ha=a,va="center",color=MUTED if v=="not recorded" else INK,weight="bold" if bold and v!="not recorded" else "normal")
yn=y0+hh+len(rows)*rh+0.32
notes=["Overall = 70% value correctness + 30% evidence F1 (Q01 to Q16); reason-code F1 for the four abstain/clarify questions (Q17 to Q20). Scored by the team benchmark scorer.",
       "Sources: reports/benchmark_runs/2026-10-22_v1_free_text2cypher.md (nb05) and 2026-10-22_v1_hybrid.md (nb06). LLM calls: sum of model_calls in data/processed/05_live_eval_2026-10-22_1521.csv",
       "and 06_hybrid_eval_2026-10-22_1613.csv (0 retries); the nb05 Claude runs did not save a per-question CSV, so their call count is not recorded."]
for j,n in enumerate(notes): ax.text(L,yn+j*0.24,n,fontsize=8.2,color=MUTED,va="center")
fig.savefig(OUT/"iati_budget_table_2026-10-23.jpg",dpi=300,pil_kwargs={"quality":95})
print("saved")
